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
  - "pyproject.toml"
  - "poetry.lock"
  - "README.md"
---

## Why

The project needs reproducible installs and a single documented way to run the tool. Poetry with a console-script entry point gives both without extra tooling.

## What changed

- The project is a Poetry-managed Python package (`lab-timeseries-grapher`, Python >=3.10) with dependencies mirrored in both `[project]` and `[tool.poetry]` tables.
- The canonical invocation is the console script `lab-timeseries-grapher` mapping to `lab_timeseries_grapher.lab_timeseries_grapher:main`; running the module file directly is not the documented path.
- pandas is capped at `<2.3.3`; ruff line length is set to 100.

## Evidence

- commit 0dc85d9: timeseries graphs v1
- pyproject.toml: `[project.scripts]`, `[tool.poetry.scripts]`, dependency tables, `[tool.ruff]`
- doc README.md: "Install" / "Usage"

## Next

- Keep `[project]` and `[tool.poetry]` dependency tables in sync when versions change; drift between them would silently split pip and Poetry installs.
