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

Lab reference ranges vary across labs and over time, so each test needs one representative normal range per chart. A deterministic selection rule keeps the band stable and explainable rather than jumping with every new result.

## What changed

- Each test's normal band uses the mode of `(Range_Low, Range_High)` pairs across rows where both bounds are numeric, accepted when the modal pair occurs at least twice or is the only pair.
- With no clear mode, the fallback is `median(low)` and `median(high)` across numeric rows.
- The band renders only when a representative pair exists; charts without usable ranges plot values with no band. Units are chosen the same way: most common non-empty units string per test.

## Evidence

- commit 0dc85d9: timeseries graphs v1
- doc README.md: "Notes" (mode-then-median range selection)
- src/lab_timeseries_grapher/lab_timeseries_grapher.py: `most_common_range`, `mode_units`, band trace in `make_figure`

## Next

- If per-era ranges matter (lab switches reference intervals), a time-segmented band would replace the single representative pair; that would supersede this rule.
