"""AI commentary on selected metrics, via ai-api-unified (Claude only for now).

The prompt is assembled here and never surfaced in the UI: the app shows a
button and the resulting commentary. The instructions come from the repo-local
`skills/bloodwork-analysis-helper` skill so the wording can be revised without
touching Python.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from .data import STATUS_HIGH, STATUS_LOW, MetricSeries
from .figures import filter_window

logger = logging.getLogger("lab_timeseries_grapher")

SKILL_NAME = "bloodwork-analysis-helper"
ENGINE = "claude"
MAX_RESPONSE_TOKENS = 2048
REQUEST_TIMEOUT_SECONDS = 120.0

STATUS_LABEL = {STATUS_LOW: "LOW", STATUS_HIGH: "HIGH"}


class CommentaryError(RuntimeError):
    """Raised when commentary cannot be produced, with a user-safe message."""


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def skill_path() -> Path:
    return project_root() / "skills" / SKILL_NAME / "SKILL.md"


def strip_frontmatter(text: str) -> str:
    """Drop a leading YAML frontmatter block, if present."""
    if not text.startswith("---"):
        return text.strip()
    parts = text.split("---", 2)
    return parts[2].strip() if len(parts) == 3 else text.strip()


def load_skill_prompt() -> str:
    """Read the bloodwork-analysis-helper skill body as the system prompt.

    Read per request, not cached: editing SKILL.md is the documented way to
    change the commentary, and it should take effect without a restart.
    """
    path = skill_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CommentaryError(f"Could not read the analysis skill at {path}.") from exc

    body = strip_frontmatter(raw)
    if not body:
        raise CommentaryError(f"The analysis skill at {path} is empty.")
    return body


def format_metric(series: MetricSeries, cutoff: pd.Timestamp | None = None) -> str:
    """Render one metric as the prompt's plain-text block."""
    idx = filter_window(series, cutoff)
    lines = [f"### {series.name}"]
    if series.units:
        lines.append(f"Units: {series.units}")
    if series.panel:
        lines.append(f"Panel: {series.panel}")
    if series.band is None:
        lines.append("Reference range: not supplied by the lab")
    else:
        low, high = series.band
        lines.append(f"Reference range: {low:g} to {high:g}")

    if not idx:
        lines.append("Measurements: none in the selected date window")
        return "\n".join(lines)

    lines.append("Measurements (oldest first):")
    for i in idx:
        date = series.dates[i].strftime("%Y-%m-%d")
        flag = STATUS_LABEL.get(series.status_of(series.values[i]), "")
        suffix = f"  [{flag}]" if flag else ""
        lines.append(f"- {date}: {series.display_values[i]}{suffix}")
    return "\n".join(lines)


def build_prompt(
    metrics: dict[str, MetricSeries],
    selected: list[str],
    cutoff: pd.Timestamp | None = None,
) -> str:
    """Assemble the user prompt for the selected metrics."""
    blocks = [format_metric(metrics[name], cutoff) for name in selected if name in metrics]
    if not blocks:
        raise CommentaryError("Select at least one metric to analyze.")

    window = "all available results" if cutoff is None else f"results since {cutoff:%Y-%m-%d}"
    header = (
        f"Here are {len(blocks)} lab metric(s) for one person, covering {window}. "
        "Write the commentary described in your instructions."
    )
    return f"{header}\n\n" + "\n\n".join(blocks)


def load_env() -> None:
    """Load .env from the project root without clobbering real env vars."""
    load_dotenv(project_root() / ".env", override=False)


def is_configured() -> bool:
    """True when an Anthropic API key is available."""
    load_env()
    return bool(os.getenv("ANTHROPIC_API_KEY", "").strip())


def configured_model_name() -> str:
    """Name of the model the commentary would call, for the consent prompt.

    Prefers the env override, else the provider's own default. Falls back to a
    generic label when the provider package cannot be inspected.
    """
    load_env()
    model = os.getenv("COMPLETIONS_MODEL_NAME", "").strip()
    if model:
        return model
    try:
        from ai_api_unified.completions.ai_anthropic_completions import AiAnthropicCompletions

        return str(AiAnthropicCompletions.DEFAULT_COMPLETIONS_MODEL)
    except Exception:  # pragma: no cover - provider package unavailable
        logger.warning("Could not read the provider default model name", exc_info=True)
        return "the configured Claude model"


def _completions_client():
    """Build the Claude completions client from ai-api-unified."""
    from ai_api_unified.ai_factory import AIFactory

    model = os.getenv("COMPLETIONS_MODEL_NAME", "").strip() or None
    return AIFactory.get_ai_completions_client(model_name=model, completions_engine=ENGINE)


def generate_commentary(
    metrics: dict[str, MetricSeries],
    selected: list[str],
    cutoff: pd.Timestamp | None = None,
) -> str:
    """Return markdown commentary for the selected metrics.

    Raises CommentaryError with a message safe to show in the UI.
    """
    prompt = build_prompt(metrics, selected, cutoff)
    system_prompt = load_skill_prompt()

    load_env()
    if not is_configured():
        raise CommentaryError(
            "No ANTHROPIC_API_KEY found. Copy .env.example to .env and add your key."
        )

    try:
        client = _completions_client()
    except Exception as exc:
        logger.exception("Could not build the completions client")
        raise CommentaryError(f"Could not reach the AI provider: {exc}") from exc

    logger.info("Requesting AI commentary for %d metric(s)", len(selected))
    try:
        response = client.send_prompt(
            prompt,
            system_prompt=system_prompt,
            max_response_tokens=MAX_RESPONSE_TOKENS,
            request_timeout_seconds=REQUEST_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        logger.exception("AI commentary request failed")
        raise CommentaryError(f"The AI request failed: {exc}") from exc

    text = (response or "").strip()
    if not text:
        raise CommentaryError("The AI returned an empty response. Try again.")
    return text
