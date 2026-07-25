"""Exercise of the AI pane callback through Dash's own machinery.

These cover the run path, which is driven by the run counter rather than by
`ctx.triggered_id`: clicking analyze changes `ai-analyze` and `ai-run-count`
in one chain, Dash invokes the callback once, and reports only the first as
the trigger. A dispatch keyed on that id alone drops the run, which is the
bug these cover.

Dash's wrapper rebuilds the callback context from the request, so a test
cannot inject a specific `triggered_id`. Trigger-driven behavior (close,
index selection, reveal) is covered against `resolve_pane_view` in
test_app.py instead.
"""

import json

import pandas as pd
import pytest
from dash._callback_context import context_value
from dash._utils import AttributeDict

from lab_timeseries_grapher import app as appmod
from lab_timeseries_grapher.data import MetricSeries

OUTPUTS = [
    {"id": "ai-pane-body", "property": "children"},
    {"id": "ai-index", "property": "children"},
    {"id": "ai-analyses", "property": "data"},
    {"id": "ai-active", "property": "data"},
    {"id": "ai-visible", "property": "data"},
    {"id": "ai-last-run", "property": "data"},
]


def make_metric(name):
    return MetricSeries(
        name=name,
        dates=[pd.Timestamp("2021-01-01"), pd.Timestamp("2025-01-01")],
        values=[23.0, 25.0],
        display_values=["23", "25"],
        band=(0.0, 50.0),
        units="U/L",
        panel="CMP",
    )


@pytest.fixture
def pane(monkeypatch):
    """The registered pane callback, with the provider call stubbed out."""
    calls = []

    def fake_commentary(metrics, ordered, cutoff):
        calls.append(list(ordered))
        return f"## Summary\ncommentary for {', '.join(ordered)}"

    monkeypatch.setattr(appmod, "generate_commentary", fake_commentary)
    application = appmod.create_app({"ALT": make_metric("ALT"), "AST": make_metric("AST")})
    key = next(k for k in application.callback_map if "ai-pane-body" in k)
    callback = application.callback_map[key]["callback"]

    def run(
        changed,
        *,
        runs=0,
        last_run=0,
        selection=("ALT",),
        window="all",
        entries=None,
        active=None,
        visible=False,
        index_clicks=None,
    ):
        context_value.set(
            AttributeDict(triggered_inputs=[{"prop_id": p, "value": 1} for p in changed])
        )
        raw = callback(
            runs,
            0,
            1,
            index_clicks or [],
            list(selection),
            window,
            [{"id": name} for name in selection],
            entries or [],
            active,
            visible,
            last_run,
            outputs_list=OUTPUTS,
        )
        return json.loads(raw)["response"]

    run.calls = calls
    return run


class TestRunDispatch:
    def test_coalesced_click_runs_the_analysis(self, pane):
        """Regression: both props change in one invocation, only the first is
        reported as the trigger. The run must still happen."""
        out = pane(["ai-analyze.n_clicks", "ai-run-count.data"], runs=1, last_run=0)
        assert len(out["ai-analyses"]["data"]) == 1
        assert out["ai-visible"]["data"] is True
        assert out["ai-last-run"]["data"] == 1
        assert pane.calls == [["ALT"]]

    def test_run_prop_alone_runs_the_analysis(self, pane):
        out = pane(["ai-run-count.data"], runs=1, last_run=0)
        assert len(out["ai-analyses"]["data"]) == 1

    def test_button_without_counter_change_does_not_run(self, pane):
        """No consent yet: the button opens the dialog, it does not analyze."""
        out = pane(["ai-analyze.n_clicks"], runs=0, last_run=0)
        assert out["ai-analyses"]["data"] == []
        assert pane.calls == []

    def test_stale_counter_does_not_replay(self, pane):
        out = pane(["selection-store.data"], runs=1, last_run=1)
        assert pane.calls == []
        assert out["ai-analyses"]["data"] == []

    def test_empty_selection_reports_instead_of_calling(self, pane):
        out = pane(["ai-run-count.data"], runs=1, last_run=0, selection=())
        assert pane.calls == []
        assert out["ai-visible"]["data"] is True
        assert out["ai-analyses"]["data"] == []


class TestPaneState:
    def test_second_selection_adds_a_second_analysis(self, pane):
        first = pane(["ai-run-count.data"], runs=1, last_run=0, selection=("ALT",))
        out = pane(
            ["ai-run-count.data"],
            runs=2,
            last_run=1,
            selection=("AST",),
            entries=first["ai-analyses"]["data"],
        )
        held = out["ai-analyses"]["data"]
        assert len(held) == 2
        assert {e["label"] for e in held} == {"ALT", "AST"}

    def test_rerunning_a_selection_replaces_its_entry(self, pane):
        first = pane(["ai-run-count.data"], runs=1, last_run=0, selection=("ALT",))
        out = pane(
            ["ai-run-count.data"],
            runs=2,
            last_run=1,
            selection=("ALT",),
            entries=first["ai-analyses"]["data"],
        )
        assert len(out["ai-analyses"]["data"]) == 1

    def test_analyses_survive_a_non_run_interaction(self, pane):
        """Held analyses last the session even when the pane re-renders."""
        first = pane(["ai-run-count.data"], runs=1, last_run=0, selection=("ALT",))
        out = pane(
            ["selection-store.data"],
            runs=1,
            last_run=1,
            selection=("AST",),
            entries=first["ai-analyses"]["data"],
            visible=True,
        )
        assert len(out["ai-analyses"]["data"]) == 1
        assert pane.calls == [["ALT"]]  # no extra request
