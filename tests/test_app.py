import pandas as pd

from lab_timeseries_grapher.app import (
    ai_panel,
    consent_denied,
    consent_granted,
    create_app,
    filter_rows,
    merge_selection,
    resolve_consent,
    resolve_selection,
    selection_order,
)
from lab_timeseries_grapher.data import MetricSeries
from lab_timeseries_grapher.layout import build_table_rows, window_cutoff


def make_metric(name, values, band=(2.0, 8.0), panel="CMP", start="2024-01-01"):
    dates = pd.date_range(start, periods=len(values), freq="MS")
    return MetricSeries(
        name=name,
        dates=list(dates),
        values=values,
        display_values=[str(v) for v in values],
        band=band,
        units="u",
        panel=panel,
    )


def sample_metrics():
    return {
        "Glucose": make_metric("Glucose", [90.0], band=(70.0, 100.0)),
        "LDL": make_metric("LDL", [160.0], band=(0.0, 130.0), panel="Lipid Panel", start="2025-01-01"),
        "TSH": make_metric("TSH", [2.0], band=None, panel="Thyroid"),
    }


class TestBuildTableRows:
    def test_newest_draw_first(self):
        rows = build_table_rows(sample_metrics())
        assert rows[0]["name"] == "LDL"

    def test_status_and_glyph(self):
        rows = {r["name"]: r for r in build_table_rows(sample_metrics())}
        assert rows["LDL"]["status"] == "high"
        assert rows["LDL"]["status_glyph"] == "▲"
        assert rows["Glucose"]["status_glyph"] == "●"
        assert rows["TSH"]["status_glyph"] == ""


class TestFilterRows:
    def test_search_matches_name_and_panel(self):
        rows = build_table_rows(sample_metrics())
        assert [r["name"] for r in filter_rows(rows, "gluc", None, [])] == ["Glucose"]
        assert [r["name"] for r in filter_rows(rows, "lipid", None, [])] == ["LDL"]

    def test_panel_filter(self):
        rows = build_table_rows(sample_metrics())
        assert [r["name"] for r in filter_rows(rows, None, "Thyroid", [])] == ["TSH"]

    def test_abnormal_only(self):
        rows = build_table_rows(sample_metrics())
        assert [r["name"] for r in filter_rows(rows, None, None, ["on"])] == ["LDL"]

    def test_no_filters_returns_all(self):
        rows = build_table_rows(sample_metrics())
        assert len(filter_rows(rows, None, None, [])) == 3


class TestMergeSelection:
    def test_visible_selection_replaces_stored(self):
        merged = merge_selection(["A", "B"], ["A", "B", "C"], ["B", "C"])
        assert merged == ["B", "C"]

    def test_hidden_ids_survive_filtering(self):
        merged = merge_selection(["A", "B"], ["C", "D"], ["C"])
        assert merged == ["A", "B", "C"]

    def test_uncheck_removes_visible_id(self):
        merged = merge_selection(["A", "B"], ["A", "B"], ["A"])
        assert merged == ["A"]

    def test_handles_none_inputs(self):
        assert merge_selection(None, ["A"], None) == []


class TestResolveSelection:
    def test_select_all_adds_every_listed_row(self):
        out = resolve_selection("select-all", ["A"], ["A", "B", "C"], ["A", "B", "C"], ["A"])
        assert out == ["A", "B", "C"]

    def test_select_all_respects_filtered_list_and_keeps_hidden(self):
        out = resolve_selection("select-all", ["Z"], ["A", "B"], ["A", "B"], [])
        assert out == ["Z", "A", "B"]

    def test_clear_all_empties_including_hidden(self):
        out = resolve_selection("clear-all", ["A", "Z"], ["A"], ["A"], ["A"])
        assert out == []

    def test_checkbox_change_merges_visible_selection(self):
        out = resolve_selection("metric-table", ["A", "Z"], ["A", "B"], ["A", "B"], ["B"])
        assert out == ["Z", "B"]

    def test_filter_change_leaves_selection_untouched(self):
        out = resolve_selection("metric-search", ["A", "Z"], ["A"], ["A", "Z"], ["A"])
        assert out == ["A", "Z"]

    def test_handles_none_stored(self):
        assert resolve_selection("select-all", None, ["A"], [], None) == ["A"]


class TestConsentGate:
    def test_first_click_opens_dialog_and_does_not_run(self):
        show, store, runs = resolve_consent("ai-analyze", None, [], 0)
        assert show is True
        assert runs == 0
        assert store is None

    def test_yes_runs_once_without_remembering(self):
        show, store, runs = resolve_consent("consent-yes", None, [], 0)
        assert (show, runs) == (False, 1)
        assert store is None  # asked again next time

    def test_yes_with_remember_is_persisted(self):
        _, store, runs = resolve_consent("consent-yes", None, ["on"], 0)
        assert store == {"decision": "granted"}
        assert runs == 1

    def test_remembered_yes_skips_the_dialog(self):
        show, _, runs = resolve_consent("ai-analyze", {"decision": "granted"}, [], 4)
        assert (show, runs) == (False, 5)

    def test_no_cancels_without_running(self):
        show, store, runs = resolve_consent("consent-no", None, [], 2)
        assert (show, runs) == (False, 2)
        assert store is None

    def test_no_with_remember_records_denial(self):
        _, store, runs = resolve_consent("consent-no", None, ["on"], 2)
        assert store == {"decision": "denied"}
        assert runs == 2

    def test_denied_never_reopens_or_runs(self):
        show, _, runs = resolve_consent("ai-analyze", {"decision": "denied"}, [], 3)
        assert (show, runs) == (False, 3)

    def test_unknown_trigger_is_inert(self):
        assert resolve_consent(None, None, [], 7) == (False, None, 7)


class TestConsentPredicates:
    def test_granted(self):
        assert consent_granted({"decision": "granted"}) is True
        assert consent_granted({"decision": "denied"}) is False
        assert consent_granted(None) is False

    def test_denied(self):
        assert consent_denied({"decision": "denied"}) is True
        assert consent_denied({"decision": "granted"}) is False
        assert consent_denied(None) is False


class TestAiPanel:
    def test_error_panel_marked(self):
        panel = ai_panel("boom", error=True)
        assert "ai-error" in panel.className

    def test_success_panel_reports_count(self):
        panel = ai_panel("## Summary", count=3)
        assert "ai-error" not in panel.className
        assert "3 metric(s)" in panel.children[0].children[1]


class TestSelectionOrder:
    def test_visible_table_order_first(self):
        rows = [{"id": "C"}, {"id": "A"}]
        assert selection_order(["A", "B", "C"], rows) == ["C", "A", "B"]

    def test_no_visible_rows_keeps_stored_order(self):
        assert selection_order(["A", "B"], None) == ["A", "B"]


class TestWindowCutoff:
    def test_all_is_none(self):
        assert window_cutoff(sample_metrics(), "all") is None

    def test_years_before_newest_draw(self):
        cutoff = window_cutoff(sample_metrics(), "1")
        assert cutoff == pd.Timestamp("2024-01-01")


class TestCreateApp:
    def test_smoke(self):
        app = create_app(sample_metrics())
        assert app.title == "Blood Metrics"
        assert app.layout is not None

    def test_index_restricts_image_sources(self):
        app = create_app(sample_metrics())
        assert "Content-Security-Policy" in app.index_string
        assert "img-src 'self' data: blob:;" in app.index_string
