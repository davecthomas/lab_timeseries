<!-- repo-context:start -->
## Purpose

Dash web app that charts personal blood-test results over time, with normal-range bands, out-of-range flags, and filterable metric selection. Loads a cleaned labs CSV from `data/` (gitignored).

## Directory map

| Path | Purpose |
|---|---|
| `src/lab_timeseries_grapher/` | The app package: `data.py` (CSV → `MetricSeries`), `figures.py` (Plotly charts), `layout.py` (Dash layout), `theme.py` (colors/CSS), `app.py` (factory + callbacks), `cli.py` (entry point) |
| `tests/` | pytest suite for data shaping, figures, and callback helpers |
| `data/` | Gitignored lab CSVs — never commit or paste contents; values are personal health data |
| `.github/workflows/` | CI: ruff + pytest |

## Dev commands

| Task | Command |
|---|---|
| Install | `poetry install` |
| Run app | `poetry run lab-timeseries-grapher` (serves http://127.0.0.1:8050) |
| Test | `poetry run pytest` |
| Lint | `poetry run ruff check src tests` |

## Conventions

- `src/` layout; entry point is `lab_timeseries_grapher.cli:main` (mirrored in `[project.scripts]` and `[tool.poetry.scripts]`)
- Selection state is tracked by metric id in `dcc.Store("selection-store")`; DataTable row indices re-map when filters change the row set
- Chart colors come from `theme.py` tokens (validated dark palette); out-of-range status always pairs color with a shape/text glyph (▲/▼)
- Ruff rule set is pinned in `pyproject.toml` (`E4,E7,E9,F,UP,C4,I`, line length 100)

## Do not read

- `data/` CSVs — personal health data; use the synthetic frames in `tests/` as schema examples
- `.venv/`, `__pycache__/`, `poetry.lock` unless doing dependency work
- `.agents/memory/` — shared-memory shards, not app code

## Last verified

2026-07-25 — sources: README.md, pyproject.toml, .github/workflows/ci.yml
<!-- repo-context:end -->
