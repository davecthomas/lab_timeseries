"""Mutable app data, so a manual entry can be reflected without a restart."""

from __future__ import annotations

from pathlib import Path

from .data import MetricSeries, load_dataframe, prepare_tests, validate_schema


class AppData:
    """The prepared metrics and sidebar rows, re-readable from the CSV."""

    def __init__(self, csv_path: Path | None, metrics: dict[str, MetricSeries], profile=None):
        self.csv_path = csv_path
        self.profile = profile
        self._set(metrics)

    def _set(self, metrics: dict[str, MetricSeries]) -> None:
        from .layout import build_table_rows

        self.metrics = metrics
        self.table_rows = build_table_rows(metrics)

    @classmethod
    def from_csv(cls, csv_path: Path, profile=None) -> AppData:
        df = load_dataframe(csv_path)
        validate_schema(df)
        return cls(csv_path, prepare_tests(df, profile), profile)

    @classmethod
    def from_metrics(cls, metrics: dict[str, MetricSeries]) -> AppData:
        """For tests and callers that already hold prepared metrics."""
        return cls(None, metrics)

    def reload(self) -> None:
        """Re-read the CSV. No-op when there is no file behind this data."""
        if self.csv_path is None:
            return
        df = load_dataframe(self.csv_path)
        validate_schema(df)
        self._set(prepare_tests(df, self.profile))
