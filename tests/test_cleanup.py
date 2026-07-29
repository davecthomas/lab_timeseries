import csv

import pytest

from lab_timeseries_grapher import cleanup

HEADER = [
    "Date", "Test Name", "Value", "Value_Numeric", "Units",
    "Range_Low", "Range_High", "Typical range", "Panel", "Notes",
]


def write_csv(path, rows):
    target = path / "labs.csv"
    with target.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(HEADER)
        writer.writerows(rows)
    return target


def row(date="2024-01-01", name="ALT", value="23 U/L", numeric="23", units="U/L",
        low="7", high="55", typical="7 - 55 U/L", panel="Liver", notes=""):
    return [date, name, value, numeric, units, low, high, typical, panel, notes]


def read_back(path):
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class TestUnitExtraction:
    def test_pulls_a_known_unit(self):
        assert cleanup.unit_from_value("4.6 g/dL") == "g/dL"

    def test_ignores_unknown_trailing_text(self):
        """A comment must not be mistaken for a unit."""
        assert cleanup.unit_from_value("12 (see note)") == ""

    def test_handles_a_comparator(self):
        assert cleanup.unit_from_value("<0.5 mg/L") == "mg/L"

    def test_no_unit_present(self):
        assert cleanup.unit_from_value("5.4") == ""

    def test_micro_signs_compare_equal(self):
        assert cleanup.normalise_unit("µg/dL") == cleanup.normalise_unit("ug/dL")


class TestNumberFromValue:
    def test_keeps_a_thousands_separator(self):
        assert cleanup.number_from_value("3,457 cells/uL") == 3457.0

    def test_plain_number(self):
        assert cleanup.number_from_value("23 U/L") == 23.0

    def test_comparator_value(self):
        assert cleanup.number_from_value("<0.5 mg/L") == 0.5

    def test_no_number(self):
        assert cleanup.number_from_value("not detected") is None


class TestBoundsFromRange:
    @pytest.mark.parametrize("text", ["1,500 - 7,800", "1,500 – 7,800", "1,500 to 7,800"])
    def test_separators(self, text):
        assert cleanup.bounds_from_range(text) == (1500.0, 7800.0)

    def test_with_units(self):
        assert cleanup.bounds_from_range("0.8 - 1.9 ng/dL") == (0.8, 1.9)

    def test_unparseable(self):
        assert cleanup.bounds_from_range("see report") == (None, None)


class TestDuplicates:
    def test_identical_rows_collapse_to_one(self, tmp_path):
        path = write_csv(tmp_path, [row(), row()])
        plan = cleanup.build_cleanup_plan(path)
        assert [i.kind for i in plan.issues] == ["duplicate"]
        assert len(plan.rows) == 2  # header + one row

    def test_conflicting_values_keep_the_later_row(self, tmp_path):
        """The importer's rule: same test, same day, newest wins."""
        path = write_csv(tmp_path, [row(value="23 U/L", numeric="23"),
                                    row(value="99 U/L", numeric="99")])
        plan = cleanup.build_cleanup_plan(path)
        assert [i.kind for i in plan.issues] == ["conflict"]
        cleanup.commit_cleanup(path, plan)
        kept = read_back(path)
        assert len(kept) == 1
        assert kept[0]["Value_Numeric"] == "99"

    def test_different_dates_are_not_duplicates(self, tmp_path):
        path = write_csv(tmp_path, [row(date="2024-01-01"), row(date="2024-06-01")])
        assert cleanup.build_cleanup_plan(path).issues == []

    def test_different_tests_are_not_duplicates(self, tmp_path):
        path = write_csv(tmp_path, [row(name="ALT"), row(name="AST")])
        assert cleanup.build_cleanup_plan(path).issues == []

    def test_the_same_day_written_two_ways_is_one_duplicate(self, tmp_path):
        """Dates are normalised before comparison."""
        path = write_csv(tmp_path, [row(date="2024-01-01"), row(date="01/01/2024")])
        plan = cleanup.build_cleanup_plan(path)
        assert [i.kind for i in plan.issues] == ["duplicate"]

    def test_three_copies_collapse_to_one(self, tmp_path):
        path = write_csv(tmp_path, [row(), row(), row()])
        plan = cleanup.build_cleanup_plan(path)
        assert len(plan.issues) == 2
        assert len(plan.rows) == 2


