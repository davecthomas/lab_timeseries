from datetime import datetime

from lab_timeseries_grapher.analyses import (
    analysis_label,
    export_filename,
    export_markdown,
    find,
    find_by_key,
    make_analysis,
    selection_key,
    upsert,
    window_label,
)

T0 = datetime(2026, 7, 25, 14, 5, 0)
T1 = datetime(2026, 7, 25, 14, 9, 0)


class TestSelectionKey:
    def test_order_does_not_matter(self):
        assert selection_key(["B", "A"], "all") == selection_key(["A", "B"], "all")

    def test_window_is_part_of_identity(self):
        assert selection_key(["A"], "all") != selection_key(["A"], "2")

    def test_different_metrics_differ(self):
        assert selection_key(["A"], "all") != selection_key(["A", "B"], "all")

    def test_missing_window_reads_as_all(self):
        assert selection_key(["A"], None) == selection_key(["A"], "all")


class TestLabels:
    def test_single_metric(self):
        assert analysis_label(["MCV"]) == "MCV"

    def test_two_metrics(self):
        assert analysis_label(["MCV", "RDW"]) == "MCV, RDW"

    def test_more_than_two_summarized(self):
        assert analysis_label(["MCV", "RDW", "Bun", "ALT"]) == "MCV, RDW + 2 more"

    def test_empty(self):
        assert analysis_label([]) == "No metrics"

    def test_window_wording(self):
        assert window_label("all") == "all results"
        assert window_label(None) == "all results"
        assert window_label("2") == "last 2 y"


class TestMakeAnalysis:
    def test_carries_selection_and_text(self):
        entry = make_analysis(["MCV", "RDW"], "2", "## Summary", T0)
        assert entry["metrics"] == ["MCV", "RDW"]
        assert entry["count"] == 2
        assert entry["window"] == "2"
        assert entry["text"] == "## Summary"
        assert entry["key"] == selection_key(["MCV", "RDW"], "2")

    def test_created_time_is_readable(self):
        assert make_analysis(["MCV"], "all", "x", T0)["created"] == "2:05 PM"

    def test_ids_differ_across_time(self):
        assert make_analysis(["A"], "all", "x", T0)["id"] != make_analysis(["A"], "all", "x", T1)["id"]


class TestUpsert:
    def test_adds_newest_first(self):
        a = make_analysis(["A"], "all", "first", T0)
        b = make_analysis(["B"], "all", "second", T1)
        assert [e["id"] for e in upsert(upsert([], a), b)] == [b["id"], a["id"]]

    def test_same_selection_replaces_in_place(self):
        a = make_analysis(["A"], "all", "first", T0)
        again = make_analysis(["A"], "all", "second", T1)
        entries = upsert(upsert([], a), again)
        assert len(entries) == 1
        assert entries[0]["text"] == "second"

    def test_same_metrics_different_window_kept_separately(self):
        a = make_analysis(["A"], "all", "x", T0)
        b = make_analysis(["A"], "2", "y", T1)
        assert len(upsert(upsert([], a), b)) == 2

    def test_handles_none(self):
        entry = make_analysis(["A"], "all", "x", T0)
        assert upsert(None, entry) == [entry]


class TestLookup:
    def test_find_by_id(self):
        a = make_analysis(["A"], "all", "x", T0)
        assert find([a], a["id"]) is a
        assert find([a], "nope") is None
        assert find(None, "x") is None

    def test_find_by_key(self):
        a = make_analysis(["A"], "all", "x", T0)
        assert find_by_key([a], selection_key(["A"], "all")) is a
        assert find_by_key([a], selection_key(["B"], "all")) is None


class TestExport:
    def test_includes_every_analysis_oldest_first(self):
        a = make_analysis(["A"], "all", "first body", T0)
        b = make_analysis(["B"], "all", "second body", T1)
        doc = export_markdown(upsert(upsert([], a), b))
        assert doc.index("first body") < doc.index("second body")

    def test_carries_metadata_and_disclaimer(self):
        entry = make_analysis(["MCV", "RDW"], "2", "body", T0)
        doc = export_markdown([entry])
        assert "## MCV, RDW" in doc
        assert "2 metric(s) · last 2 y" in doc
        assert "Metrics: MCV, RDW" in doc
        assert "not medical advice" in doc

    def test_empty_export_is_still_valid_markdown(self):
        doc = export_markdown([])
        assert doc.startswith("# Blood Metrics")
        assert "No analyses" in doc

    def test_filename_is_timestamped(self):
        assert export_filename(T0) == "blood-metrics-ai-analyses-20260725-1405.md"
