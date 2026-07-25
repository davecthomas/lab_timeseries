import pandas as pd
import pytest

from lab_timeseries_grapher import data
from lab_timeseries_grapher.data import (
    STATUS_HIGH,
    STATUS_IN,
    STATUS_LOW,
    STATUS_UNKNOWN,
    MetricSeries,
    coerce_float,
    mode_str,
    most_common_range,
    prepare_tests,
    resolve_csv_path,
    validate_schema,
)


class TestCoerceFloat:
    def test_plain_number(self):
        assert coerce_float("5.4") == 5.4

    def test_thousands_separator(self):
        assert coerce_float("3,457") == 3457.0

    @pytest.mark.parametrize("value", ["n/a", "NA", "nan", "", None, "abc", "<0.1"])
    def test_unparseable(self, value):
        assert coerce_float(value) is None


class TestMostCommonRange:
    def test_mode_wins(self):
        low = pd.Series(["1", "1", "2"])
        high = pd.Series(["9", "9", "8"])
        assert most_common_range(low, high) == (1.0, 9.0)

    def test_single_pair(self):
        assert most_common_range(pd.Series(["3"]), pd.Series(["7"])) == (3.0, 7.0)

    def test_median_fallback_without_mode(self):
        low = pd.Series(["1", "2", "3"])
        high = pd.Series(["7", "8", "9"])
        assert most_common_range(low, high) == (2.0, 8.0)

    def test_none_when_no_numeric_pairs(self):
        assert most_common_range(pd.Series(["n/a"]), pd.Series(["n/a"])) is None


class TestModeStr:
    def test_most_common(self):
        assert mode_str(pd.Series(["mg/dL", "mg/dL", "g/L"])) == "mg/dL"

    def test_ignores_placeholders(self):
        assert mode_str(pd.Series(["n/a", "", "K/uL"])) == "K/uL"

    def test_empty(self):
        assert mode_str(pd.Series(["n/a", ""])) == ""


def make_series(values, band=(2.0, 8.0)):
    dates = pd.date_range("2024-01-01", periods=len(values), freq="MS")
    return MetricSeries(
        name="Test",
        dates=list(dates),
        values=values,
        display_values=[str(v) for v in values],
        band=band,
        units="u",
        panel="Panel A",
    )


class TestMetricSeries:
    def test_statuses(self):
        s = make_series([1.0, 5.0, 9.0])
        assert s.point_statuses() == [STATUS_LOW, STATUS_IN, STATUS_HIGH]
        assert s.latest_status == STATUS_HIGH

    def test_unknown_without_band(self):
        s = make_series([5.0], band=None)
        assert s.latest_status == STATUS_UNKNOWN

    def test_latest_accessors(self):
        s = make_series([1.0, 2.5])
        assert s.latest_value == 2.5
        assert s.latest_display == "2.5"
        assert s.last_date == s.dates[-1]


def labs_frame(rows):
    return pd.DataFrame(
        rows,
        columns=[
            "Date",
            "Test Name",
            "Value",
            "Value_Numeric",
            "Units",
            "Range_Low",
            "Range_High",
            "Panel",
        ],
    )


class TestPrepareTests:
    def test_basic_series(self):
        df = labs_frame(
            [
                ["2024-01-01", "Glucose", "90", "90", "mg/dL", "70", "100", "CMP"],
                ["2024-06-01", "Glucose", "105", "105", "mg/dL", "70", "100", "CMP"],
            ]
        )
        metrics = prepare_tests(df)
        glucose = metrics["Glucose"]
        assert glucose.values == [90.0, 105.0]
        assert glucose.band == (70.0, 100.0)
        assert glucose.panel == "CMP"
        assert glucose.latest_status == STATUS_HIGH

    def test_skips_unparseable_rows(self):
        df = labs_frame(
            [
                ["bad-date", "Glucose", "90", "90", "mg/dL", "70", "100", "CMP"],
                ["2024-06-01", "Glucose", "95", "95", "mg/dL", "70", "100", "CMP"],
                ["2024-06-01", "Mystery", "x", "n/a", "", "n/a", "n/a", ""],
            ]
        )
        metrics = prepare_tests(df)
        assert list(metrics) == ["Glucose"]
        assert len(metrics["Glucose"].values) == 1

    def test_display_keeps_original_string(self):
        df = labs_frame(
            [["2024-01-01", "TSH", "<0.1", "0.1", "mIU/L", "0.4", "4.5", "Thyroid"]]
        )
        metrics = prepare_tests(df)
        assert metrics["TSH"].display_values == ["<0.1"]
        assert metrics["TSH"].latest_status == STATUS_LOW

    def test_works_without_optional_columns(self):
        df = labs_frame([["2024-01-01", "Glucose", "90", "90", "mg/dL", "70", "100", "CMP"]])
        df = df.drop(columns=["Value", "Panel"])
        metrics = prepare_tests(df)
        assert metrics["Glucose"].panel == ""
        assert metrics["Glucose"].display_values == ["90"]


class TestResolveCsvPath:
    def test_named_file_in_data_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(data, "data_dir", lambda: tmp_path)
        (tmp_path / "labs_results.csv").write_text("Date\n")
        assert resolve_csv_path("labs_results.csv") == tmp_path / "labs_results.csv"

    def test_falls_back_to_only_csv(self, tmp_path, monkeypatch):
        monkeypatch.setattr(data, "data_dir", lambda: tmp_path)
        (tmp_path / "my_labs.csv").write_text("Date\n")
        assert resolve_csv_path("labs_results.csv") == tmp_path / "my_labs.csv"

    def test_no_fallback_with_multiple_csvs(self, tmp_path, monkeypatch):
        monkeypatch.setattr(data, "data_dir", lambda: tmp_path)
        (tmp_path / "a.csv").write_text("Date\n")
        (tmp_path / "b.csv").write_text("Date\n")
        assert resolve_csv_path("labs_results.csv") == tmp_path / "labs_results.csv"

    def test_absolute_path(self, tmp_path):
        target = tmp_path / "abs.csv"
        target.write_text("Date\n")
        assert resolve_csv_path(str(target)) == target


class TestValidateSchema:
    def test_passes_with_required_columns(self):
        validate_schema(labs_frame([]))

    def test_exits_on_missing_columns(self):
        with pytest.raises(SystemExit, match="Range_High"):
            validate_schema(pd.DataFrame(columns=["Date", "Test Name"]))