class TestTruncatedNumbers:
    def test_value_restored_from_the_printed_number(self, tmp_path):
        path = write_csv(tmp_path, [row(value="3,457 cells/uL", numeric="3",
                                        units="cells/uL", low="1500", high="7800",
                                        typical="1500 - 7800 cells/uL")])
        plan = cleanup.build_cleanup_plan(path)
        assert [i.kind for i in plan.issues] == ["truncated_value"]
        cleanup.commit_cleanup(path, plan)
        assert read_back(path)[0]["Value_Numeric"] == "3457"

    def test_range_restored_from_the_printed_range(self, tmp_path):
        path = write_csv(tmp_path, [row(value="3457 cells/uL", numeric="3457",
                                        units="cells/uL", low="500", high="7",
                                        typical="1,500 - 7,800 cells/uL")])
        plan = cleanup.build_cleanup_plan(path)
        assert [i.kind for i in plan.issues] == ["truncated_range"]
        cleanup.commit_cleanup(path, plan)
        saved = read_back(path)[0]
        assert (saved["Range_Low"], saved["Range_High"]) == ("1500", "7800")

    def test_agreeing_numbers_are_left_alone(self, tmp_path):
        assert cleanup.build_cleanup_plan(write_csv(tmp_path, [row()])).issues == []

    def test_a_comparator_value_is_not_flagged(self, tmp_path):
        """'<0.5' stored as 0.5 is correct, not truncated."""
        path = write_csv(tmp_path, [row(value="<0.5 mg/L", numeric="0.5", units="mg/L",
                                        low="0", high="3", typical="0 - 3 mg/L")])
        assert cleanup.build_cleanup_plan(path).issues == []


class TestUnits:
    def test_blank_units_filled_from_the_value(self, tmp_path):
        path = write_csv(tmp_path, [row(units="")])
        plan = cleanup.build_cleanup_plan(path)
        assert [i.kind for i in plan.issues] == ["missing_units"]
        cleanup.commit_cleanup(path, plan)
        assert read_back(path)[0]["Units"] == "U/L"

    @pytest.mark.parametrize("blank", ["", "N/A", "unitless", "-", "nan"])
    def test_all_the_spellings_of_no_unit(self, tmp_path, blank):
        path = write_csv(tmp_path, [row(units=blank)])
        assert [i.kind for i in cleanup.build_cleanup_plan(path).issues] == ["missing_units"]

    def test_contradicting_units_are_reported_but_not_changed(self, tmp_path):
        """Picking a side would rescale a result; the row can't settle it."""
        path = write_csv(tmp_path, [row(value="1.64 ng/dL", numeric="1.64", units="g/dL",
                                        low="0.8", high="1.9", typical="0.8 - 1.9 ng/dL")])
        plan = cleanup.build_cleanup_plan(path)
        assert [i.kind for i in plan.issues] == ["unit_mismatch"]
        assert plan.total == 0
        assert plan.rows[1][4] == "g/dL"  # untouched

    def test_a_case_difference_is_not_a_mismatch(self, tmp_path):
        path = write_csv(tmp_path, [row(value="23 U/L", units="u/l")])
        assert cleanup.build_cleanup_plan(path).issues == []

    @pytest.mark.parametrize(
        ("column", "printed"),
        [
            ("10^3/µL", "x10E3/uL"),
            ("K/uL", "x10E3/uL"),
            ("10^6/µL", "x10E6/uL"),
            ("mcg/dL", "ug/dL"),
            ("mm/hr", "mm/h"),
        ],
    )
    def test_equivalent_spellings_are_not_a_disagreement(self, tmp_path, column, printed):
        """A readable units column must not be rewritten into a lab's encoding."""
        path = write_csv(tmp_path, [row(value=f"5.2 {printed}", numeric="5.2",
                                        units=column, low="", high="", typical="")])
        assert cleanup.build_cleanup_plan(path).issues == []

    def test_genuinely_different_units_still_disagree(self):
        assert not cleanup.units_agree("g/dL", "ng/dL")
        assert not cleanup.units_agree("mg/dL", "mmol/L")

    def test_units_absent_from_the_value_are_left_alone(self, tmp_path):
        """Nothing to copy, so the existing column stands."""
        path = write_csv(tmp_path, [row(value="23", units="U/L")])
        assert cleanup.build_cleanup_plan(path).issues == []


class TestInvertedRange:
    def test_swapped_bounds_are_righted(self, tmp_path):
        path = write_csv(tmp_path, [row(low="55", high="7", typical="")])
        plan = cleanup.build_cleanup_plan(path)
        assert [i.kind for i in plan.issues] == ["inverted_range"]
        cleanup.commit_cleanup(path, plan)
        saved = read_back(path)[0]
        assert (saved["Range_Low"], saved["Range_High"]) == ("7", "55")


class TestUnreadableRows:
    def test_reported_but_never_deleted(self, tmp_path):
        """Losing a result is worse than leaving a mess."""
        path = write_csv(tmp_path, [row(value="not detected", numeric="")])
        plan = cleanup.build_cleanup_plan(path)
        assert [i.kind for i in plan.issues] == ["unreadable"]
        assert plan.total == 0  # nothing offered as a fix
        assert len(plan.rows) == 2  # the row survives

    def test_a_short_row_is_reported_and_kept(self, tmp_path):
        target = tmp_path / "labs.csv"
        with target.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(HEADER)
            writer.writerow(["2024-01-01", "ALT"])
        plan = cleanup.build_cleanup_plan(target)
        assert [i.kind for i in plan.issues] == ["unreadable"]
        assert len(plan.rows) == 2

    def test_unreadable_rows_are_never_deduplicated(self, tmp_path):
        """Two unusable rows cannot be compared, so both are kept."""
        path = write_csv(tmp_path, [row(value="pending", numeric=""),
                                    row(value="pending", numeric="")])
        plan = cleanup.build_cleanup_plan(path)
        assert len(plan.rows) == 3


