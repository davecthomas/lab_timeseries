"""Session-held AI analyses: identity, indexing, and export.

An analysis is tied to the exact metric selection and date window that
produced it, so the pane never shows commentary that describes a different
set of tests than the one currently selected.
"""

from __future__ import annotations

import json
from datetime import datetime

MAX_LABEL_METRICS = 2


def selection_key(names: list[str], window: str | None) -> str:
    """Stable identity for a selection: which metrics, over which window."""
    return json.dumps({"metrics": sorted(names), "window": window or "all"}, sort_keys=True)


def analysis_label(names: list[str]) -> str:
    """Short index label naming the metrics, e.g. 'MCV, RDW + 10 more'."""
    if not names:
        return "No metrics"
    head = ", ".join(names[:MAX_LABEL_METRICS])
    rest = len(names) - MAX_LABEL_METRICS
    return f"{head} + {rest} more" if rest > 0 else head


def window_label(window: str | None) -> str:
    """Human wording for a date-window value."""
    if not window or window == "all":
        return "all results"
    return f"last {window} y"


def make_analysis(
    names: list[str], window: str | None, text: str, created: datetime
) -> dict:
    """Build an index entry for a completed analysis."""
    return {
        "id": f"{int(created.timestamp() * 1000)}",
        "key": selection_key(names, window),
        "label": analysis_label(names),
        "metrics": list(names),
        "count": len(names),
        "window": window or "all",
        "created": created.strftime("%I:%M %p").lstrip("0"),
        "created_iso": created.isoformat(timespec="seconds"),
        "text": text,
    }


def upsert(entries: list[dict] | None, entry: dict) -> list[dict]:
    """Add an analysis, replacing any earlier one for the same selection.

    Re-running the same metrics refreshes that entry in place rather than
    stacking near-duplicates in the index. Newest first.
    """
    kept = [e for e in (entries or []) if e.get("key") != entry["key"]]
    return [entry] + kept


def find(entries: list[dict] | None, entry_id: str | None) -> dict | None:
    """Look up an analysis by id."""
    for entry in entries or []:
        if entry.get("id") == entry_id:
            return entry
    return None


def find_by_key(entries: list[dict] | None, key: str) -> dict | None:
    """Look up the analysis matching a selection key."""
    for entry in entries or []:
        if entry.get("key") == key:
            return entry
    return None


def export_markdown(entries: list[dict] | None) -> str:
    """Render every held analysis as one markdown document, oldest first."""
    ordered = list(reversed(entries or []))
    if not ordered:
        return "# Blood Metrics — AI analyses\n\nNo analyses in this session.\n"

    parts = ["# Blood Metrics — AI analyses", ""]
    for entry in ordered:
        parts.append(f"## {entry['label']}")
        parts.append("")
        parts.append(
            f"*{entry['count']} metric(s) · {window_label(entry.get('window'))} "
            f"· {entry.get('created_iso', entry.get('created', ''))}*"
        )
        parts.append("")
        parts.append("Metrics: " + ", ".join(entry.get("metrics", [])))
        parts.append("")
        parts.append(entry.get("text", "").strip())
        parts.append("")
        parts.append("---")
        parts.append("")
    parts.append("*Interpretation of numbers, not medical advice.*")
    return "\n".join(parts)


def export_filename(now: datetime) -> str:
    return f"blood-metrics-ai-analyses-{now:%Y%m%d-%H%M}.md"
