"""Dash application factory and callbacks.

Selection is tracked by metric id in a dcc.Store rather than by the
DataTable's own row indices: filtering swaps the row set out from under the
table, and index-based selection would silently re-attach checkmarks (and
charts) to whichever rows land on those indices.
"""

from __future__ import annotations

import logging

from dash import Dash, Input, Output, State, ctx, dcc, html

from . import theme
from .commentary import CommentaryError, generate_commentary
from .data import STATUS_HIGH, STATUS_LOW, MetricSeries
from .layout import build_layout, build_table_rows, render_graphs, window_cutoff

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


def resolve_selection(
    trigger: str | None,
    stored: list[str] | None,
    listed_ids: list[str],
    prev_visible_ids: list[str],
    selected_visible: list[str] | None,
) -> list[str]:
    """Next stored selection for whichever control fired.

    `listed_ids` are the rows the table shows after the current filters;
    `prev_visible_ids` are the rows it showed when the user last clicked.
    """
    if trigger == "select-all":
        kept = list(stored or [])
        kept_set = set(kept)
        return kept + [i for i in listed_ids if i not in kept_set]
    if trigger == "clear-all":
        return []
    if trigger == "metric-table":
        return merge_selection(stored, prev_visible_ids, selected_visible)
    return list(stored or [])


def create_app(metrics: dict[str, MetricSeries]) -> Dash:
    """Build the Dash app for a prepared set of metric series."""
    table_rows = build_table_rows(metrics)

    app = Dash(__name__)
    app.title = "Blood Metrics"
    app.index_string = theme.index_string()
    app.layout = build_layout(metrics, table_rows)

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
        Input("metric-table", "selected_row_ids"),
        State("metric-table", "data"),
        State("selection-store", "data"),
    )
    def update_table(search, panel, abnormal_only, _select, _clear, selected_row_ids, prev_rows, stored):
        rows = filter_rows(table_rows, search, panel, abnormal_only or [])
        listed_ids = [r["id"] for r in rows]
        prev_visible_ids = [r["id"] for r in prev_rows or []]

        selection = resolve_selection(
            ctx.triggered_id, stored, listed_ids, prev_visible_ids, selected_row_ids
        )
        selected = set(selection)
        selected_rows = [i for i, r in enumerate(rows) if r["id"] in selected]
        return rows, selected_rows, selection, f"{len(selection)} selected"

    @app.callback(
        Output("graphs-container", "children"),
        Input("selection-store", "data"),
        Input("metric-table", "derived_virtual_data"),
        Input("date-window", "value"),
    )
    def update_graphs(stored, visible_rows, window):
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
        cutoff = window_cutoff(metrics, window or "all")
        rendered = render_graphs(metrics, ordered, cutoff)
        if not rendered:
            logger.warning("No graphs rendered for selection: %s", ", ".join(stored))
        return rendered

    @app.callback(
        Output("ai-commentary", "children"),
        Input("ai-analyze", "n_clicks"),
        State("selection-store", "data"),
        State("metric-table", "derived_virtual_data"),
        State("date-window", "value"),
        prevent_initial_call=True,
    )
    def analyze_with_ai(_clicks, stored, visible_rows, window):
        if not stored:
            return ai_panel("Select at least one metric, then run the analysis.", error=True)

        ordered = selection_order(stored, visible_rows)
        cutoff = window_cutoff(metrics, window or "all")
        try:
            text = generate_commentary(metrics, ordered, cutoff)
        except CommentaryError as exc:
            return ai_panel(str(exc), error=True)
        except Exception:  # pragma: no cover - defensive
            logger.exception("Unexpected error generating AI commentary")
            return ai_panel("Something went wrong generating the analysis.", error=True)
        return ai_panel(text, count=len(ordered))

    return app


def ai_panel(text: str, *, error: bool = False, count: int | None = None) -> html.Div:
    """Wrap commentary (or an error) in the AI panel."""
    label = "Analysis unavailable" if error else f"AI analysis · {count} metric(s)"
    return html.Div(
        className="ai-panel ai-error" if error else "ai-panel",
        children=[
            html.Div(
                className="ai-panel-head",
                children=[html.Span("✦", className="ai-icon"), label],
            ),
            dcc.Markdown(text) if not error else html.P(text),
        ],
    )
