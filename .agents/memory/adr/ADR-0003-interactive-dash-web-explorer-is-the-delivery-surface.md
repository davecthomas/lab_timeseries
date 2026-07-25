# ADR-0003 Interactive Dash web explorer is the delivery surface

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

Purpose: Interactive Dash web explorer is the delivery surface
Derived from: [2025-10-13T14-19-29Z--davethomas--dash-web-explorer-surface](../daily/2025-10-13/events/2025-10-13T14-19-29Z--davethomas--dash-web-explorer-surface.md)

## Context

Exploring dozens of lab metrics over time is an interactive task: the user picks metrics, sorts by recency, and hovers for exact values. A local web app serves that better than a folder of static images.

## Decision

- The delivery surface is a local Plotly Dash web app (`app.run` on `127.0.0.1:8050` by default), not static PNG/PDF export.
- Metrics appear in a sidebar table sorted by most recent result date, with the ten most recently updated metrics selected by default (`INITIAL_METRIC_COUNT = 10`); charts render as cards for the current selection.
- Styling is a dark-theme shell (Pico CSS + Inter font via CDN) with inline CSS in the module; charts use Plotly with a translucent teal band and sky-blue series line.
- README still documents an earlier static `--outdir`/`--pdf` flow that the code no longer implements — the Dash app is the source of truth.

## Consequences

- Update README usage section to describe the Dash server flow instead of PNG/PDF output.

## Source memory events

- [2025-10-13T14-19-29Z--davethomas--dash-web-explorer-surface](../daily/2025-10-13/events/2025-10-13T14-19-29Z--davethomas--dash-web-explorer-surface.md)

## Related code paths

- src/lab_timeseries_grapher/lab_timeseries_grapher.py
- pyproject.toml
