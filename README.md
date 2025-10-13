# Lab Time-Series Grapher

Generate per-test time-series charts (alphabetical) from a cleaned labs CSV, with a **green normal-range band** when available.

## Input

Place your CSV in the same directory. By default the script loads:

- `blood_results_units_fixed.csv`

Override with `--csv YOUR_FILE.csv`.

### Expected columns (from your cleaned file)

- `Date` (ISO preferred, e.g., `YYYY-MM-DD`)
- `Test Name`
- `Value_Numeric` (numeric value parsed from `Value`)
- `Units`
- `Range_Low` (numeric or `n/a`)
- `Range_High` (numeric or `n/a`)

Other columns are ignored for plotting.

## Install

```bash
# (optional) python -m venv .venv && source .venv/bin/activate
pip install -r <(python - <<'PY'
print("\\n".join([
    "pandas>=2.2.0",
    "matplotlib>=3.8.0",
    "numpy>=1.26.0",
    "python-dateutil>=2.9.0.post0",
]))
PY
)
```

_(Or use `pyproject.toml` with your preferred tool.)_

## Usage

```bash
python app.py --csv blood_results_units_fixed.csv --outdir plots --pdf all_tests.pdf
```

Arguments:

- `--csv` : Path to input CSV (default: `blood_results_units_fixed.csv`)
- `--outdir`: Output directory for PNGs (default: `plots`)
- `--pdf` : (Optional) Path to a multi-page PDF combining all charts

## Notes

- Tests are plotted **alphabetically**.
- The **normal range band** is shaded green when both `Range_Low` and `Range_High` are usable numbers.

  - If multiple range pairs exist over time, the script chooses the **mode** (most frequent pair); if there’s no clear mode it falls back to **median** low/high across rows with numeric ranges.

- Any row missing `Value_Numeric` or an unparseable `Date` is skipped for that chart (other rows still plot).
