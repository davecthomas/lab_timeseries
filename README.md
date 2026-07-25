# Lab Time-Series Explorer

An interactive [Dash](https://dash.plotly.com/) web app for exploring per-test lab time series from a cleaned labs CSV, with a **green normal-range band** shown when a range is available.

## Input

Put your CSV in the `data/` directory. The `data/` directory is **gitignored**, so your lab data never gets committed.

By default the app loads `data/labs_results.csv`. If that name isn't present but `data/` contains exactly one CSV, the app uses that file automatically. Override the choice with `--csv YOUR_FILE.csv`.

### Expected columns

- `Date` (ISO preferred, e.g., `YYYY-MM-DD`)
- `Test Name`
- `Value_Numeric` (numeric value parsed from `Value`)
- `Units`
- `Range_Low` (numeric or `n/a`)
- `Range_High` (numeric or `n/a`)

Other columns are ignored.

## Install

Dependencies are defined in `pyproject.toml`. Install with Poetry:

```bash
poetry install
```

## Run

Start the web server:

```bash
poetry run lab-timeseries-grapher
```

Then open http://127.0.0.1:8050 in your browser.

### Arguments

- `--csv`: CSV filename (looked up in `data/`) or an absolute path. Default: `labs_results.csv`, with fallback to the only CSV in `data/`.
- `--host`: Host interface for the web server (default: `127.0.0.1`)
- `--port`: Port for the web server (default: `8050`)
- `--debug`: Run Dash in debug mode with live reload
- `--log-level`: Python logging level, e.g. `DEBUG`, `INFO`, `WARNING` (default: `INFO`, or `LAB_TS_LOG_LEVEL`)

Run `poetry run lab-timeseries-grapher --help` to see every option.

## Notes

- Tests are listed with the **most recently measured first**; the newest metrics are pre-selected on load.
- The **normal range band** is shaded green when both `Range_Low` and `Range_High` are usable numbers.

  - If multiple range pairs exist over time, the app chooses the **mode** (most frequent pair); with no clear mode it falls back to the **median** low/high across rows with numeric ranges.

- Any row missing `Value_Numeric` or with an unparseable `Date` is skipped for that chart (other rows still plot).
