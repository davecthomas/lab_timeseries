"""Dash application factory and callbacks.

Selection is tracked by metric id in a dcc.Store rather than by the
DataTable's own row indices: filtering swaps the row set out from under the
table, and index-based selection would silently re-attach checkmarks (and
charts) to whichever rows land on those indices.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import NamedTuple

from dash import ALL, Dash, Input, Output, State, ctx, dcc, html, no_update

from . import analyses, cleanup, entries, export, ingest, theme
from .commentary import CommentaryError, generate_commentary
from .data import STATUS_HIGH, STATUS_LOW, MetricSeries
from .layout import (
    ai_error as ai_error_body,
)
from .layout import (
    build_layout,
    condition_legend,
    profile_scope_note,
    render_analysis,
    render_cleanup_preview,
    render_graphs,
    render_index,
    render_upload_preview,
    stat_tiles,
    window_cutoff,
)
from .reference_ranges import Profile
from .state import AppData
from .synonyms import format_synonyms

logger = logging.getLogger("lab_timeseries_grapher")


def filter_rows(
    table_rows: list[dict],
    search: str | None,
    panel: str | None,
    abnormal_only: list[str],
) -> list[dict]:
    """Apply the sidebar filters to the metric table rows."""
    rows = table_rows
    if search:
        needle = search.strip().lower()
        rows = [r for r in rows if needle in r["name"].lower() or needle in r["panel"].lower()]
    if panel:
        rows = [r for r in rows if r["panel"] == panel]
    if abnormal_only:
        rows = [r for r in rows if r["status"] in {STATUS_LOW, STATUS_HIGH}]
    return rows


def merge_selection(
    stored: list[str] | None,
    visible_ids: list[str],
    selected_visible: list[str] | None,
) -> list[str]:
    """Fold the table's visible selection into the stored id list.

    Ids hidden by the current filter keep their stored state; visible ids
    are replaced by what the checkboxes now say.
    """
    visible = set(visible_ids)
    selected = list(selected_visible or [])
    selected_set = set(selected)
    kept = [i for i in (stored or []) if i not in visible or i in selected_set]
    kept_set = set(kept)
    return kept + [i for i in selected if i not in kept_set]


def selection_order(stored: list[str], visible_rows: list[dict] | None) -> list[str]:
    """Chart order: current table order first, then selected-but-hidden ids."""
    stored_set = set(stored)
    visible = [r["id"] for r in visible_rows or [] if r.get("id") in stored_set]
    visible_set = set(visible)
    return visible + [i for i in stored if i not in visible_set]


GRANTED = "granted"
DENIED = "denied"


def consent_granted(store: dict | None) -> bool:
    """True when the user has agreed and asked not to be asked again."""
    return bool(store) and store.get("decision") == GRANTED


def consent_denied(store: dict | None) -> bool:
    """True when the user has declined and asked not to be asked again."""
    return bool(store) and store.get("decision") == DENIED


def resolve_consent(
    trigger: str | None,
    store: dict | None,
    remember: list[str] | None,
    runs: int | None,
) -> tuple[bool, dict | None, int]:
    """Decide what the consent gate does next.

    Returns (show_dialog, next_store, next_run_count). The run count is a
    counter the analysis callback listens on: bumping it starts a run.

    A decision is persisted only when "don't ask again" is ticked, so an
    un-ticked answer applies to this click alone.
    """
    runs = runs or 0
    keep = bool(remember)

    if trigger == "ai-analyze":
        if consent_granted(store):
            return False, store, runs + 1
        if consent_denied(store):
            return False, store, runs
        return True, store, runs

    if trigger == "consent-yes":
        return False, {"decision": GRANTED} if keep else store, runs + 1

    if trigger == "consent-no":
        return False, {"decision": DENIED} if keep else store, runs

    return False, store, runs


RUN_PROP = "ai-run-count.data"
ANALYZE_PROP = "ai-analyze.n_clicks"
RUN_TRIGGERS = {RUN_PROP, ANALYZE_PROP}


def is_run_request(
    runs: int | None, last_run: int | None, changed_props: object = ()
) -> bool:
    """True when the consent gate authorized a fresh run on this invocation.

    Both conditions are required, and each covers a distinct failure:

    - **The run prop must have changed.** `ai-run-count` is written only by
      the consent gate. `ai-last-run` advances only when this callback
      *returns*, so during a pending request the client holds `runs = N`
      against `last_run = N - 1`. Any invocation in that window — a close, an
      index click, or a second analyze click while the dialog is open — would
      otherwise spend that gap on an unconsented request.
    - **The counter must have advanced.** `ctx.triggered_id` reports only the
      first trigger of a coalesced chain, so the prop check reads
      `ctx.triggered_prop_ids`, which lists them all; the counter comparison
      then guards against replaying a value already handled.
    """
    props = set(changed_props or ())
    advanced = (runs or 0) > (last_run or 0)
    if RUN_PROP not in props:
        if ANALYZE_PROP in props and advanced:
            # Would mean Dash coalesced the chain without reporting the run
            # prop, which is the case the prop check assumes cannot happen.
            # Refusing is the safe default; this line names the reason.
            logger.warning(
                "Analyze click carried no %s among %s; refusing to run without it",
                RUN_PROP,
                sorted(props),
            )
        return False
    return advanced


class PaneState(NamedTuple):
    entries: list[dict]
    active: str | None
    visible: bool
    last_run: int
    error: str | None = None


def pane_update(
    *,
    trigger: object,
    changed_props: object,
    runs: int | None,
    last_run: int | None,
    ordered: list[str],
    window: str | None,
    entries: list[dict],
    active: str | None,
    visible: bool,
    run_analysis,
    now,
) -> PaneState:
    """Next pane state for one callback invocation.

    Pure apart from `run_analysis`, which is injected so the decision — above
    all, *whether to call the provider at all* — can be exercised without a
    Dash context or a network call.
    """
    runs, last_run = runs or 0, last_run or 0
    entries = list(entries or [])

    if not is_run_request(runs, last_run, changed_props):
        active, visible = resolve_pane_view(
            trigger, entries, analyses.selection_key(ordered, window) if ordered else None,
            active, visible,
        )
        return PaneState(entries, active, visible, last_run)

    if not ordered:
        return PaneState(
            entries, active, True, runs, "Select at least one metric, then run the analysis."
        )

    try:
        text = run_analysis(ordered, window)
    except CommentaryError as exc:
        return PaneState(entries, active, True, runs, str(exc))
    except Exception:  # pragma: no cover - defensive
        logger.exception("Unexpected error generating AI commentary")
        return PaneState(entries, active, True, runs, "Something went wrong generating the analysis.")

    entry = analyses.make_analysis(ordered, window, text, now())
    return PaneState(analyses.upsert(entries, entry), entry["id"], True, runs)


def resolve_pane_view(
    trigger: object,
    entries: list[dict],
    current_key: str | None,
    active: str | None,
    visible: bool,
) -> tuple[str | None, bool]:
    """Which analysis the pane shows, and whether it is open, after a
    non-run interaction.

    Held analyses stay in the session index; the pane only *displays* one
    while it still describes the current selection.
    """
    if trigger == "ai-close":
        return active, False
    if isinstance(trigger, dict) and trigger.get("type") == "ai-index-item":
        return trigger.get("index"), True

    held = analyses.find_by_key(entries, current_key) if current_key else None
    if trigger == "ai-analyze":
        # A held analysis already covers this selection: reveal it rather
        # than spending another request.
        return (held["id"], True) if held is not None else (active, visible)

    # Selection or window changed.
    if visible and held is None:
        return active, False
    if visible:
        return held["id"], True
    return active, visible


def resolve_selection(
    trigger: str | None,
    stored: list[str] | None,
    listed_ids: list[str],
    prev_visible_ids: list[str],
    selected_visible: list[str] | None,
    out_of_range_ids: list[str] | None = None,
) -> list[str]:
    """Next stored selection for whichever control fired.

    `listed_ids` are the rows the table shows after the current filters;
    `prev_visible_ids` are the rows it showed when the user last clicked.

    The out-of-range tile charts those metrics rather than merely filtering the
    list to them: filtering alone left every matching row *unselected*, so the
    charts went on showing whatever was selected before and the tile appeared
    to do nothing. It reads from `out_of_range_ids` rather than `listed_ids`
    because the filter it also switches on lands in a separate callback
    invocation, so the rows may not have narrowed yet when this one runs.
    """
    if trigger == "tile-out-of-range":
        return list(out_of_range_ids or [])
    if trigger == "select-all":
        kept = list(stored or [])
        kept_set = set(kept)
        return kept + [i for i in listed_ids if i not in kept_set]
    if trigger == "clear-all":
        return []
    if trigger == "metric-table":
        return merge_selection(stored, prev_visible_ids, selected_visible)
    return list(stored or [])


def create_app(data: AppData | dict[str, MetricSeries]) -> Dash:
    """Build the Dash app over reloadable app data.

    Callbacks read `data.metrics` / `data.table_rows` on every invocation
    rather than closing over them, so a manual entry can reload the CSV and
    have the charts, sidebar, and tiles pick it up without a restart.
    """
    if not isinstance(data, AppData):
        data = AppData.from_metrics(data)

    app = Dash(__name__)
    app.title = "Blood Metrics"
    app.index_string = theme.index_string()
    app.layout = build_layout(data.metrics, data.table_rows)

    # Seed the profile controls from whatever the app was started with.
    profile = data.profile or Profile()
    app.layout["profile-age"].value = profile.age
    app.layout["profile-sex"].value = profile.sex

    @app.callback(
        Output("data-version", "data", allow_duplicate=True),
        Input("profile-age", "value"),
        Input("profile-sex", "value"),
        State("data-version", "data"),
        prevent_initial_call=True,
    )
    def update_profile(age, sex, version):
        """Re-band every metric for a new age or sex."""
        if age is None or sex is None:
            return no_update
        data.profile = Profile(age=int(age), sex=sex)
        data.reload()
        logger.info("Reference profile set to %s, age %s", sex, age)
        return (version or 0) + 1

    # One callback owns both the row set and the selection: the table's checkbox
    # indices and the stored ids would otherwise chase each other in a cycle.
    @app.callback(
        Output("metric-table", "data"),
        Output("metric-table", "selected_rows"),
        Output("selection-store", "data"),
        Output("selection-count", "children"),
        Input("metric-search", "value"),
        Input("panel-filter", "value"),
        Input("abnormal-only", "value"),
        Input("select-all", "n_clicks"),
        Input("clear-all", "n_clicks"),
        Input("tile-out-of-range", "n_clicks"),
        Input("metric-table", "selected_row_ids"),
        Input("data-version", "data"),
        State("metric-table", "data"),
        State("selection-store", "data"),
    )
    def update_table(
        search, panel, abnormal_only, _select, _clear, _tile, selected_row_ids,
        _version, prev_rows, stored,
    ):
        rows = filter_rows(data.table_rows, search, panel, abnormal_only or [])
        listed_ids = [r["id"] for r in rows]
        prev_visible_ids = [r["id"] for r in prev_rows or []]

        trigger = ctx.triggered_id
        if trigger == "tile-out-of-range" and not (
            ctx.triggered and ctx.triggered[0].get("value")
        ):
            # Refreshing the stat tiles rebuilds the tile, and Dash fires for a
            # recreated component. Only a real click carries a count.
            trigger = None

        selection = resolve_selection(
            trigger, stored, listed_ids, prev_visible_ids, selected_row_ids,
            [r["id"] for r in data.table_rows if r["status"] in {STATUS_LOW, STATUS_HIGH}],
        )
        selected = set(selection)
        selected_rows = [i for i, r in enumerate(rows) if r["id"] in selected]
        return rows, selected_rows, selection, f"{len(selection)} selected"

    @app.callback(
        Output("graphs-container", "children"),
        Input("selection-store", "data"),
        Input("metric-table", "derived_virtual_data"),
        Input("date-window", "value"),
        Input("data-version", "data"),
        Input("conditions-select", "value"),
    )
    def update_graphs(stored, visible_rows, window, _version, conditions_selected):
        if not stored:
            return [
                html.Div(
                    className="chart-card",
                    children=[
                        html.H2("Select a metric to begin"),
                        html.P(
                            "Choose metrics from the table on the left; filter by search, "
                            "panel, or out-of-range status.",
                            className="empty-note",
                        ),
                    ],
                )
            ]

        ordered = selection_order(stored, visible_rows)
        cutoff = window_cutoff(data.metrics, window or "all")
        rendered = render_graphs(data.metrics, ordered, cutoff, conditions_selected)
        if not rendered:
            logger.warning("No graphs rendered for selection: %s", ", ".join(stored))
        return rendered

    @app.callback(
        Output("ai-consent-modal", "style"),
        Output("ai-consent-store", "data"),
        Output("ai-run-count", "data"),
        Input("ai-analyze", "n_clicks"),
        Input("consent-yes", "n_clicks"),
        Input("consent-no", "n_clicks"),
        State("consent-remember", "value"),
        State("ai-consent-store", "data"),
        State("ai-run-count", "data"),
        prevent_initial_call=True,
    )
    def consent_gate(_analyze, _yes, _no, remember, store, runs):
        show, next_store, next_runs = resolve_consent(ctx.triggered_id, store, remember, runs)
        # Only write the counter when a run should start; writing an unchanged
        # value could still wake the analysis callback.
        runs_out = next_runs if next_runs != (runs or 0) else no_update
        return {"display": "flex" if show else "none"}, next_store, runs_out

    @app.callback(
        Output("ai-analyze", "disabled"),
        Output("ai-analyze", "title"),
        Input("ai-consent-store", "data"),
    )
    def gate_button(store):
        if consent_denied(store):
            return True, (
                "You chose not to share lab data with the AI. Clear this site's "
                "storage to re-enable."
            )
        return False, "Send the selected metrics to the AI for commentary"

    # One owner for the pane: a run, a close, a show, and an index click all
    # move the same three pieces of state, and the API call lives inside the
    # callback that writes the pane body so the spinner reflects it.
    @app.callback(
        Output("ai-pane-body", "children"),
        Output("ai-index", "children"),
        Output("ai-analyses", "data"),
        Output("ai-active", "data"),
        Output("ai-visible", "data"),
        Output("ai-last-run", "data"),
        Input("ai-run-count", "data"),
        Input("ai-close", "n_clicks"),
        Input("ai-analyze", "n_clicks"),
        Input({"type": "ai-index-item", "index": ALL}, "n_clicks"),
        Input("selection-store", "data"),
        Input("date-window", "value"),
        State("metric-table", "derived_virtual_data"),
        State("ai-analyses", "data"),
        State("ai-active", "data"),
        State("ai-visible", "data"),
        State("ai-last-run", "data"),
        prevent_initial_call=True,
    )
    def update_pane(
        runs, _close, _show, _items, stored, window, visible_rows, entries, active, visible, last_run
    ):
        ordered = selection_order(stored or [], visible_rows)
        state = pane_update(
            trigger=ctx.triggered_id,
            changed_props=ctx.triggered_prop_ids,
            runs=runs,
            last_run=last_run,
            ordered=ordered,
            window=window,
            entries=entries or [],
            active=active,
            visible=visible,
            run_analysis=lambda names, win: generate_commentary(
                data.metrics, names, window_cutoff(data.metrics, win or "all")
            ),
            now=datetime.now,
        )

        current_key = analyses.selection_key(ordered, window) if ordered else None
        body = (
            ai_error_body(state.error)
            if state.error
            else render_analysis(analyses.find(state.entries, state.active))
        )
        index = render_index(state.entries, state.active, current_key)
        return body, index, state.entries, state.active, state.visible, state.last_run

    @app.callback(
        Output("ai-pane", "style"),
        Output("split-pane", "className"),
        Output("ai-analyze", "children"),
        Input("ai-visible", "data"),
        Input("ai-analyses", "data"),
        Input("selection-store", "data"),
        Input("date-window", "value"),
        State("metric-table", "derived_virtual_data"),
    )
    def render_split(visible, entries, stored, window, visible_rows):
        ordered = selection_order(stored or [], visible_rows)
        key = analyses.selection_key(ordered, window) if ordered else None
        held = analyses.find_by_key(entries, key) if key else None
        label = "Show analysis" if (held is not None and not visible) else "Analysis with AI"
        return (
            {"display": "flex"} if visible else {"display": "none"},
            "split-pane is-split" if visible else "split-pane",
            [html.Span("✦", className="ai-icon"), label],
        )

    @app.callback(
        Output("ai-download", "data"),
        Input("ai-export", "n_clicks"),
        State("ai-analyses", "data"),
        prevent_initial_call=True,
    )
    def export_analyses(_clicks, entries):
        return dcc.send_string(
            analyses.export_markdown(entries), analyses.export_filename(datetime.now())
        )

    @app.callback(
        Output("entry-metric", "children"),
        Output("entry-units", "children"),
        Output("entry-description", "children"),
        Output("entry-aka", "children"),
        Output("entry-units-input", "value"),
        Output("entry-range-low", "value"),
        Output("entry-range-high", "value"),
        Input("entry-metric-select", "value"),
    )
    def describe_chosen_metric(name):
        series = data.metrics.get(name) if name else None
        if series is None:
            return "", "", "", "", "", None, None
        # Pre-fill with the band the charts already use, so the field only
        # needs touching when the lab report disagrees with it.
        low, high = series.band if series.band else (None, None)
        return (
            series.name,
            series.units,
            series.description,
            format_synonyms(series.name),
            series.units,
            low,
            high,
        )

    # One owner for the dialog: opening, cancelling and saving all move the
    # same pieces, and a failed save must leave the dialog up with its reason.
    @app.callback(
        Output("entry-modal", "style"),
        Output("entry-metric-select", "value"),
        Output("entry-error", "children"),
        Output("data-version", "data"),
        Output("entry-value", "value"),
        Input("entry-open", "n_clicks"),
        Input("entry-open-sidebar", "n_clicks"),
        Input({"type": "card-add", "index": ALL}, "n_clicks"),
        Input("entry-cancel", "n_clicks"),
        Input("entry-save", "n_clicks"),
        State("selection-store", "data"),
        State("entry-metric-select", "value"),
        State("entry-date", "date"),
        State("entry-value", "value"),
        State("entry-units-input", "value"),
        State("entry-range-low", "value"),
        State("entry-range-high", "value"),
        State("data-version", "data"),
        prevent_initial_call=True,
    )
    def entry_dialog_flow(
        _open, _open2, _cards, _cancel, _save, stored, chosen, when, value, units, low, high,
        version,
    ):
        trigger = ctx.triggered_id
        shown = {"display": "flex"}
        hidden = {"display": "none"}

        if isinstance(trigger, dict) and trigger.get("type") == "card-add":
            # Rendering charts *creates* these buttons, and Dash fires the
            # callback for newly-matched pattern components. Only a real click
            # carries a click count, so an appearing button is ignored.
            clicked = ctx.triggered[0].get("value") if ctx.triggered else None
            if not clicked:
                return no_update, no_update, no_update, no_update, no_update
            # The button lives on a chart, so the metric is unambiguous.
            return shown, trigger.get("index"), "", no_update, None

        if trigger in {"entry-open", "entry-open-sidebar"}:
            # Pre-fill from the selection when it is unambiguous; otherwise
            # leave the picker empty for the user to choose.
            preset = (stored or [None])[0] if len(stored or []) == 1 else None
            return shown, preset, "", no_update, None

        if trigger == "entry-cancel":
            return hidden, no_update, "", no_update, None

        try:
            entries.append_measurement(
                data.csv_path, data.metrics, chosen, when, value,
                units=units, range_low=low, range_high=high,
            )
        except entries.EntryError as exc:
            return shown, no_update, str(exc), no_update, no_update
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Failed to append manual entry")
            return shown, no_update, f"Could not save: {exc}", no_update, no_update

        data.reload()
        return hidden, no_update, "", (version or 0) + 1, None

    # Clicking the out-of-range tile filters the list to those metrics.
    @app.callback(
        Output("abnormal-only", "value"),
        Input("tile-out-of-range", "n_clicks"),
        prevent_initial_call=True,
    )
    def filter_to_out_of_range(clicks):
        # Refreshing the stat tiles rebuilds this button, and Dash fires the
        # callback for the recreated component. Without this guard, saving an
        # entry or a cleanup would silently switch the filter on.
        if not clicks:
            return no_update
        return ["on"]

    app.clientside_callback(
        """
        function (value) {
            const table = document.getElementById('metric-table');
            if (table) table.scrollIntoView({behavior: 'smooth', block: 'center'});
            return window.dash_clientside.no_update;
        }
        """,
        Output("tile-out-of-range", "title"),
        Input("abnormal-only", "value"),
        prevent_initial_call=True,
    )

    # Upload: build a plan, show it, and only write once it is confirmed.
    @app.callback(
        Output("upload-modal", "style"),
        Output("upload-preview", "children"),
        Output("upload-error", "children"),
        Output("upload-confirm", "disabled"),
        Output("upload-plan", "data"),
        Output("data-version", "data", allow_duplicate=True),
        Input("upload-open", "n_clicks"),
        Input("upload-cancel", "n_clicks"),
        Input("upload-csv", "contents"),
        Input("upload-confirm", "n_clicks"),
        State("upload-plan", "data"),
        State("data-version", "data"),
        prevent_initial_call=True,
    )
    def upload_flow(_open, _cancel, contents, _confirm, held, version):
        import base64

        trigger = ctx.triggered_id
        shown, hidden = {"display": "flex"}, {"display": "none"}

        if trigger == "upload-open":
            return shown, [], "", True, None, no_update
        if trigger == "upload-cancel":
            return hidden, [], "", True, None, no_update

        if trigger == "upload-csv":
            if not contents:
                return shown, [], "", True, None, no_update
            try:
                _, _, payload = contents.partition(",")
                frame = ingest.read_uploaded(base64.b64decode(payload))
                plan = ingest.build_plan(data.csv_path, frame)
            except ingest.IngestError as exc:
                return shown, [], str(exc), True, None, no_update
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("Could not read the uploaded CSV")
                return shown, [], f"Could not read that file: {exc}", True, None, no_update

            if plan.total == 0:
                return shown, render_upload_preview(plan), (
                    "Nothing in that file could be imported."
                ), True, None, no_update
            return shown, render_upload_preview(plan), "", False, {"rows": plan.rows}, no_update

        # Confirm
        if not held or not held.get("rows"):
            return shown, [], "Load a file first.", True, None, no_update
        try:
            plan = ingest.Plan(rows=held["rows"])
            ingest.commit_plan(data.csv_path, plan)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Could not write the imported CSV")
            return shown, no_update, f"Could not save: {exc}", True, no_update, no_update

        data.reload()
        return hidden, [], "", True, None, (version or 0) + 1

    # Clean up: scan on open, repair only once the report is confirmed.
    @app.callback(
        Output("cleanup-modal", "style"),
        Output("cleanup-report", "children"),
        Output("cleanup-error", "children"),
        Output("cleanup-confirm", "disabled"),
        Output("cleanup-plan", "data"),
        Output("data-version", "data", allow_duplicate=True),
        Input("cleanup-open", "n_clicks"),
        Input("cleanup-cancel", "n_clicks"),
        Input("cleanup-confirm", "n_clicks"),
        State("cleanup-plan", "data"),
        State("data-version", "data"),
        prevent_initial_call=True,
    )
    def cleanup_flow(_open, _cancel, _confirm, held, version):
        trigger = ctx.triggered_id
        shown, hidden = {"display": "flex"}, {"display": "none"}

        if trigger == "cleanup-cancel":
            return hidden, [], "", True, None, no_update

        if trigger == "cleanup-open":
            try:
                plan = cleanup.build_cleanup_plan(data.csv_path)
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("Could not scan the labs CSV")
                return shown, [], f"Could not read the data file: {exc}", True, None, no_update
            # A clean file still gets its report; there is just nothing to apply.
            return (
                shown, render_cleanup_preview(plan), "", plan.total == 0,
                {"rows": plan.rows} if plan.total else None, no_update,
            )

        # Confirm
        if not held or not held.get("rows"):
            return shown, no_update, "Nothing to fix.", True, None, no_update
        try:
            backup = cleanup.commit_cleanup(
                data.csv_path, cleanup.CleanupPlan(rows=held["rows"])
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Could not write the cleaned CSV")
            return shown, no_update, f"Could not save: {exc}", True, no_update, no_update

        logger.info("Cleanup applied; previous file kept at %s", backup)
        data.reload()
        return hidden, [], "", True, None, (version or 0) + 1

    @app.callback(
        Output("condition-legend", "children"),
        Output("condition-legend", "style"),
        Input("conditions-select", "value"),
    )
    def update_condition_legend(conditions_selected):
        legend = condition_legend(conditions_selected)
        return legend.children, legend.style

    @app.callback(
        Output("stat-tiles", "children"),
        Input("data-version", "data"),
        prevent_initial_call=True,
    )
    def refresh_tiles(_version):
        return stat_tiles(data.metrics).children

    # The claim this line makes depends on the data, so it is recomputed with
    # it rather than written once into the layout.
    @app.callback(
        Output("profile-scope", "children"),
        Input("data-version", "data"),
        prevent_initial_call=True,
    )
    def refresh_profile_scope(_version):
        return profile_scope_note(data.metrics)

    @app.callback(
        Output("export-csv", "disabled"),
        Output("export-csv", "title"),
        Input("selection-store", "data"),
    )
    def gate_export(stored):
        if not stored:
            return True, "Select at least one metric to export"
        return False, f"Download the {len(stored)} selected metric(s) as CSV"

    @app.callback(
        Output("metrics-download", "data"),
        Input("export-csv", "n_clicks"),
        State("selection-store", "data"),
        State("metric-table", "derived_virtual_data"),
        State("date-window", "value"),
        prevent_initial_call=True,
    )
    def export_metrics_csv(_clicks, stored, visible_rows, window):
        ordered = selection_order(stored or [], visible_rows)
        if not ordered:
            return no_update
        cutoff = window_cutoff(data.metrics, window or "all")
        text = export.metrics_csv(data.metrics, ordered, cutoff)
        logger.info("Exporting %d metric(s) as CSV", len(ordered))
        return dcc.send_string(text, export.csv_filename(datetime.now()))

    return app
