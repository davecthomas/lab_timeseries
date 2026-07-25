---
timestamp: "2025-10-13T14:19:29Z"
author: "Dave Thomas"
branch: "main"
thread_id: "memory-bootstrap"
turn_id: "memory-bootstrap"
decision_candidate: true
bootstrapped_at: "2026-07-23T19:38:46Z"
ai_generated: true
ai_model: "claude-fable-5"
ai_tool: "claude"
ai_surface: "claude-code"
ai_executor: "local-agent"
related_adrs:
files_touched:
  - "src/lab_timeseries_grapher/lab_timeseries_grapher.py"
  - "README.md"
---

## Why

The grapher needs a stable boundary between upstream lab-data cleaning and downstream visualization. Fixing a canonical cleaned-CSV schema lets the plotting layer stay ignorant of how raw lab exports are normalized.

## What changed

- Canonical input is a cleaned labs CSV with six required columns: `Date`, `Test Name`, `Value_Numeric`, `Units`, `Range_Low`, `Range_High`; all other columns are ignored.
- Input CSVs live under the project `data/` directory; `resolve_csv_path` accepts an absolute path but resolves bare filenames against `data/`.
- Data cleaning is fail-soft per row: rows with unparseable dates or values are skipped and tests with no valid rows are dropped, while the run hard-fails only on missing required columns or zero plottable rows.

## Evidence

- commit 0dc85d9: timeseries graphs v1
- doc README.md: "Input" / "Expected columns (from your cleaned file)" / "Notes"
- src/lab_timeseries_grapher/lab_timeseries_grapher.py: `resolve_csv_path`, `load_dataframe`, `prepare_tests`, required-columns check in `main`

## Next

- Upstream cleaning scripts must keep emitting this exact column contract; any schema change needs a coordinated update here.
- README default filename (`blood_results_units_fixed.csv`) and code default (`labs_results.csv`) disagree; reconcile.
