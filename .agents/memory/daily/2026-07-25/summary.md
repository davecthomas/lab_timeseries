# 2026-07-25 summary

## Snapshot

- Captured 2 memory events.
- Main work: A new root Makefile defines install, run, test, lint, check, and help targets; run depends on install so a bare 'make' on a fresh clone installs dev dependencies and serves the app on a PORT-overridable port. README's Install section collapsed into a make-first Run section with a one-line Poetry fallback, and AGENTS.md's dev-commands table was rewritten around make with Makefile added to its verified sources.
- Top decision: None.
- Blockers: None.

| Metric | Value |
|---|---|
| Memory events captured | 2 |
| Repo files changed | 2 |
| Decision candidates | 0 |
| Active blockers | 0 |

## Major work completed

- A new root Makefile defines install, run, test, lint, check, and help targets; run depends on install so a bare 'make' on a fresh clone installs dev dependencies and serves the app on a PORT-overridable port. README's Install section collapsed into a make-first Run section with a one-line Poetry fallback, and AGENTS.md's dev-commands table was rewritten around make with Makefile added to its verified sources.
- load_skill_prompt() is no longer memoized; its docstring now records the editability rationale so the tradeoff survives in the code itself. The test suite gained a case that monkeypatches skill_path() to a temp file, reads it, rewrites it, and reads again, locking in the no-restart behavior. The old test's load_skill_prompt.cache_clear() call, which existed only to work around the cache, was removed.

## Why this mattered

- The documented workflow required knowing three separate Poetry commands before the app would start; contributors and agents each had to rediscover them. Standardizing on a Makefile whose default target installs dependencies and serves the ADR-0003 Dash explorer makes 'make' the canonical entry point for run, test, and lint, and both human docs (README) and agent docs (AGENTS.md) now teach the same commands.
- The project's stated convention is that commentary wording lives in skills/*/SKILL.md rather than inline in Python, so that prompt tuning is an editing task rather than a code change. Caching the file body for the process lifetime quietly broke that promise: an edit to SKILL.md had no effect until the Dash server was restarted, which is the opposite of what a file-based prompt is for. Reading per request trades a small local file read (already cheap next to a 120-second Claude call) for the editability the convention assumes. A future contributor optimizing startup cost should know the cache was removed deliberately.

## Active blockers

- None

## Decision candidates

- None

## Next likely steps

- Makefile, AGENTS.md, and README changes are uncommitted on main; commit them from a branch per repo convention. CI still invokes ruff and pytest directly rather than the make targets, so the Makefile and CI steps can drift apart.
- Changes are uncommitted on feat/ai-commentary alongside the larger commentary feature; they need a commit and PR. Open edge: skill_path() resolves relative to the source tree via parents[2], so an installed (non-editable) package would not find SKILL.md, and the CommentaryError path is the only signal if that happens.

## Relevant event shards

- [2026-07-25 17:04:53 UTC by 2355287-davecthomas](events/2026-07-25T17-04-53Z--2355287-davecthomas--thread_8f1e05c3-53f2-492e-aea8-e5a4b9c1f614--turn_27f65e7ed2.md)
- [2026-07-25 17:31:35 UTC by 2355287-davecthomas](events/2026-07-25T17-31-35Z--2355287-davecthomas--thread_8d35ef4b-45ec-4577-b2c3-485a7b1d639a--turn_6830154170.md)
