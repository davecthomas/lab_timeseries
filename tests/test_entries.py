import csv
from datetime import date, datetime

import pandas as pd
import pytest

from lab_timeseries_grapher.data import MetricSeries, load_dataframe, prepare_tests
from lab_timeseries_grapher.entries import (
    EntryError,
    append_measurement,
    format_value,
    parse_date,
    parse_value,
    validate_entry,
)

HEADER = [
    "Date", "Test Name", "Value", "Value_Prefix", "Value_Numeric", "Units",
    "Typical range", "Range_Low", "Range_High", "Fasting?", "Panel", "Notes",
    "Test Name (Original)",
]
ROWS = [
    ["2021-03-30", "ALT", "25 U/L", "n/a", "25", "U/L", "0 - 50 U/L", "0", "50",
     "No", "CMP", "lab note", "ALT"],
    ["2025-10-10", "ALT", "23 U/L", "n/a", "23", "U/L", "0 - 50 U/L", "0", "50",
     "No", "CMP", "lab note", "ALT"],
]
NOW = datetime(2026, 7, 28, 10, 0)


@pytest.fixture
def csv_path(tmp_path):
    p = tmp_path / "labs.csv"
    with p.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(HEADER)
        w.writerows(ROWS)
    return p


@pytest.fixture
def metrics(csv_path):
    return prepare_tests(load_dataframe(csv_path))


def read(path):
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class TestParsing:
    def test_parse_date_accepts_string_and_date(self):
        assert parse_date("2026-01-05") == pd.Timestamp("2026-01-05")
        assert parse_date(date(2026, 1, 5)) == pd.Timestamp("2026-01-05")

    def test_parse_date_rejects_blank_and_junk(self):
        with pytest.raises(EntryError, match="Pick a date"):
            parse_date("")
        with pytest.raises(EntryError, match="date"):
            parse_date("not-a-date")

    def test_parse_value_accepts_numbers_and_separators(self):
        assert parse_value("4.6") == 4.6
        assert parse_value("3,457") == 3457.0
        assert parse_value(12) == 12.0

    def test_parse_value_rejects_blank_and_text(self):
        with pytest.raises(EntryError, match="Enter a value"):
            parse_value("")
        with pytest.raises(EntryError, match="not a number"):
            parse_value("high")

    def test_format_value_pairs_number_with_units(self):
        assert format_value(4.6, "g/dL") == "4.6 g/dL"
        assert format_value(23.0, "U/L") == "23 U/L"
        assert format_value(5.0, "") == "5"


class TestValidateEntry:
    def test_accepts_a_new_date(self, metrics):
        name, when, number = validate_entry(metrics, "ALT", "2026-07-28", "31")
        assert (name, when, number) == ("ALT", pd.Timestamp("2026-07-28"), 31.0)

    def test_rejects_a_duplicate_date(self, metrics):
        with pytest.raises(EntryError, match="already has a result"):
            validate_entry(metrics, "ALT", "2025-10-10", "31")

    def test_rejects_an_unknown_metric(self, metrics):
        with pytest.raises(EntryError, match="not a known metric"):
            validate_entry(metrics, "Nope", "2026-07-28", "31")

    def test_rejects_no_metric(self, metrics):
        with pytest.raises(EntryError, match="exactly one metric"):
            validate_entry(metrics, None, "2026-07-28", "31")


class TestAppendMeasurement:
    def test_appends_one_row(self, csv_path, metrics):
        append_measurement(csv_path, metrics, "ALT", "2026-07-28", "31", now=NOW)
        rows = read(csv_path)
        assert len(rows) == len(ROWS) + 1
        assert rows[-1]["Date"] == "2026-07-28"
        assert rows[-1]["Value_Numeric"] == "31"

    def test_inherits_units_and_range_from_the_metric(self, csv_path, metrics):
        append_measurement(csv_path, metrics, "ALT", "2026-07-28", "31", now=NOW)
        new = read(csv_path)[-1]
        assert new["Units"] == "U/L"
        assert new["Range_Low"] == "0" and new["Range_High"] == "50"
        assert new["Panel"] == "CMP"

    def test_records_provenance_in_notes(self, csv_path, metrics):
        append_measurement(csv_path, metrics, "ALT", "2026-07-28", "31", now=NOW)
        assert read(csv_path)[-1]["Notes"] == "Manually entered 2026-07-28"

    def test_value_string_matches_the_lab_format(self, csv_path, metrics):
        append_measurement(csv_path, metrics, "ALT", "2026-07-28", "31", now=NOW)
        assert read(csv_path)[-1]["Value"] == "31 U/L"

    def test_existing_rows_are_untouched(self, csv_path, metrics):
        before = read(csv_path)
        append_measurement(csv_path, metrics, "ALT", "2026-07-28", "31", now=NOW)
        assert read(csv_path)[: len(before)] == before

    def test_the_app_picks_up_the_new_point(self, csv_path, metrics):
        append_measurement(csv_path, metrics, "ALT", "2026-07-28", "31", now=NOW)
        reloaded = prepare_tests(load_dataframe(csv_path))["ALT"]
        assert reloaded.values == [25.0, 23.0, 31.0]
        assert reloaded.latest_value == 31.0
        assert reloaded.band == (0.0, 50.0)
        assert reloaded.latest_status == "in"

    def test_out_of_range_entry_is_flagged(self, csv_path, metrics):
        append_measurement(csv_path, metrics, "ALT", "2026-07-28", "88", now=NOW)
        assert prepare_tests(load_dataframe(csv_path))["ALT"].latest_status == "high"

    def test_duplicate_date_leaves_the_file_alone(self, csv_path, metrics):
        before = csv_path.read_text()
        with pytest.raises(EntryError):
            append_measurement(csv_path, metrics, "ALT", "2025-10-10", "31", now=NOW)
        assert csv_path.read_text() == before

    def test_no_temp_files_left_behind(self, csv_path, metrics, tmp_path):
        append_measurement(csv_path, metrics, "ALT", "2026-07-28", "31", now=NOW)
        assert sorted(p.name for p in tmp_path.iterdir()) == ["labs.csv"]

    def test_metric_with_no_existing_rows_is_refused(self, csv_path, metrics):
        metrics = dict(metrics)
        metrics["Ghost"] = MetricSeries(
            name="Ghost", dates=[pd.Timestamp("2020-01-01")], values=[1.0],
            display_values=["1"], band=None, units="", panel="",
        )
        with pytest.raises(EntryError, match="No existing rows"):
            append_measurement(csv_path, metrics, "Ghost", "2026-07-28", "2", now=NOW)


