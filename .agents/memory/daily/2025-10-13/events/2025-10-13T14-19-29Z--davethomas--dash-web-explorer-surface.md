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
  - "pyproject.toml"
---

## Why

Exploring dozens of lab metrics over time is an interactive task: the user picks metrics, sorts by recency, and hovers for exact values. A local web app serves that better than a folder of static images.

## What changed

- The delivery surface is a local Plotly Dash web app (`app.run` on `127.0.0.1:8050` by default), not static PNG/PDF export.
- Metrics appear in a sidebar table sorted by most recent result date, with the ten most recently updated metrics selected by default (`INITIAL_METRIC_COUNT = 10`); charts render as cards for the current selection.
- Styling is a dark-theme shell (Pico CSS + Inter font via CDN) with inline CSS in the module; charts use Plotly with a translucent teal band and sky-blue series line.
- README still documents an earlier static `--outdir`/`--pdf` flow that the code no longer implements — the Dash app is the source of truth.

## Evidence

- commit 0dc85d9: timeseries graphs v1
- src/lab_timeseries_grapher/lab_timeseries_grapher.py: `main` CLI args (`--host`, `--port`, `--debug`), Dash layout and `update_graphs` callback
- pyproject.toml: `plotly>=5.24.0`, `dash>=2.17.0` dependencies

## Next

- Update README usage section to describe the Dash server flow instead of PNG/PDF output.
