<!-- repo-context:start -->
## Purpose

Dash web app that charts personal blood-test results over time, with normal-range bands, out-of-range flags, and filterable metric selection. Loads a cleaned labs CSV from `data/` (gitignored).

## Directory map

| Path | Purpose |
|---|---|
| `src/lab_timeseries_grapher/` | The app package: `data.py` (CSV → `MetricSeries`), `figures.py` (Plotly charts), `layout.py` (Dash layout), `theme.py` (colors/CSS), `commentary.py` (AI prompt + Claude call), `app.py` (factory + callbacks), `cli.py` (entry point) |
| `skills/bloodwork-analysis-helper/` | `SKILL.md` — the system prompt for AI commentary; edit here rather than in Python |
| `tests/` | pytest suite for data shaping, figures, prompt assembly, and callback helpers |
| `data/` | Gitignored lab CSVs — never commit or paste contents; values are personal health data |
| `.github/workflows/` | CI: ruff + pytest |

## Dev commands

| Task | Command |
|---|---|
| Run app | `make` (installs deps, serves http://127.0.0.1:8050; `PORT=` to override) |
| Test | `make test` |
| Lint | `make lint` |
| Lint + test | `make check` |

## Conventions

- `src/` layout; entry point is `lab_timeseries_grapher.cli:main` (mirrored in `[project.scripts]` and `[tool.poetry.scripts]`)
- Python 3.11–3.13 (`ai-api-unified` sets the floor)
- Selection state is tracked by metric id in `dcc.Store("selection-store")`; DataTable row indices re-map when filters change the row set. One callback owns table data + selection, since split ownership makes the two chase each other
- Chart colors come from `theme.py` tokens (validated dark palette); out-of-range status always pairs color with a shape/text glyph (▲/▼)
- AI calls go through `ai-api-unified` (`AIFactory.get_ai_completions_client`), never a provider SDK directly; Claude is the only engine wired up. Secrets come from a gitignored `.env` (see `.env.example`)
- Prompt text lives in `skills/*/SKILL.md`, never inline in Python, and is never shown to the end user
- Ruff rule set is pinned in `pyproject.toml` (`E4,E7,E9,F,UP,C4,I`, line length 100)

## Do not read

- `data/` CSVs — personal health data; use the synthetic frames in `tests/` as schema examples
- `.env` — holds a live API key; read `.env.example` for the variable names
- `.venv/`, `__pycache__/`, `poetry.lock` unless doing dependency work
- `.agents/memory/` — shared-memory shards, not app code

## Last verified

2026-07-25 — sources: README.md, pyproject.toml, Makefile, .env.example, .github/workflows/ci.yml
<!-- repo-context:end -->
