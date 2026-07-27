# Blood Metrics

A [Dash](https://dash.plotly.com/) web app for exploring blood-test results over time. Each metric gets an interactive chart with its normal range shaded; results outside the range are flagged on the chart, in the metric list, and in a summary tile.

## Features

- Per-metric time-series charts with the normal range shaded and out-of-range points marked (▲ above, ▼ below)
- Summary tiles: metrics tracked, lab draws, latest draw, out-of-range count
- Metric list with latest value, draw date, and in/out-of-range status
- Search, panel filter (CBC, metabolic, lipid, …), and an out-of-range-only toggle
- Select all / clear all, and date window presets (all / 5 y / 2 y / 1 y)
- **Export CSV** — downloads the selected metrics as `blood-metrics-YYYY-MM-DD.csv`
- Chart selection survives filtering; hidden selections stay charted
- **Analysis with AI** — commentary on the selected metrics from Claude, behind a first-run consent prompt (see below)

## Input

Put your CSV in the `data/` directory. `data/` is **gitignored**, so lab results never get committed.

By default the app loads `data/labs_results.csv`. If that name is absent and `data/` holds exactly one CSV, the app uses that file. Override with `--csv YOUR_FILE.csv`.

### Required columns

- `Date` (ISO preferred, e.g. `YYYY-MM-DD`)
- `Test Name`
- `Value_Numeric` (numeric value parsed from `Value`)
- `Units`
- `Range_Low` (numeric or `n/a`)
- `Range_High` (numeric or `n/a`)

### Optional columns

- `Value` — the original result string (e.g. `<0.1`), shown in hovers and the metric list
- `Panel` — groups metrics for the panel filter

Other columns are ignored.

## Exporting data

**Export CSV**, top right, downloads the metrics you have selected — one row per measurement, respecting the current date window — as `blood-metrics-YYYY-MM-DD.csv`, stamped with the export date.

Columns: `Date`, `Test Name`, `Panel`, `Value`, `Value_Numeric`, `Units`, `Range_Low`, `Range_High`, `Status`. `Value` keeps the lab's original string (`<0.1`, `3,457 cells/uL`); `Value_Numeric` is the parsed number the charts plot; `Status` is `in`, `low`, `high`, or blank when the lab gave no usable range.

It exports the selection rather than the whole file, so **Select all** then **Export CSV** gives you everything. The button is disabled while nothing is selected.

## AI commentary

Select one or more metrics and press **✦ Analysis with AI**. The app sends those metrics — values, dates, units, and reference ranges — to Claude and opens a pane beside the charts: a summary, out-of-range results, trends, and questions worth taking to a doctor.

### The analysis pane

The pane splits the view — charts on the left, commentary on the right — and stays in place while the charts scroll, so you can read the commentary against the data it describes. Close it with **✕** and the charts return to full width.

Every analysis you run is kept for the browser session and listed in the pane's index, so you can run several and move between them. Each is tied to the exact metrics and date window that produced it: change the selection and the pane steps aside rather than showing commentary about different tests. Return to that selection and the button reads **Show analysis**, revealing the held one instead of spending another request.

- **Copy** — the icon beside the title copies that analysis.
- **Export all** — downloads every analysis from the session as one markdown file.

**This sends the selected lab values to Anthropic's API.** The first time you press the button, the app names the configured model and asks whether to share your health data. Nothing leaves your machine until you agree, and only the metrics you selected go.

The dialog offers **Don't ask again**:

| Answer | Don't ask again | Result |
|---|---|---|
| Yes | unticked | Runs once; asks again next time |
| Yes | ticked | Runs, and stops asking |
| No | unticked | Cancels; asks again next time |
| No | ticked | Cancels and disables the button |

The choice is stored in your browser, so it survives reloads. To undo a remembered answer — including a disabled button — clear this site's storage in your browser.

### Setup

```bash
cp .env.example .env     # then add your key
```

`.env` is gitignored. It needs one value:

- `ANTHROPIC_API_KEY` — your Anthropic API key

Optional: `COMPLETIONS_MODEL_NAME` to pin a model (the library defaults to `claude-opus-4-8`). Claude is the only provider wired up right now; the button reports a clear message when no key is set.

Requests go through [`ai-api-unified`](https://pypi.org/project/ai-api-unified/), so switching providers later is a config change rather than a rewrite.

### The prompt

Instructions live in `skills/bloodwork-analysis-helper/SKILL.md` and are loaded as the system prompt. Edit that file to change the commentary's structure, tone, or rules — no Python changes needed. The prompt is not shown in the UI.

## Run

```bash
make
```

That installs dependencies (first run only) and starts the app. Open http://127.0.0.1:8050 in your browser. Use `make run PORT=8080` for a different port, and `make help` to list all targets.

Re-running `make` stops whatever is already serving the port and starts fresh, so you never end up reading stale code from an old server. `make stop` ends the running app without starting a new one.

Without make: `poetry install`, then `poetry run lab-timeseries-grapher`.

### Arguments

- `--csv`: CSV filename (looked up in `data/`) or an absolute path
- `--host`: host interface (default `127.0.0.1`)
- `--port`: port (default `8050`)
- `--debug`: Dash debug mode with live reload
- `--log-level`: e.g. `DEBUG`, `INFO`, `WARNING` (default `INFO`, or `LAB_TS_LOG_LEVEL`)

## Development

```bash
make test    # test suite
make lint    # ruff
make check   # both
```

Code layout (`src/lab_timeseries_grapher/`):

| Module | Role |
|---|---|
| `data.py` | CSV loading, cleaning, `MetricSeries` model, range/status logic |
| `figures.py` | Plotly figure construction |
| `layout.py` | Dash layout: header tiles, sidebar, chart cards |
| `theme.py` | Color tokens and page CSS |
| `commentary.py` | Prompt assembly and the Claude call for AI commentary |
| `analyses.py` | Session-held analyses: identity by selection, index, markdown export |
| `export.py` | CSV export of the metric data in view |
| `app.py` | App factory and callbacks |
| `cli.py` | Command-line entry point |

Python 3.11–3.13 is required (`ai-api-unified` sets the floor).

## Notes

- The normal-range band uses the most frequent `(Range_Low, Range_High)` pair for the test; with no repeated pair it falls back to the median low/high.
- A metric's in/out-of-range status compares its most recent numeric value to that band.
- Rows with an unparseable `Date` or missing `Value_Numeric` are skipped for that chart; other rows still plot.
