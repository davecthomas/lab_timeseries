# ADR-0001 Cleaned labs CSV is the canonical input contract

Status: accepted
Date: 2025-10-13
Owners: Dave Thomas
Must read: true
Supersedes: 
Superseded by: 
ai-generated: True
ai-model: claude-fable-5
ai-tool: claude
ai-surface: claude-code
ai-executor: local-agent

Purpose: Cleaned labs CSV is the canonical input contract
Derived from: [2025-10-13T14-19-29Z--davethomas--csv-input-contract](../daily/2025-10-13/events/2025-10-13T14-19-29Z--davethomas--csv-input-contract.md)

## Context

The grapher needs a stable boundary between upstream lab-data cleaning and downstream visualization. Fixing a canonical cleaned-CSV schema lets the plotting layer stay ignorant of how raw lab exports are normalized.

## Decision

- Canonical input is a cleaned labs CSV with six required columns: `Date`, `Test Name`, `Value_Numeric`, `Units`, `Range_Low`, `Range_High`; all other columns are ignored.
- Input CSVs live under the project `data/` directory; `resolve_csv_path` accepts an absolute path but resolves bare filenames against `data/`.
- Data cleaning is fail-soft per row: rows with unparseable dates or values are skipped and tests with no valid rows are dropped, while the run hard-fails only on missing required columns or zero plottable rows.

## Consequences

- Upstream cleaning scripts must keep emitting this exact column contract; any schema change needs a coordinated update here.
- README default filename (`blood_results_units_fixed.csv`) and code default (`labs_results.csv`) disagree; reconcile.

## Source memory events

- [2025-10-13T14-19-29Z--davethomas--csv-input-contract](../daily/2025-10-13/events/2025-10-13T14-19-29Z--davethomas--csv-input-contract.md)

## Related code paths

- src/lab_timeseries_grapher/lab_timeseries_grapher.py
- README.md
