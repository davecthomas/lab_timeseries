import csv

import pytest

from lab_timeseries_grapher.data import load_dataframe, prepare_tests
from lab_timeseries_grapher.ingest import (
    IngestError,
    build_plan,
    commit_plan,
    infer_columns,
    read_uploaded,
    split_range,
)

HEADER = [
    "Date", "Test Name", "Value", "Value_Prefix", "Value_Numeric", "Units",
    "Typical range", "Range_Low", "Range_High", "Fasting?", "Panel", "Notes",
    "Test Name (Original)",
]
ROWS = [
    ["2025-10-10", "ALT", "23 U/L", "n/a", "23", "U/L", "0 - 50 U/L", "0", "50",
     "No", "CMP", "lab note", "ALT"],
    ["2025-10-10", "AST", "24 U/L", "n/a", "24", "U/L", "5 - 45 U/L", "5", "45",
     "No", "CMP", "lab note", "AST"],
]


@pytest.fixture
def csv_path(tmp_path):
    p = tmp_path / "labs.csv"
    with p.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(HEADER)
        w.writerows(ROWS)
    return p


def upload(text):
    return read_uploaded(text.encode())


def read(path):
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class TestInference:
    def test_matches_this_apps_own_export(self):
        df = upload("Date,Test Name,Value,Units,Range_Low,Range_High\n2026-01-01,ALT,25,U/L,0,50\n")
        m = infer_columns(df)
        assert (m["Date"], m["Test Name"], m["Value"]) == ("Date", "Test Name", "Value")

    def test_matches_a_foreign_export_by_header(self):
        df = upload("Collected,Analyte,Result,UOM\n2026-01-01,ALT,25,U/L\n")
        m = infer_columns(df)
        assert m["Date"] == "Collected"
        assert m["Test Name"] == "Analyte"
        assert m["Value"] == "Result"
        assert m["Units"] == "UOM"

    def test_falls_back_to_content_when_headers_are_opaque(self):
        df = upload(
            "a,b,c\n"
            "2026-01-01,Glucose,92\n"
            "2026-01-01,Sodium,140\n"
            "2026-02-01,Potassium,4.2\n"
        )
        m = infer_columns(df)
        assert m["Date"] == "a"
        assert m["Test Name"] == "b"
        assert m["Value"] == "c"

    def test_reference_range_column_is_found(self):
        df = upload("Date,Test,Result,Reference Range\n2026-01-01,ALT,25,0 - 50\n")
        assert "Typical range" in infer_columns(df)

    def test_unusable_file_is_refused(self):
        with pytest.raises(IngestError, match="Could not work out"):
            infer_columns(upload("foo,bar\nlorem,ipsum\n"))


class TestSplitRange:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("0.8 - 1.9 ng/dL", (0.8, 1.9)),
            ("0.8–1.9", (0.8, 1.9)),
            ("70 to 100", (70.0, 100.0)),
            ("", (None, None)),
            ("n/a", (None, None)),
            ("negative", (None, None)),
        ],
    )
    def test_parsing(self, text, expected):
        assert split_range(text) == expected


