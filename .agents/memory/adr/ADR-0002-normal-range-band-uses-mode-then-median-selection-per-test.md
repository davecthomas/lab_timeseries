# ADR-0002 Normal-range band uses mode-then-median selection per test

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

Purpose: Normal-range band uses mode-then-median selection per test
Derived from: [2025-10-13T14-19-29Z--davethomas--normal-range-band-rule](../daily/2025-10-13/events/2025-10-13T14-19-29Z--davethomas--normal-range-band-rule.md)

## Context

Lab reference ranges vary across labs and over time, so each test needs one representative normal range per chart. A deterministic selection rule keeps the band stable and explainable rather than jumping with every new result.

## Decision

- Each test's normal band uses the mode of `(Range_Low, Range_High)` pairs across rows where both bounds are numeric, accepted when the modal pair occurs at least twice or is the only pair.
- With no clear mode, the fallback is `median(low)` and `median(high)` across numeric rows.
- The band renders only when a representative pair exists; charts without usable ranges plot values with no band. Units are chosen the same way: most common non-empty units string per test.

## Consequences

- If per-era ranges matter (lab switches reference intervals), a time-segmented band would replace the single representative pair; that would supersede this rule.

## Source memory events

- [2025-10-13T14-19-29Z--davethomas--normal-range-band-rule](../daily/2025-10-13/events/2025-10-13T14-19-29Z--davethomas--normal-range-band-rule.md)

## Related code paths

- src/lab_timeseries_grapher/lab_timeseries_grapher.py
- README.md
