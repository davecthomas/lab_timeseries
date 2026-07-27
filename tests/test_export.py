import csv
import io
from datetime import datetime

import pandas as pd

from lab_timeseries_grapher.data import MetricSeries
from lab_timeseries_grapher.export import COLUMNS, csv_filename, metric_rows, metrics_csv


def make_metric(name="ALT", values=(23.0, 60.0), band=(0.0, 50.0), panel="CMP", units="U/L"):
    dates = pd.date_range("2021-01-01", periods=len(values), freq="YS")
    return MetricSeries(
        name=name,
        dates=list(dates),
        values=list(values),
        display_values=[f"{v:g} {units}" for v in values],
        band=band,
        units=units,
        panel=panel,
    )


def parse(text):
    return list(csv.DictReader(io.StringIO(text)))


class TestMetricRows:
    def test_one_row_per_measurement_oldest_first(self):
        rows = metric_rows({"ALT": make_metric()}, ["ALT"])
        assert [r["Date"] for r in rows] == ["2021-01-01", "2022-01-01"]

    def test_carries_range_and_status(self):
        rows = metric_rows({"ALT": make_metric()}, ["ALT"])
        assert rows[0]["Range_Low"] == "0" and rows[0]["Range_High"] == "50"
        assert rows[0]["Status"] == "in"
        assert rows[1]["Status"] == "high"

    def test_missing_band_leaves_range_and_status_blank(self):
        rows = metric_rows({"ALT": make_metric(band=None)}, ["ALT"])
        assert rows[0]["Range_Low"] == ""
        assert rows[0]["Range_High"] == ""
        assert rows[0]["Status"] == ""

    def test_follows_the_given_metric_order(self):
        metrics = {"ALT": make_metric("ALT"), "AST": make_metric("AST")}
        rows = metric_rows(metrics, ["AST", "ALT"])
        assert [r["Test Name"] for r in rows][:2] == ["AST", "AST"]

    def test_unknown_names_are_skipped(self):
        rows = metric_rows({"ALT": make_metric()}, ["ALT", "Nope"])
        assert {r["Test Name"] for r in rows} == {"ALT"}

    def test_window_cutoff_limits_rows(self):
        rows = metric_rows({"ALT": make_metric()}, ["ALT"], cutoff=pd.Timestamp("2021-06-01"))
        assert [r["Date"] for r in rows] == ["2022-01-01"]

    def test_whole_numbers_render_without_trailing_zero(self):
        rows = metric_rows({"ALT": make_metric(values=(23.0,))}, ["ALT"])
        assert rows[0]["Value_Numeric"] == "23"

    def test_empty_selection_yields_no_rows(self):
        assert metric_rows({"ALT": make_metric()}, []) == []


class TestMetricsCsv:
    def test_header_matches_declared_columns(self):
        text = metrics_csv({"ALT": make_metric()}, ["ALT"])
        assert text.splitlines()[0] == ",".join(COLUMNS)

    def test_round_trips_through_a_csv_reader(self):
        rows = parse(metrics_csv({"ALT": make_metric()}, ["ALT"]))
        assert len(rows) == 2
        assert rows[0]["Test Name"] == "ALT"
        assert rows[0]["Units"] == "U/L"

    def test_names_containing_commas_are_quoted(self):
        metric = make_metric(name="Neutrophils, Absolute Count")
        rows = parse(metrics_csv({metric.name: metric}, [metric.name]))
        assert rows[0]["Test Name"] == "Neutrophils, Absolute Count"

    def test_empty_selection_still_emits_a_header(self):
        text = metrics_csv({"ALT": make_metric()}, [])
        assert text.strip() == ",".join(COLUMNS)


class TestFilename:
    def test_stamped_with_the_export_date(self):
        assert csv_filename(datetime(2026, 7, 27, 9, 5)) == "blood-metrics-2026-07-27.csv"

    def test_date_only_so_repeat_exports_that_day_match(self):
        morning = csv_filename(datetime(2026, 7, 27, 1, 0))
        evening = csv_filename(datetime(2026, 7, 27, 23, 59))
        assert morning == evening
