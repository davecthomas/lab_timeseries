"""The AI pane's decision logic, including when the provider may be called.

`pane_update` is the whole callback body with `run_analysis` injected, so
every path — above all "does this invocation reach the network" — is
exercised without a Dash context or an HTTP request.

Two bugs live here and must stay covered:

1. Clicking analyze changes `ai-analyze` and `ai-run-count` in one chain.
   Dash invokes the callback once and reports only the first as the trigger,
   so a dispatch keyed on the trigger alone silently drops the run.
2. `ai-last-run` only advances when the callback returns, so while a request
   is in flight the client holds `runs = N` against `last_run = N - 1`. A
   counter comparison that any trigger could satisfy would turn a close, an
   index click, or a selection change into a second unconsented request.
"""

from datetime import datetime

import pytest

from lab_timeseries_grapher.app import pane_update
from lab_timeseries_grapher.commentary import CommentaryError

NOW = lambda: datetime(2026, 7, 25, 17, 30, 0)  # noqa: E731


@pytest.fixture
def provider():
    """Records every call, so 'was the provider reached' is assertable."""

    class Provider:
        def __init__(self):
            self.calls = []

        def __call__(self, names, window):
            self.calls.append(list(names))
            return f"## Summary\ncommentary for {', '.join(names)}"

    return Provider()


def update(provider, changed, *, trigger=None, runs=0, last_run=0, ordered=("ALT",), **kw):
    return pane_update(
        trigger=trigger,
        changed_props=changed,
        runs=runs,
        last_run=last_run,
        ordered=list(ordered),
        window=kw.get("window", "all"),
        entries=kw.get("entries", []),
        active=kw.get("active"),
        visible=kw.get("visible", False),
        run_analysis=provider,
        now=NOW,
    )


class TestRunDetection:
    def test_coalesced_click_runs_the_analysis(self, provider):
        """Regression: both props change in one invocation, only the first is
        reported as the trigger."""
        state = update(
            provider,
            {"ai-analyze.n_clicks": 1, "ai-run-count.data": 1},
            trigger="ai-analyze",
            runs=1,
        )
        assert provider.calls == [["ALT"]]
        assert len(state.entries) == 1
        assert state.visible is True
        assert state.last_run == 1

    def test_run_prop_alone_runs_the_analysis(self, provider):
        update(provider, {"ai-run-count.data": 1}, runs=1)
        assert provider.calls == [["ALT"]]

    def test_button_without_consent_does_not_run(self, provider):
        """No counter movement: the button opened the dialog, nothing more."""
        update(provider, {"ai-analyze.n_clicks": 1}, trigger="ai-analyze", runs=0)
        assert provider.calls == []

    def test_analyze_click_while_the_dialog_is_open_does_not_run(self, provider):
        """Consent was not remembered, so a second click re-opens the dialog.
        Nothing may be sent while that dialog sits unanswered, even though the
        counter is ahead of last_run from the still-pending first run."""
        state = update(
            provider,
            {"ai-analyze.n_clicks": 1},
            trigger="ai-analyze",
            runs=1,
            last_run=0,
            ordered=("ALT", "AST"),
        )
        assert provider.calls == []
        assert state.entries == []

    def test_steady_state_interaction_does_not_run(self, provider):
        update(provider, {"selection-store.data": 1}, trigger="selection-store", runs=1, last_run=1)
        assert provider.calls == []


class TestInFlightRace:
    """While a request is pending the counter is ahead of last_run. No
    unrelated trigger may spend that gap on a second request."""

    @pytest.mark.parametrize(
        "prop,trigger",
        [
            ("ai-close.n_clicks", "ai-close"),
            ("selection-store.data", "selection-store"),
            ("date-window.value", "date-window"),
            ('{"index":"1","type":"ai-index-item"}.n_clicks', {"type": "ai-index-item", "index": "1"}),
        ],
    )
    def test_interaction_during_a_pending_run_does_not_call_the_provider(
        self, provider, prop, trigger
    ):
        state = update(provider, {prop: 1}, trigger=trigger, runs=2, last_run=1)
        assert provider.calls == []
        assert state.last_run == 1  # the pending run still owns the counter

    def test_close_during_a_pending_run_still_closes(self, provider):
        state = update(
            provider, {"ai-close.n_clicks": 1}, trigger="ai-close", runs=2, last_run=1, visible=True
        )
        assert state.visible is False
        assert provider.calls == []


class TestAnalysesLifecycle:
    def test_second_selection_adds_a_second_analysis(self, provider):
        first = update(provider, {"ai-run-count.data": 1}, runs=1, ordered=("ALT",))
        second = update(
            provider,
            {"ai-run-count.data": 1},
            runs=2,
            last_run=1,
            ordered=("AST",),
            entries=first.entries,
        )
        assert {e["label"] for e in second.entries} == {"ALT", "AST"}

    def test_rerunning_a_selection_replaces_its_entry(self, provider):
        first = update(provider, {"ai-run-count.data": 1}, runs=1)
        second = update(
            provider, {"ai-run-count.data": 1}, runs=2, last_run=1, entries=first.entries
        )
        assert len(second.entries) == 1
        assert provider.calls == [["ALT"], ["ALT"]]

    def test_changing_selection_hides_but_keeps_the_analysis(self, provider):
        first = update(provider, {"ai-run-count.data": 1}, runs=1, ordered=("ALT",))
        state = update(
            provider,
            {"selection-store.data": 1},
            trigger="selection-store",
            runs=1,
            last_run=1,
            ordered=("AST",),
            entries=first.entries,
            visible=True,
        )
        assert state.visible is False
        assert len(state.entries) == 1

    def test_returning_to_a_selection_reveals_it_without_a_request(self, provider):
        first = update(provider, {"ai-run-count.data": 1}, runs=1, ordered=("ALT",))
        state = update(
            provider,
            {"ai-analyze.n_clicks": 1},
            trigger="ai-analyze",
            runs=1,
            last_run=1,
            ordered=("ALT",),
            entries=first.entries,
        )
        assert state.visible is True
        assert state.active == first.entries[0]["id"]
        assert provider.calls == [["ALT"]]  # revealed, not re-requested


class TestFailurePaths:
    def test_empty_selection_reports_without_calling(self, provider):
        state = update(provider, {"ai-run-count.data": 1}, runs=1, ordered=())
        assert provider.calls == []
        assert "at least one metric" in state.error
        assert state.entries == []

    def test_provider_error_surfaces_and_holds_nothing(self, provider):
        def boom(names, window):
            raise CommentaryError("no API key")

        state = pane_update(
            trigger=None,
            changed_props={"ai-run-count.data": 1},
            runs=1,
            last_run=0,
            ordered=["ALT"],
            window="all",
            entries=[],
            active=None,
            visible=False,
            run_analysis=boom,
            now=NOW,
        )
        assert state.error == "no API key"
        assert state.entries == []
        assert state.last_run == 1  # consumed, so the failure does not retry itself
