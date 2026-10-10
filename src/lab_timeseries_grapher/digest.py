"""A plain-text digest of the labs CSV, shaped for an LLM to read.

The raw CSV spends tokens on boilerplate Notes, repeated units and ranges, and
retired spellings of the same test. The digest reads the file through the same
`prepare_tests` the dashboard uses, so a value, its band and its flag here are
the ones the charts show — an agent never re-derives a verdict on its own.
"""

from __future__ import annotations

import argparse
import logging
import sys

import pandas as pd

from .data import (
    RECENT_MONTHS,
    STATUS_HIGH,
    STATUS_LOW,
    MetricSeries,
    data_csvs,
    is_current,
    load_dataframe,
    newest_draw,
    out_of_range_now,
    prepare_tests,
    resolve_csv_path,
    validate_schema,
)
from .reference_ranges import Profile
from .synonyms import synonyms_for

FLAG = {STATUS_LOW: "▼ LOW", STATUS_HIGH: "▲ HIGH"}


def band_text(series: MetricSeries) -> str:
    """The range a metric is judged against, and where it came from."""
    if series.band is None:
        return "no range"
    low, high = series.band
    source = "lab" if series.lab_band else "reference"
    return f"{low:g}–{high:g} ({source})"


def match_metrics(metrics: dict[str, MetricSeries], query: str) -> list[str]:
    """Metric names matching a query by name or known synonym, case-insensitively.

    An exact name wins outright, so asking for "HDL" does not also pull in
    "Non-HDL Cholesterol".
    """
    q = query.strip().casefold()
    exact = [n for n in metrics if n.casefold() == q]
    if exact:
        return exact
    return sorted(
        n
        for n in metrics
        if q in n.casefold() or any(q == s.casefold() for s in synonyms_for(n))
    )


def overview(metrics: dict[str, MetricSeries], profile: Profile, source: str) -> str:
    """One line per metric, grouped by panel, plus what is out of range now."""
    newest = newest_draw(metrics)
    flagged = out_of_range_now(metrics)
    lines = [
        "# Blood metrics overview",
        "",
        f"- Source: {source}",
        f"- Reference profile: {profile.sex}, age {profile.age}",
        f"- Metrics: {len(metrics)}; newest draw: {newest:%Y-%m-%d}" if newest else "- No draws",
        f"- Current = measured within {RECENT_MONTHS} months of the newest draw",
        "",
        "## Out of range now",
        "",
    ]
    if flagged:
        for name in flagged:
            m = metrics[name]
            lines.append(
                f"- {name}: {m.latest_display} {m.units} on {m.last_date:%Y-%m-%d} "
                f"{FLAG[m.latest_status]} (range {band_text(m)})"
            )
    else:
        lines.append("- None")

    lines += [
        "",
        "## All metrics",
        "",
        "Columns: name | latest (date) | previous | range | flag | points | current",
    ]
    by_panel: dict[str, list[MetricSeries]] = {}
    for m in metrics.values():
        by_panel.setdefault(m.panel or "Other", []).append(m)
    for panel in sorted(by_panel):
        lines += ["", f"### {panel}", ""]
        for m in sorted(by_panel[panel], key=lambda s: s.name.casefold()):
            prev = m.display_values[-2] if len(m.values) > 1 else "—"
            flag = FLAG.get(m.latest_status, "")
            current = "yes" if is_current(m, newest) else "no"
            lines.append(
                f"- {m.name} | {m.latest_display} {m.units} ({m.last_date:%Y-%m-%d}) | "
                f"{prev} | {band_text(m)} | {flag or 'ok'} | {len(m.values)} | {current}"
            )
    return "\n".join(lines)


