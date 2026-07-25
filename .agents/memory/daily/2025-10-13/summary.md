# 2025-10-13 summary

## Snapshot

- Captured 4 memory events.
- Main work: Canonical input is a cleaned labs CSV with six required columns: `Date`, `Test Name`, `Value_Numeric`, `Units`, `Range_Low`, `Range_High`; all other columns are ignored.
- Top decision: The grapher needs a stable boundary between upstream lab-data cleaning and downstream visualization. Fixing a canonical cleaned-CSV schema lets the plotting layer stay ignorant of how raw lab exports are normalized. ([2025-10-13 14:19:29 UTC by Dave Thomas](events/2025-10-13T14-19-29Z--davethomas--csv-input-contract.md))
- Blockers: None.

| Metric | Value |
|---|---|
| Memory events captured | 4 |
| Repo files changed | 4 |
| Decision candidates | 4 |
| Active blockers | 0 |

## Major work completed

- Canonical input is a cleaned labs CSV with six required columns: `Date`, `Test Name`, `Value_Numeric`, `Units`, `Range_Low`, `Range_High`; all other columns are ignored.
- The delivery surface is a local Plotly Dash web app (`app.run` on `127.0.0.1:8050` by default), not static PNG/PDF export.
- Each test's normal band uses the mode of `(Range_Low, Range_High)` pairs across rows where both bounds are numeric, accepted when the modal pair occurs at least twice or is the only pair.
- The project is a Poetry-managed Python package (`lab-timeseries-grapher`, Python >=3.10) with dependencies mirrored in both `[project]` and `[tool.poetry]` tables.

## Why this mattered

- The grapher needs a stable boundary between upstream lab-data cleaning and downstream visualization. Fixing a canonical cleaned-CSV schema lets the plotting layer stay ignorant of how raw lab exports are normalized.
- Exploring dozens of lab metrics over time is an interactive task: the user picks metrics, sorts by recency, and hovers for exact values. A local web app serves that better than a folder of static images.
- Lab reference ranges vary across labs and over time, so each test needs one representative normal range per chart. A deterministic selection rule keeps the band stable and explainable rather than jumping with every new result.
- The project needs reproducible installs and a single documented way to run the tool. Poetry with a console-script entry point gives both without extra tooling.

## Active blockers

- None

## Decision candidates

- The grapher needs a stable boundary between upstream lab-data cleaning and downstream visualization. Fixing a canonical cleaned-CSV schema lets the plotting layer stay ignorant of how raw lab exports are normalized. ([2025-10-13 14:19:29 UTC by Dave Thomas](events/2025-10-13T14-19-29Z--davethomas--csv-input-contract.md))
- Exploring dozens of lab metrics over time is an interactive task: the user picks metrics, sorts by recency, and hovers for exact values. A local web app serves that better than a folder of static images. ([2025-10-13 14:19:29 UTC by Dave Thomas](events/2025-10-13T14-19-29Z--davethomas--dash-web-explorer-surface.md))
- Lab reference ranges vary across labs and over time, so each test needs one representative normal range per chart. A deterministic selection rule keeps the band stable and explainable rather than jumping with every new result. ([2025-10-13 14:19:29 UTC by Dave Thomas](events/2025-10-13T14-19-29Z--davethomas--normal-range-band-rule.md))
- The project needs reproducible installs and a single documented way to run the tool. Poetry with a console-script entry point gives both without extra tooling. ([2025-10-13 14:19:29 UTC by Dave Thomas](events/2025-10-13T14-19-29Z--davethomas--poetry-packaging.md))

## Next likely steps

- Keep `[project]` and `[tool.poetry]` dependency tables in sync when versions change; drift between them would silently split pip and Poetry installs.

## Relevant event shards

- [2025-10-13 14:19:29 UTC by Dave Thomas](events/2025-10-13T14-19-29Z--davethomas--csv-input-contract.md)
- [2025-10-13 14:19:29 UTC by Dave Thomas](events/2025-10-13T14-19-29Z--davethomas--dash-web-explorer-surface.md)
- [2025-10-13 14:19:29 UTC by Dave Thomas](events/2025-10-13T14-19-29Z--davethomas--normal-range-band-rule.md)
- [2025-10-13 14:19:29 UTC by Dave Thomas](events/2025-10-13T14-19-29Z--davethomas--poetry-packaging.md)