class TestAppDataReload:
    """The 'update the graph' half: an entry must surface without a restart."""

    def test_reload_picks_up_an_appended_row(self, csv_path, metrics):
        from lab_timeseries_grapher.state import AppData

        data = AppData.from_csv(csv_path)
        assert data.metrics["ALT"].values == [25.0, 23.0]

        append_measurement(csv_path, data.metrics, "ALT", "2026-07-28", "31", now=NOW)
        data.reload()

        assert data.metrics["ALT"].values == [25.0, 23.0, 31.0]
        row = next(r for r in data.table_rows if r["id"] == "ALT")
        assert row["latest_display"] == "31 U/L"
        assert row["last_date_display"] == "07/26"

    def test_reload_without_a_path_is_a_no_op(self, metrics):
        from lab_timeseries_grapher.state import AppData

        data = AppData.from_metrics(metrics)
        data.reload()
        assert data.metrics["ALT"].values == [25.0, 23.0]


class TestDuplicateGuarantee:
    """The check must not depend on the caller holding fresh metrics, nor on
    the conflicting row having survived parsing."""

    def test_repeat_save_without_reloading_metrics_is_refused(self, csv_path, metrics):
        # The UI reloads after each save; the guarantee must not rely on it.
        append_measurement(csv_path, metrics, "ALT", "2026-02-05", "31", now=NOW)
        with pytest.raises(EntryError, match="already has a result"):
            append_measurement(csv_path, metrics, "ALT", "2026-02-05", "99", now=NOW)
        dates = [r["Date"] for r in read(csv_path) if r["Test Name"] == "ALT"]
        assert dates.count("2026-02-05") == 1

    def test_conflicting_row_invisible_to_the_parser_is_still_refused(self, csv_path, metrics):
        # A row whose value will not parse is dropped by prepare_tests, so the
        # in-memory series cannot see the clash.
        with csv_path.open("a", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerow(
                ["2024-05-05", "ALT", "pending", "n/a", "n/a", "U/L", "0 - 50 U/L",
                 "0", "50", "No", "CMP", "lab note", "ALT"]
            )
        metrics = prepare_tests(load_dataframe(csv_path))
        assert pd.Timestamp("2024-05-05") not in metrics["ALT"].dates

        with pytest.raises(EntryError, match="already has a result"):
            append_measurement(csv_path, metrics, "ALT", "2024-05-05", "31", now=NOW)
        dates = [r["Date"] for r in read(csv_path) if r["Test Name"] == "ALT"]
        assert dates.count("2024-05-05") == 1

    def test_time_component_still_collides_with_the_same_day(self, csv_path, metrics):
        with pytest.raises(EntryError, match="already has a result"):
            append_measurement(csv_path, metrics, "ALT", "2025-10-10T14:30:00", "31", now=NOW)

    def test_same_date_on_a_different_metric_is_allowed(self, csv_path, metrics):
        with csv_path.open("a", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerow(
                ["2025-10-10", "AST", "30 U/L", "n/a", "30", "U/L", "5 - 45 U/L",
                 "5", "45", "No", "CMP", "lab note", "AST"]
            )
        metrics = prepare_tests(load_dataframe(csv_path))
        append_measurement(csv_path, metrics, "AST", "2026-06-06", "33", now=NOW)
        assert any(
            r["Test Name"] == "AST" and r["Date"] == "2026-06-06" for r in read(csv_path)
        )
