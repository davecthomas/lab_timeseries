"""Dash application factory and callbacks.

Selection is tracked by metric id in a dcc.Store rather than by the
DataTable's own row indices: filtering swaps the row set out from under the
table, and index-based selection would silently re-attach checkmarks (and
charts) to whichever rows land on those indices.
"""

from __future__ import annotations

import logging

from dash import Dash, Input, Output, State, html

from . import theme
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


def create_app(metrics: dict[str, MetricSeries]) -> Dash:
    """Build the Dash app for a prepared set of metric series."""
    table_rows = build_table_rows(metrics)

    app = Dash(__name__)
    app.title = "Blood Metrics"
    app.index_string = theme.index_string()
    app.layout = build_layout(metrics, table_rows)

    @app.callback(
        Output("metric-table", "data"),
        Output("metric-table", "selected_rows"),
        Input("metric-search", "value"),
        Input("panel-filter", "value"),
        Input("abnormal-only", "value"),
        State("selection-store", "data"),
    )
    def update_table(search, panel, abnormal_only, stored):
        rows = filter_rows(table_rows, search, panel, abnormal_only or [])
        selected = set(stored or [])
        return rows, [i for i, r in enumerate(rows) if r["id"] in selected]

    @app.callback(
        Output("selection-store", "data"),
        Input("metric-table", "selected_row_ids"),
        State("metric-table", "data"),
        State("selection-store", "data"),
    )
    def update_selection(selected_row_ids, visible_rows, stored):
        return merge_selection(stored, [r["id"] for r in visible_rows or []], selected_row_ids)

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

    return app