def history(series: MetricSeries, cutoff: pd.Timestamp | None = None) -> str:
    """Every measurement of one metric, oldest first, with its flag."""
    lines = [f"## {series.name}", ""]
    if series.description:
        lines.append(f"- About: {series.description}")
    aliases = synonyms_for(series.name)
    if aliases:
        lines.append(f"- Also known as: {', '.join(aliases)}")
    if series.panel:
        lines.append(f"- Panel: {series.panel}")
    lines.append(f"- Units: {series.units or 'not stated'}")
    lines.append(f"- Range: {band_text(series)}")
    if series.reference and series.lab_band:
        ref = series.reference
        if ref.band:
            lines.append(f"- Population reference: {ref.low:g}–{ref.high:g} ({ref.source})")

    points = [i for i, d in enumerate(series.dates) if cutoff is None or d >= cutoff]
    if not points:
        lines.append("- Measurements: none in the window")
        return "\n".join(lines)
    lines += ["", "| Date | Value | Flag |", "|---|---|---|"]
    for i in points:
        flag = FLAG.get(series.status_of(series.values[i]), "")
        lines.append(f"| {series.dates[i]:%Y-%m-%d} | {series.display_values[i]} | {flag} |")
    return "\n".join(lines)


def build_digest(
    metrics: dict[str, MetricSeries],
    profile: Profile,
    source: str,
    queries: list[str] | None = None,
    panel: str | None = None,
    out_of_range: bool = False,
    since: pd.Timestamp | None = None,
) -> str:
    """The overview when nothing narrows it, else full histories for the chosen metrics."""
    names: list[str] = []
    missing: list[str] = []
    for q in queries or []:
        found = match_metrics(metrics, q)
        names += [n for n in found if n not in names]
        if not found:
            missing.append(q)
    if panel:
        names += [
            n for n, m in metrics.items()
            if m.panel.casefold() == panel.casefold() and n not in names
        ]
    if out_of_range:
        names += [n for n in out_of_range_now(metrics) if n not in names]

    if not (queries or panel or out_of_range):
        return overview(metrics, profile, source)

    if since is not None:
        stale = [n for n in names if metrics[n].last_date < since]
        names = [n for n in names if n not in stale]
    else:
        stale = []
    blocks = [history(metrics[n], since) for n in names]
    if stale:
        blocks.append(f"Not measured since {since:%Y-%m-%d}: {', '.join(stale)}.")
    if missing:
        blocks.append(
            f"No metric matched: {', '.join(missing)}. Run with --list to see every name."
        )
    if not blocks:
        blocks.append("Nothing matched.")
    return "\n\n".join(blocks)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        description="Print the labs CSV as a compact markdown digest for an LLM to read"
    )
    ap.add_argument("--csv", default="labs_results.csv", help="CSV filename or path to load")
    ap.add_argument(
        "--metric", "-m", action="append",
        help="Full history for metrics matching this name or synonym (repeatable)",
    )
    ap.add_argument("--panel", help="Full history for every metric in this panel")
    ap.add_argument(
        "--out-of-range", action="store_true",
        help="Full history for every metric out of range now",
    )
    ap.add_argument("--since", help="Only measurements on or after this date (YYYY-MM-DD)")
    ap.add_argument("--list", action="store_true", help="Print metric names and panels only")
    ap.add_argument("--age", type=int, default=60, help="Age for reference ranges (default 60)")
    ap.add_argument(
        "--sex", choices=["male", "female"], default="male",
        help="Sex for reference ranges (default male)",
    )
    args = ap.parse_args(argv)

    # Keep stdout to the digest alone; loader chatter would cost tokens.
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)

    csv_path = resolve_csv_path(args.csv)
    if not csv_path.exists():
        names = ", ".join(p.name for p in data_csvs()) or "none"
        raise SystemExit(f"CSV not found at {csv_path}. CSVs in /data: {names}")

    profile = Profile(age=args.age, sex=args.sex)
    df = load_dataframe(csv_path)
    validate_schema(df)
    metrics = prepare_tests(df, profile)
    if not metrics:
        raise SystemExit("No plottable rows were found in the CSV.")

    if args.list:
        for name, m in sorted(metrics.items(), key=lambda kv: (kv[1].panel, kv[0].casefold())):
            print(f"{m.panel or 'Other'} | {name}")
        return

    since = pd.Timestamp(args.since) if args.since else None
    print(
        build_digest(
            metrics, profile, csv_path.name,
            queries=args.metric, panel=args.panel,
            out_of_range=args.out_of_range, since=since,
        )
    )


if __name__ == "__main__":
    main()