class TestMerge:
    """Same test on the same day: the uploaded value wins."""

    def test_new_result_is_added(self, csv_path):
        plan = build_plan(csv_path, upload("Date,Test Name,Value\n2026-03-01,ALT,31\n"))
        assert len(plan.added) == 1
        assert plan.replaced == []

    def test_same_test_same_day_replaces(self, csv_path):
        plan = build_plan(csv_path, upload("Date,Test Name,Value\n2025-10-10,ALT,99\n"))
        assert plan.added == []
        assert len(plan.replaced) == 1
        assert plan.replaced[0].replaced == "23 U/L"

    def test_replacement_wins_in_the_written_file(self, csv_path):
        plan = build_plan(csv_path, upload("Date,Test Name,Value\n2025-10-10,ALT,99\n"))
        commit_plan(csv_path, plan)
        rows = [r for r in read(csv_path) if r["Test Name"] == "ALT"]
        assert len(rows) == 1
        assert rows[0]["Value_Numeric"] == "99"

    def test_same_day_different_test_is_not_a_collision(self, csv_path):
        plan = build_plan(csv_path, upload("Date,Test Name,Value\n2025-10-10,Glucose,92\n"))
        assert len(plan.added) == 1

    def test_date_formats_still_collide(self, csv_path):
        plan = build_plan(csv_path, upload("Date,Test Name,Value\n10/10/2025,ALT,99\n"))
        assert len(plan.replaced) == 1

    def test_repeated_rows_within_one_upload_keep_the_last(self, csv_path):
        plan = build_plan(
            csv_path,
            upload("Date,Test Name,Value\n2026-03-01,ALT,10\n2026-03-01,ALT,20\n"),
        )
        commit_plan(csv_path, plan)
        rows = [r for r in read(csv_path) if r["Test Name"] == "ALT" and r["Date"] == "2026-03-01"]
        assert len(rows) == 1
        assert rows[0]["Value_Numeric"] == "20"

    def test_unusable_rows_are_counted_not_written(self, csv_path):
        plan = build_plan(
            csv_path,
            upload("Date,Test Name,Value\n2026-03-01,ALT,pending\nbad-date,AST,20\n,,\n"),
        )
        assert plan.skipped == 3
        assert plan.total == 0

    def test_untouched_rows_survive(self, csv_path):
        before = read(csv_path)
        plan = build_plan(csv_path, upload("Date,Test Name,Value\n2026-03-01,ALT,31\n"))
        commit_plan(csv_path, plan)
        after = read(csv_path)
        assert after[: len(before)] == before


class TestMetadata:
    def test_units_and_range_come_from_the_upload(self, csv_path):
        plan = build_plan(
            csv_path,
            upload("Date,Test Name,Value,Units,Range_Low,Range_High\n"
                   "2026-03-01,ALT,31,IU/L,2,40\n"),
        )
        commit_plan(csv_path, plan)
        row = read(csv_path)[-1]
        assert (row["Units"], row["Range_Low"], row["Range_High"]) == ("IU/L", "2", "40")

    def test_reference_range_text_is_split(self, csv_path):
        plan = build_plan(
            csv_path,
            upload("Date,Test Name,Value,Reference Range\n2026-03-01,ALT,31,2 - 40\n"),
        )
        commit_plan(csv_path, plan)
        row = read(csv_path)[-1]
        assert (row["Range_Low"], row["Range_High"]) == ("2", "40")

    def test_metadata_is_inherited_for_a_known_test(self, csv_path):
        plan = build_plan(csv_path, upload("Date,Test Name,Value\n2026-03-01,ALT,31\n"))
        commit_plan(csv_path, plan)
        row = read(csv_path)[-1]
        assert row["Units"] == "U/L"
        assert row["Panel"] == "CMP"

    def test_a_brand_new_test_is_accepted(self, csv_path):
        plan = build_plan(
            csv_path,
            upload("Date,Test Name,Value,Units\n2026-03-01,Ferritin,82,ng/mL\n"),
        )
        commit_plan(csv_path, plan)
        metrics = prepare_tests(load_dataframe(csv_path))
        assert metrics["Ferritin"].values == [82.0]
        assert metrics["Ferritin"].units == "ng/mL"


class TestReadUploaded:
    def test_handles_a_utf8_bom(self):
        df = read_uploaded("﻿Date,Test Name,Value\n2026-01-01,ALT,25\n".encode())
        assert list(df.columns)[0] == "Date"

    def test_empty_file_is_refused(self):
        with pytest.raises(IngestError):
            read_uploaded(b"")

    def test_header_only_is_refused(self):
        with pytest.raises(IngestError, match="no rows"):
            read_uploaded(b"Date,Test Name,Value\n")


class TestAtomicity:
    def test_no_temp_files_left_behind(self, csv_path, tmp_path):
        plan = build_plan(csv_path, upload("Date,Test Name,Value\n2026-03-01,ALT,31\n"))
        commit_plan(csv_path, plan)
        assert sorted(p.name for p in tmp_path.iterdir()) == ["labs.csv"]

    def test_building_a_plan_writes_nothing(self, csv_path):
        before = csv_path.read_text()
        build_plan(csv_path, upload("Date,Test Name,Value\n2025-10-10,ALT,99\n"))
        assert csv_path.read_text() == before
