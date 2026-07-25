# Blood Metrics

A [Dash](https://dash.plotly.com/) web app for exploring blood-test results over time. Each metric gets an interactive chart with its normal range shaded; results outside the range are flagged on the chart, in the metric list, and in a summary tile.

## Features

- Per-metric time-series charts with the normal range shaded and out-of-range points marked (▲ above, ▼ below)
- Summary tiles: metrics tracked, lab draws, latest draw, out-of-range count
- Metric list with latest value, draw date, and in/out-of-range status
- Search, panel filter (CBC, metabolic, lipid, …), and an out-of-range-only toggle
- Date window presets (all / 5 y / 2 y / 1 y)
- Chart selection survives filtering; hidden selections stay charted

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

## Install

```bash
poetry install
```

## Run

```bash
poetry run lab-timeseries-grapher
```

Open http://127.0.0.1:8050 in your browser.

### Arguments

- `--csv`: CSV filename (looked up in `data/`) or an absolute path
- `--host`: host interface (default `127.0.0.1`)
- `--port`: port (default `8050`)
- `--debug`: Dash debug mode with live reload
- `--log-level`: e.g. `DEBUG`, `INFO`, `WARNING` (default `INFO`, or `LAB_TS_LOG_LEVEL`)

## Development

```bash
poetry run pytest                 # tests
poetry run ruff check src tests   # lint
```

Code layout (`src/lab_timeseries_grapher/`):

| Module | Role |
|---|---|
| `data.py` | CSV loading, cleaning, `MetricSeries` model, range/status logic |
| `figures.py` | Plotly figure construction |
| `layout.py` | Dash layout: header tiles, sidebar, chart cards |
| `theme.py` | Color tokens and page CSS |
| `app.py` | App factory and callbacks |
| `cli.py` | Command-line entry point |

## Notes

- The normal-range band uses the most frequent `(Range_Low, Range_High)` pair for the test; with no repeated pair it falls back to the median low/high.
- A metric's in/out-of-range status compares its most recent numeric value to that band.
- Rows with an unparseable `Date` or missing `Value_Numeric` are skipped for that chart; other rows still plot.
