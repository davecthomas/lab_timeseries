<!-- repo-context:start -->
## Purpose

Dash web app that charts personal blood-test results over time, with normal-range bands, out-of-range flags, and filterable metric selection. Loads a cleaned labs CSV from `data/` (gitignored).

## Directory map

| Path | Purpose |
|---|---|
| `src/lab_timeseries_grapher/` | The app package: `data.py` (CSV → `MetricSeries`), `figures.py` (Plotly charts), `layout.py` (Dash layout), `theme.py` (colors/CSS), `commentary.py` (AI prompt + Claude call), `analyses.py` (session-held analyses + export), `export.py` (metric CSV export), `entries.py` (manual entry), `state.py` (reloadable AppData), `app.py` (factory + callbacks), `cli.py` (entry point) |
| `skills/bloodwork-analysis-helper/` | `SKILL.md` — the system prompt for AI commentary; edit here rather than in Python |
| `tests/` | pytest suite for data shaping, figures, prompt assembly, and callback helpers |
| `data/` | Gitignored lab CSVs — never commit or paste contents; values are personal health data |
| `.github/workflows/` | CI: ruff + pytest |

## Dev commands

| Task | Command |
|---|---|
| Run app | `make` (installs deps, reclaims the port, serves http://127.0.0.1:8050; `PORT=` to override) |
| Stop app | `make stop` |
| Test | `make test` |
| Lint | `make lint` |
| Lint + test | `make check` |

## Conventions

- `src/` layout; entry point is `lab_timeseries_grapher.cli:main` (mirrored in `[project.scripts]` and `[tool.poetry.scripts]`)
- Python 3.11–3.13 (`ai-api-unified` sets the floor)
- Selection state is tracked by metric id in `dcc.Store("selection-store")`; DataTable row indices re-map when filters change the row set. One callback owns table data + selection, since split ownership makes the two chase each other
- Chart colors come from `theme.py` tokens (validated dark palette); out-of-range status always pairs color with a shape/text glyph (▲/▼)
- AI calls go through `ai-api-unified` (`AIFactory.get_ai_completions_client`), never a provider SDK directly; Claude is the only engine wired up. Secrets come from a gitignored `.env` (see `.env.example`)
- Lab values reach the network only after the consent dialog; the analysis callback listens on the `ai-run-count` store, which only the consent gate writes. Keep that ordering — do not wire an analysis trigger straight to a button
- A run is detected by the counter advancing (`is_run_request`), never by `ctx.triggered_id` alone: clicking analyze changes `ai-analyze` and `ai-run-count` in one chain, and Dash then invokes the pane callback once reporting only the first trigger. Trigger-driven pane state lives in `resolve_pane_view` so it stays testable — Dash's wrapper rebuilds the callback context, so tests cannot inject a `triggered_id`
- Callbacks read `data.metrics` / `data.table_rows` off `AppData` rather than closing over them, so a manual entry can reload the CSV mid-session; a `data-version` store fans the refresh out to the table, tiles and charts
- The metric for a manual entry is chosen inside the dialog, not required beforehand; gating the button on the sidebar selection left it disabled on load and read as the feature being absent
- Dash's DataTable ships its own active-cell style (a red wash) and its `state` keys do not cover checkbox-selected rows; both are handled by CSS in `theme.py`, not `style_data_conditional`
- Manual entries append to the labs CSV atomically (temp file + `os.replace`) and inherit units/range/panel from the metric's latest existing row; `Notes` records provenance
- Band precedence: a range carried by the rows wins; the age/sex reference fills in only where no row states one. Rows are uniform — never branch on how a row was created
- `reference_ranges.py` (authored, cited, age/sex-aware) supplies the fallback band; `MetricSeries.lab_band` is the newest range stated by the rows (`latest_range`, superseding ADR-0002's mode-then-median, which let two old reports outvote the newest). A reference is applied only when `reference_in_units` can reconcile units — applying a cells/µL range to a 10^3/µL value would misread 2.7 as critically low
- Metric descriptions come from the `Notes` column via `data.describe()`; never generate them
- Downloads are selection-scoped and window-scoped, and use `dcc.Download` + `dcc.send_string`; filenames carry the export date
- Analyses are keyed by metric selection + date window (`analyses.selection_key`); the pane shows one only while it matches the current selection
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
