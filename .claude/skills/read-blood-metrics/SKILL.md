---
name: read-blood-metrics
description: Reads the user's blood-test results from the labs CSV as a compact markdown digest (overview, out-of-range now, per-metric histories). Use when the user asks about their own lab values, trends, or what is out of range. Never open the CSV directly.
---

# Read blood metrics

The labs CSV in `data/` is personal health data. Read it only when the user asks about their own results, and only through `lab-digest`. The command loads the file the same way the dashboard does, so every value, range and flag it prints matches the charts. Do not open or `cat` the CSV, and do not compute your own in/out-of-range verdicts.

## Where the data is

- The results live on the user's machine in `data/` at the root of the repository that contains this skill, the directory holding `.claude/`, `src/` and `pyproject.toml`. `data/` is gitignored, so the results are never on GitHub.
- The default file is `data/labs_results.csv`. If that name is absent and `data/` holds exactly one CSV, `lab-digest` uses that one. Backups in `data/backups/` are never read.
- With several CSVs in `data/`, pass the one you want: `--csv <name>.csv`. A CSV elsewhere can be passed by absolute path.

Do not ask the user to upload or paste the CSV. If the command fails with "CSV not found", `data/` holds either no CSV or several; the error lists the ones it found, so retry with `--csv` and one of those names. With no CSV at all, tell the user their results need to be in `data/` first.

## If you cannot run commands

`lab-digest` needs a shell in the repo with dependencies installed (`make install` or `poetry install`). If you have no shell, or you are not in this repository, do not ask for the raw CSV. Ask the user to either:

- open this repo in Claude Code and ask again there, or
- run `poetry run lab-digest > digest.md` in the repo root (add filters such as `--out-of-range` to keep it short) and share `digest.md`.

The digest is smaller than the CSV, has the dashboard's flags already applied, and leaves out the CSV's boilerplate notes.

## Commands

Run from the repo root. Start with the overview, then drill in.

| Need | Command |
|---|---|
| Overview: every metric's latest value, plus what is out of range now | `poetry run lab-digest` |
| Metric names only (to find the right spelling) | `poetry run lab-digest --list` |
| Full history for one or more metrics | `poetry run lab-digest -m ferritin -m "vitamin d"` |
| Full history for a panel | `poetry run lab-digest --panel "<panel name from --list>"` |
| Full history for everything out of range now | `poetry run lab-digest --out-of-range` |
| Limit any history to a window | add `--since 2024-01-01` |
| Reference ranges for another profile | add `--age 45 --sex female` (default: male, 60) |
| A CSV other than the default | add `--csv <name>.csv` |

`-m` matches case-insensitively by substring or known synonym (`-m hgb` finds hemoglobin). An exact name wins over substring matches. If nothing matches, the command says so; run `--list` and retry with the printed name.

## Reading the output

- **Range** shows its source: `(lab)` is the range printed on the report, `(reference)` is the age/sex population range used when the lab gave none. A history block also shows the population reference when it differs.
- **Flags**: `▼ LOW` and `▲ HIGH` are the dashboard's verdicts against that range. `ok` means in range; no flag in a history row means in range.
- **Current**: `yes` means measured within 12 months of the newest draw. "Out of range now" lists only current metrics. A `no` metric is often a retired test name from an old lab, so treat its flag as history, not a present finding.
- **Duplicate spellings**: one test can appear under several names from different labs (for example `MCV` and `Mean Corpuscular Volume`). Check `--list` and merge them when you describe a trend.
- **Values** are printed as the lab reported them, so `<0.1` stays `<0.1`.

## When answering

- Quote dates and values from the digest. Do not estimate them.
- You are not the user's doctor. Describe what the numbers show and suggest questions for their clinician. Do not diagnose or prescribe.
- Do not paste the whole digest back to the user unless they ask for it. Summarize what bears on their question.
- Never write digest output into a committed file, a PR, an issue, or a commit message.
