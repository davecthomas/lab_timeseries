# Blood Metrics

A [Dash](https://dash.plotly.com/) web app for exploring blood-test results over time. Each metric gets an interactive chart with its normal range shaded; results outside the range are flagged on the chart, in the metric list, and in a summary tile.

## Features

- Per-metric time-series charts with the normal range shaded and out-of-range points marked (▲ above, ▼ below)
- Summary tiles: metrics tracked, lab draws, latest draw, out-of-range count
- Metric list with latest value, draw date, and in/out-of-range status
- A plain-language description on each chart saying what that test measures
- **Add data** — record a new result from the toolbar, the sidebar, or the ＋ on any chart
- **Import CSV** — merge a lab export, with a preview of what changes
- **Clean up data** — find and repair duplicates, broken numbers and missing units, with a preview
- **Relevant conditions** — declare a benign condition and see the range it would explain, drawn alongside the normal one
- Click the **Out of range** tile to filter the list to just those tests
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

## Adding a result

Press **＋ Add data**, choose the metric, pick a date from the calendar, and enter a value. The dialog shows the test's units and what it measures once a metric is chosen. When exactly one metric is selected in the sidebar, the picker is pre-filled with it.

The units and normal range are pre-filled from the band in use for that metric — change them if your lab report says something different. Whatever range the row ends up with is the range that result is judged against.

The result is appended to `data/labs_results.csv` — the same file your lab export lives in, so there is one source of truth. The new row inherits its units, reference range, and panel from that metric's most recent existing row, so the point lands in the band the chart already draws. Its `Notes` cell records `Manually entered <date>`, which is how you find or remove entries later.

The write is atomic: an interrupted save cannot leave a truncated file behind. Entering a date that already has a result for that metric is refused rather than silently overwriting.

## Relevant conditions

Some people have a persistent, harmless reason for a result to sit outside the population range. A thalassemia carrier runs a low MCV for life. Gilbert syndrome raises bilirubin and does nothing else. Duffy-null individuals have a neutrophil count below the standard floor with no added infection risk. Against the population interval these read as findings on every single draw.

Ticking a condition in the sidebar draws **an extra band, in its own colour, alongside the normal one**:

```
MCH   Latest 22.4 pg ▼ low
      Range 26–32 pg · age/sex reference 27–32 pg
      ■ Thalassemia trait: a low MCH accompanies the small red cells of
        thalassemia trait, typically 19–26 pg.
```

The green normal band stays where it was, the purple band shows 19–26, and the point sits in the purple — still flagged low, but now visibly *explained*.

**The normal band and the out-of-range flags never change.** That is deliberate. Replacing the band would mean a ticked checkbox could silently hide a real abnormality: a carrier who later becomes iron deficient still needs their falling MCV to register. Showing both boundaries lets you see the value, the population range, and the range the condition would account for, and decide which you are looking at.

One legend covers the whole chart set. Colours separate by hue rather than lightness, since the bands overlap, and every band is also named in text on the card it affects — the colour never carries the meaning by itself.

Some conditions add a note and no band. Biotin interference is not a shifted interval, it is an unreliable measurement, so inventing a range for it would misrepresent what is known; those are marked *(note only)* in the legend. Where a band cannot be converted into the metric's units it is dropped rather than rescaled, and the note still stands.

Every condition and band is authored and cited in `conditions.py`. None of this is diagnostic, and a checkbox is not a diagnosis.

## Cleaning up the data

**✓ Clean up data** scans every row for the ways lab exports arrive damaged, and repairs the ones it can prove:

- the same test recorded twice on the same day — the later row is kept, matching the import rule
- a thousands separator that ate a value, so `3,457` was stored as `3`
- the same truncation inside a reference range, so `1,500 - 7,800` became `500`–`7`
- a units column left blank while the printed value carried the unit
- a reference range stored low-high inverted

Every repair recovers something another column of the same row already states; none invents a number. Nothing is written until you confirm, and the file is backed up first to `data/backups/` under its original name — one backup, overwritten each run, rather than a growing pile of copies of your health data.

The backup deliberately does **not** sit beside the data file. `/data` is scanned for the lab CSV by name, falling back to the single CSV present when the name does not match, so a second `.csv` alongside it would break startup — and if the data file were ever lost, a backup left in `/data` would silently be loaded in its place. Backups in a subdirectory can be neither.

```
7 to fix   376 rows scanned
Duplicate rows removed (4)
  Calcium · 2021-03-30 · 9.8 mg/dL recorded twice
Values restored from a truncated number (1)
  Absolute Neutrophils · 2026-09-01 · 3 → 3457
```

Two kinds are reported but deliberately **not** fixed, because the row alone cannot settle them: a units column that genuinely contradicts the printed value (choosing a side would rescale a result), and a row with no readable number at all (`NOT APPLICABLE (calc)`, `B Pattern`). Those are listed so you can decide. Units that merely look different — `10^3/µL` against `x10E3/uL` — are recognised as the same unit and left alone.

Running it twice is a no-op: the second pass finds nothing to fix.

## Importing a CSV

**↑ Import CSV** takes a lab export in whatever shape it arrives. Columns are worked out from the file: headers first (`Collected`, `Analyte`, `Result`, `UOM`, `Reference Range` all resolve), falling back to content — the column that parses as dates, the one that is mostly numeric, the one that reads like test names.

Nothing is written until you confirm. The preview shows how the columns were read, what will be added, and what will be replaced:

```
2 added   1 replaced   0 skipped
Columns read as: Date ← Collected, Test Name ← Analyte, Value ← Result, …
Replacing:  ALT (sgpt) · 2025-10-10 · 23 U/L → 99 U/L
Adding:     Ferritin · 2026-08-01 · 82 ng/mL
```

A result is identified by its test and its date. **When an upload carries a result for a test and date you already have, the uploaded one wins** — a corrected or re-issued report supersedes what was there. Tests the file introduces are added; rows that cannot be parsed are counted and skipped.

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
| `entries.py` | Manual result entry appended to the labs CSV |
| `state.py` | Reloadable app data, so an entry appears without a restart |
| `app.py` | App factory and callbacks |
| `cli.py` | Command-line entry point |

Python 3.11–3.13 is required (`ai-api-unified` sets the floor).

## Reference ranges

A row that carries a reference range states the range for that result, so that range draws the band. Where no row supplies one, a published reference range selected for an age and sex is used instead. How a row arrived makes no difference — a result typed into the app is a row like any other.

When rows disagree, the most recent stated range wins: a newer report supersedes an older one.

Age and sex are set in the sidebar and take effect immediately; every chart re-bands. They can also be given at startup:

```bash
make run                       # defaults to age 60, male
poetry run lab-timeseries-grapher --age 72 --sex female
```

Ranges live in `src/lab_timeseries_grapher/reference_ranges.py`, one entry per analyte with the source it came from (MedlinePlus, StatPearls, NCEP ATP III, Mayo Clinic Labs, ADA). PSA and ESR are banded by age; hemoglobin, hematocrit and RBC by sex.

**These are authored from published sources, not from your lab**, and published sources disagree — free T4 is 0.9–1.7 ng/dL at Mayo and 0.70–1.48 on one report in this dataset. A range is applied only when its units reconcile with the metric's; where they cannot, or where no consensus interval exists (particle assays, calculated ratios), the lab's own range stands.

## Notes

- The normal-range band uses the most frequent `(Range_Low, Range_High)` pair for the test; with no repeated pair it falls back to the median low/high.
- A metric's in/out-of-range status compares its most recent numeric value to that band.
- Rows with an unparseable `Date` or missing `Value_Numeric` are skipped for that chart; other rows still plot.
- Chart descriptions come from the CSV's `Notes` column, with panel prefixes and reference-range boilerplate stripped. 134 of 166 metrics have one; the rest show no description rather than an invented one.
