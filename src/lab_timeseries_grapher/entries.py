"""Manual measurement entry, appended to the source labs CSV.

Entries are written into the same file the lab export lives in, so there is
one source of truth. Two consequences are handled here:

- The write is atomic (temp file in the same directory, then replace), so an
  interrupted save cannot leave a truncated 374-row file behind.
- A new row inherits its metadata — units, reference range, panel — from that
  metric's most recent existing row, so the point lands in the same band the
  chart already draws, and `Notes` records that it was entered by hand.
"""

from __future__ import annotations

import csv
import logging
import os
import tempfile
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from .data import MetricSeries

logger = logging.getLogger("lab_timeseries_grapher")

NOTE_PREFIX = "Manually entered"
# Appended only when the entered range differs from what the row inherited,
# so an untouched pre-filled range never masquerades as a deliberate override.
CUSTOM_RANGE_NOTE = "custom range"


class EntryError(ValueError):
    """Raised with a message safe to show in the UI."""


def parse_date(value: str | date | None) -> pd.Timestamp:
    if value in (None, ""):
        raise EntryError("Pick a date for the measurement.")
    try:
        return pd.Timestamp(value).normalize()
    except Exception as exc:
        raise EntryError(f"Could not read {value!r} as a date.") from exc


def parse_value(value: str | float | None) -> float:
    if value in (None, ""):
        raise EntryError("Enter a value.")
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError) as exc:
        raise EntryError(f"{value!r} is not a number.") from exc


def validate_entry(
    metrics: dict[str, MetricSeries],
    name: str | None,
    when: str | date | None,
    value: str | float | None,
) -> tuple[str, pd.Timestamp, float]:
    """Check an entry, returning the cleaned parts or raising EntryError."""
    if not name:
        raise EntryError("Select exactly one metric first.")
    series = metrics.get(name)
    if series is None:
        raise EntryError(f"{name!r} is not a known metric.")

    when = parse_date(when)
    number = parse_value(value)

    if any(d.normalize() == when for d in series.dates):
        raise EntryError(
            f"{name} already has a result for {when:%Y-%m-%d}. "
            "Pick another date, or edit the CSV directly to change it."
        )
    return name, when, number


def format_value(number: float, units: str) -> str:
    return f"{number:g} {units}".strip()


def build_row(
    header: list[str],
    template: dict[str, str],
    *,
    name: str,
    when: pd.Timestamp,
    number: float,
    entered_on: datetime,
    custom_range: bool = False,
) -> list[str]:
    """A CSV row inheriting the metric's metadata from an existing row."""
    row = dict(template)
    row["Date"] = f"{when:%Y-%m-%d}"
    row["Test Name"] = name
    row["Value"] = format_value(number, template.get("Units", ""))
    row["Value_Numeric"] = f"{number:g}"
    note = f"{NOTE_PREFIX} {entered_on:%Y-%m-%d}"
    row["Notes"] = f"{note} · {CUSTOM_RANGE_NOTE}" if custom_range else note
    if "Value_Prefix" in row:
        row["Value_Prefix"] = "n/a"
    return [row.get(col, "") for col in header]


def parse_bound(value: str | float | None) -> float | None:
    """A reference bound, or None when the field was left empty."""
    if value in (None, ""):
        return None
    return parse_value(value)


def append_measurement(
    csv_path: Path,
    metrics: dict[str, MetricSeries],
    name: str,
    when: str | date | None,
    value: str | float | None,
    *,
    units: str | None = None,
    range_low: str | float | None = None,
    range_high: str | float | None = None,
    now: datetime | None = None,
) -> pd.Timestamp:
    """Validate and append one measurement. Returns the stored date.

    `units` and the range bounds come from the dialog pre-filled with the
    reference for this metric, so a lab reporting a different interval can be
    recorded as it actually was rather than inheriting a stale one.
    """
    name, when, number = validate_entry(metrics, name, when, value)

    with csv_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    if not rows:
        raise EntryError("The labs CSV is empty.")
    header = rows[0]
    idx = {col: i for i, col in enumerate(header)}
    if "Test Name" not in idx or "Date" not in idx:
        raise EntryError("The labs CSV is missing its Date or Test Name column.")

    matching = [r for r in rows[1:] if len(r) == len(header) and r[idx["Test Name"]] == name]
    if not matching:
        raise EntryError(f"No existing rows for {name!r} to take units and range from.")

    # Authoritative duplicate check, against the file rather than the caller's
    # metrics. validate_entry only sees rows that survived parsing, and it sees
    # whatever snapshot the caller happens to hold; neither is a guarantee.
    # This read is the same one that finds the template, so it costs nothing.
    for existing in matching:
        stamp = pd.to_datetime(existing[idx["Date"]], errors="coerce")
        if pd.notna(stamp) and stamp.normalize() == when:
            raise EntryError(
                f"{name} already has a result for {when:%Y-%m-%d}. "
                "Pick another date, or edit the CSV directly to change it."
            )

    low, high = parse_bound(range_low), parse_bound(range_high)
    if low is not None and high is not None and low >= high:
        raise EntryError(f"The range low ({low:g}) must be below the high ({high:g}).")

    template = dict(zip(header, matching[-1]))
    inherited = (template.get("Range_Low", ""), template.get("Range_High", ""))
    if units:
        template["Units"] = units.strip()
    if low is not None:
        template["Range_Low"] = f"{low:g}"
    if high is not None:
        template["Range_High"] = f"{high:g}"
    custom = (low is not None or high is not None) and (
        (template.get("Range_Low", ""), template.get("Range_High", "")) != inherited
    )
    if low is not None or high is not None:
        template["Typical range"] = (
            f"{low:g} - {high:g} {template.get('Units', '')}".strip()
            if low is not None and high is not None
            else template.get("Typical range", "")
        )

    rows.append(
        build_row(
            header, template, name=name, when=when, number=number,
            entered_on=now or datetime.now(),
            custom_range=custom,
        )
    )

    # Atomic replace: a partial write must never land on the lab export.
    fd, tmp = tempfile.mkstemp(dir=str(csv_path.parent), suffix=".csv")
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerows(rows)
        os.replace(tmp, csv_path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise

    logger.info("Appended manual entry: %s = %g on %s", name, number, f"{when:%Y-%m-%d}")
    return when
