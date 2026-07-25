import pandas as pd

from lab_timeseries_grapher.app import (
    consent_denied,
    consent_granted,
    create_app,
    filter_rows,
    is_run_request,
    merge_selection,
    resolve_consent,
    resolve_pane_view,
    resolve_selection,
    selection_order,
)
from lab_timeseries_grapher.data import MetricSeries
from lab_timeseries_grapher.layout import (
    ai_error,
    build_table_rows,
    render_analysis,
    render_index,
    window_cutoff,
)


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


class TestIsRunRequest:
    """The run prop is authoritative. The counter comparison backs it up for
    coalesced invocations, but only within the analyze chain: `ai-last-run`
    lags while a request is in flight, so a counter test open to any trigger
    would let an unrelated click start a second unconsented request."""

    def test_run_prop_is_a_run(self):
        assert is_run_request(1, 1, {"ai-run-count.data": "ai-run-count"}) is True

    def test_coalesced_click_is_a_run(self):
        changed = {"ai-analyze.n_clicks": "ai-analyze", "ai-run-count.data": "ai-run-count"}
        assert is_run_request(2, 1, changed) is True

    def test_analyze_prop_with_advanced_counter_is_a_run(self):
        assert is_run_request(2, 1, {"ai-analyze.n_clicks": "ai-analyze"}) is True

    def test_analyze_prop_without_counter_movement_is_not_a_run(self):
        assert is_run_request(1, 1, {"ai-analyze.n_clicks": "ai-analyze"}) is False

    def test_unrelated_trigger_never_runs_even_with_a_lagging_counter(self):
        for prop in ("ai-close.n_clicks", "selection-store.data", "date-window.value"):
            assert is_run_request(2, 1, {prop: "x"}) is False, prop

    def test_counter_alone_is_not_enough(self):
        # No trigger information: refuse rather than guess.
        assert is_run_request(2, 1) is False
        assert is_run_request(1, 0) is False

    def test_stale_counter_does_not_replay(self):
        assert is_run_request(2, 5, {"ai-analyze.n_clicks": "ai-analyze"}) is False

    def test_handles_none(self):
        assert is_run_request(None, None) is False
        assert is_run_request(1, None, {"ai-analyze.n_clicks": "x"}) is True
        assert is_run_request(None, 3, {"ai-analyze.n_clicks": "x"}) is False


class TestConsentPredicates:
    def test_granted(self):
        assert consent_granted({"decision": "granted"}) is True
        assert consent_granted({"decision": "denied"}) is False
        assert consent_granted(None) is False

    def test_denied(self):
        assert consent_denied({"decision": "denied"}) is True
        assert consent_denied({"decision": "granted"}) is False
        assert consent_denied(None) is False


def entry(entry_id="1", key="k1", label="MCV"):
    return {"id": entry_id, "key": key, "label": label, "count": 1, "window": "all"}


class TestResolvePaneView:
    def test_close_hides_the_pane(self):
        assert resolve_pane_view("ai-close", [entry()], "k1", "1", True) == ("1", False)

    def test_index_click_selects_that_analysis(self):
        trigger = {"type": "ai-index-item", "index": "2"}
        assert resolve_pane_view(trigger, [entry()], "k1", "1", False) == ("2", True)

    def test_button_reveals_a_held_analysis(self):
        assert resolve_pane_view("ai-analyze", [entry()], "k1", None, False) == ("1", True)

    def test_button_without_a_held_analysis_changes_nothing(self):
        # The run itself arrives via the counter, not through this path.
        assert resolve_pane_view("ai-analyze", [], "k9", None, False) == (None, False)

    def test_selection_change_hides_a_mismatched_analysis(self):
        assert resolve_pane_view("selection-store", [entry()], "k9", "1", True) == ("1", False)

    def test_selection_change_reveals_the_matching_analysis(self):
        entries = [entry("1", "k1"), entry("2", "k2", "RDW")]
        assert resolve_pane_view("selection-store", entries, "k2", "1", True) == ("2", True)

    def test_closed_pane_stays_closed_on_selection_change(self):
        assert resolve_pane_view("selection-store", [entry()], "k1", "1", False) == ("1", False)

    def test_no_selection_leaves_a_closed_pane_alone(self):
        assert resolve_pane_view("date-window", [entry()], None, "1", False) == ("1", False)


class TestPaneRendering:
    def test_error_body_is_marked(self):
        body = ai_error("boom")
        assert body[0].children.className.endswith("is-error")

    def test_analysis_body_has_copy_target(self):
        entry = {"id": "1", "label": "MCV", "text": "## Summary"}
        body = render_analysis(entry)
        clipboard = body[0].children[1]
        assert clipboard.target_id == "ai-body-text"
        assert body[1].id == "ai-body-text"

    def test_empty_body_prompts(self):
        body = render_analysis(None)
        assert "Select an analysis" in body[0].children

    def test_index_is_empty_without_analyses(self):
        assert render_index([], None, None) == []

    def test_index_marks_active_and_current(self):
        entries = [
            {"id": "1", "key": "k1", "label": "MCV", "count": 1, "window": "all", "created": "2:00 PM"},
            {"id": "2", "key": "k2", "label": "RDW", "count": 1, "window": "all", "created": "1:00 PM"},
        ]
        rows = render_index(entries, "1", "k2")
        assert "is-active" in rows[1].className
        assert "is-active" not in rows[2].className
        assert "current selection" in rows[2].children.children[1].children


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
