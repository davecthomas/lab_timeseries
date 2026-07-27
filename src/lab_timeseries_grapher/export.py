"""CSV export of the metric data currently in view.

Exports the app's own view of the data — one row per measurement, with the
reference range and in/out-of-range status resolved — rather than a copy of
the source file, so the download matches what the charts show.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime

import pandas as pd

from .data import STATUS_UNKNOWN, MetricSeries
from .figures import filter_window

COLUMNS = [
    "Date",
    "Test Name",
    "Panel",
    "Value",
    "Value_Numeric",
    "Units",
    "Range_Low",
    "Range_High",
    "Status",
]


def _num(value: float) -> str:
    """Render a float without a trailing .0 on whole numbers."""
    return f"{value:g}"


def metric_rows(
    metrics: dict[str, MetricSeries],
    selected: list[str],
    cutoff: pd.Timestamp | None = None,
) -> list[dict]:
    """One row per measurement, in the given metric order, oldest first."""
    rows: list[dict] = []
    for name in selected:
        series = metrics.get(name)
        if series is None:
            continue
        low, high = series.band if series.band else ("", "")
        for i in filter_window(series, cutoff):
            status = series.status_of(series.values[i])
            rows.append(
                {
                    "Date": series.dates[i].strftime("%Y-%m-%d"),
                    "Test Name": series.name,
                    "Panel": series.panel,
                    "Value": series.display_values[i],
                    "Value_Numeric": _num(series.values[i]),
                    "Units": series.units,
                    "Range_Low": _num(low) if low != "" else "",
                    "Range_High": _num(high) if high != "" else "",
                    "Status": "" if status == STATUS_UNKNOWN else status,
                }
            )
    return rows


def metrics_csv(
    metrics: dict[str, MetricSeries],
    selected: list[str],
    cutoff: pd.Timestamp | None = None,
) -> str:
    """Render the selected metrics as CSV text."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(metric_rows(metrics, selected, cutoff))
    return buf.getvalue()


def csv_filename(now: datetime) -> str:
    """Download name, stamped with the export date."""
    return f"blood-metrics-{now:%Y-%m-%d}.csv"