class TestPlanReporting:
    def test_a_clean_file_reports_nothing(self, tmp_path):
        plan = cleanup.build_cleanup_plan(write_csv(tmp_path, [row(), row(name="AST")]))
        assert plan.total == 0
        assert plan.by_kind() == {}
        assert plan.scanned == 2

    def test_grouping_follows_the_display_order(self, tmp_path):
        path = write_csv(tmp_path, [row(units=""), row(name="AST"), row(name="AST")])
        grouped = cleanup.build_cleanup_plan(path).by_kind()
        assert list(grouped) == [k for k in cleanup.KIND_LABELS if k in grouped]

    def test_every_kind_has_a_label(self, tmp_path):
        path = write_csv(tmp_path, [row(units=""), row(), row()])
        for issue in cleanup.build_cleanup_plan(path).issues:
            assert issue.kind in cleanup.KIND_LABELS

    def test_scanning_does_not_touch_the_file(self, tmp_path):
        path = write_csv(tmp_path, [row(), row()])
        before = path.read_bytes()
        cleanup.build_cleanup_plan(path)
        assert path.read_bytes() == before


class TestCommit:
    def test_a_backup_is_kept(self, tmp_path):
        path = write_csv(tmp_path, [row(), row()])
        before = path.read_bytes()
        backup = cleanup.commit_cleanup(path, cleanup.build_cleanup_plan(path))
        assert backup.exists()
        assert backup.read_bytes() == before

    def test_the_backup_does_not_accumulate(self, tmp_path):
        """One backup, overwritten — not a new copy of health data each run."""
        path = write_csv(tmp_path, [row(), row()])
        cleanup.commit_cleanup(path, cleanup.build_cleanup_plan(path))
        cleanup.commit_cleanup(path, cleanup.build_cleanup_plan(path))
        assert len(list((tmp_path / cleanup.BACKUP_DIR).glob("*.csv"))) == 1

    def test_the_backup_never_sits_beside_the_data(self, tmp_path):
        """A second *.csv in /data breaks the single-CSV fallback, and would be
        loaded as live data if the real file were ever lost."""
        path = write_csv(tmp_path, [row(), row()])
        cleanup.commit_cleanup(path, cleanup.build_cleanup_plan(path))
        assert [p.name for p in tmp_path.glob("*.csv")] == ["labs.csv"]

    def test_the_backup_keeps_the_original_filename(self, tmp_path):
        path = write_csv(tmp_path, [row(), row()])
        backup = cleanup.commit_cleanup(path, cleanup.build_cleanup_plan(path))
        assert backup == tmp_path / cleanup.BACKUP_DIR / "labs.csv"

    def test_the_header_survives(self, tmp_path):
        path = write_csv(tmp_path, [row(), row()])
        cleanup.commit_cleanup(path, cleanup.build_cleanup_plan(path))
        with path.open(newline="", encoding="utf-8") as fh:
            assert next(csv.reader(fh)) == HEADER

    def test_running_twice_is_a_no_op_the_second_time(self, tmp_path):
        path = write_csv(tmp_path, [row(units=""), row(), row()])
        cleanup.commit_cleanup(path, cleanup.build_cleanup_plan(path))
        assert cleanup.build_cleanup_plan(path).total == 0

    def test_an_empty_plan_refuses_to_write(self, tmp_path):
        with pytest.raises(ValueError):
            cleanup.commit_cleanup(write_csv(tmp_path, [row()]), cleanup.CleanupPlan())

    def test_unrelated_columns_are_preserved(self, tmp_path):
        path = write_csv(tmp_path, [row(units="", notes="drawn fasting")])
        cleanup.commit_cleanup(path, cleanup.build_cleanup_plan(path))
        saved = read_back(path)[0]
        assert saved["Notes"] == "drawn fasting"
        assert saved["Panel"] == "Liver"


class TestAgainstRealDamage:
    """The failure modes this was written for, as found in real exports."""

    def test_repairs_a_row_with_several_faults_at_once(self, tmp_path):
        path = write_csv(tmp_path, [row(
            value="3,457 cells/uL", numeric="3", units="",
            low="7800", high="1500", typical="1,500 - 7,800 cells/uL",
        )])
        plan = cleanup.build_cleanup_plan(path)
        assert {i.kind for i in plan.issues} == {"truncated_value", "truncated_range",
                                                 "missing_units"}
        cleanup.commit_cleanup(path, plan)
        saved = read_back(path)[0]
        assert saved["Value_Numeric"] == "3457"
        assert (saved["Range_Low"], saved["Range_High"]) == ("1500", "7800")
        assert saved["Units"] == "cells/uL"

    def test_a_repaired_row_still_wins_deduplication(self, tmp_path):
        path = write_csv(tmp_path, [row(value="23 U/L", numeric="23"),
                                    row(value="3,457 U/L", numeric="3")])
        plan = cleanup.build_cleanup_plan(path)
        cleanup.commit_cleanup(path, plan)
        kept = read_back(path)
        assert len(kept) == 1
        assert kept[0]["Value_Numeric"] == "3457"
