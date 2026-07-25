"""Dash layout: header stat tiles, sidebar controls, and chart cards."""

from __future__ import annotations

import pandas as pd
from dash import dash_table, dcc, html

from . import theme
from .data import STATUS_HIGH, STATUS_IN, STATUS_LOW, MetricSeries
from .figures import make_figure

INITIAL_METRIC_COUNT = 10

STATUS_GLYPH = {STATUS_LOW: "▼", STATUS_HIGH: "▲", STATUS_IN: "●"}
STATUS_FLAG_TEXT = {STATUS_LOW: "▼ low", STATUS_HIGH: "▲ high", STATUS_IN: "● in range"}

DATE_WINDOWS = [
    {"label": "All", "value": "all"},
    {"label": "5 y", "value": "5"},
    {"label": "2 y", "value": "2"},
    {"label": "1 y", "value": "1"},
]


def build_table_rows(metrics: dict[str, MetricSeries]) -> list[dict]:
    """Sidebar table rows, newest last-draw first."""
    ordered = sorted(metrics.values(), key=lambda m: m.last_date, reverse=True)
    rows = []
    for m in ordered:
        rows.append(
            {
                "id": m.name,
                "name": m.name,
                "status": m.latest_status,
                "status_glyph": STATUS_GLYPH.get(m.latest_status, ""),
                "latest_display": m.latest_display,
                "last_date_display": m.last_date.strftime("%m/%y"),
                "last_date_sort": m.last_date.strftime("%Y-%m-%d"),
                "panel": m.panel,
            }
        )
    return rows


def window_cutoff(metrics: dict[str, MetricSeries], window: str) -> pd.Timestamp | None:
    """Cutoff timestamp for a date-window value ('all' or a year count)."""
    if window == "all" or not metrics:
        return None
    newest = max(m.last_date for m in metrics.values())
    return newest - pd.DateOffset(years=int(window))


def stat_tiles(metrics: dict[str, MetricSeries]) -> html.Div:
    """Header summary: metric count, draw count, latest draw, out-of-range count."""
    all_dates = {d.date() for m in metrics.values() for d in m.dates}
    latest = max(m.last_date for m in metrics.values()) if metrics else None
    out_count = sum(1 for m in metrics.values() if m.latest_status in {STATUS_LOW, STATUS_HIGH})

    def tile(label: str, value: str, note: str = "") -> html.Div:
        children = [html.P(label, className="tile-label"), html.P(value, className="tile-value")]
        if note:
            children.append(html.P(note, className="tile-note"))
        return html.Div(className="stat-tile", children=children)

    return html.Div(
        className="stat-tiles",
        children=[
            tile("Metrics tracked", str(len(metrics))),
            tile("Lab draws", str(len(all_dates))),
            tile("Latest draw", latest.strftime("%b %Y") if latest is not None else "—"),
            tile("Out of range", f"▲▼ {out_count}", "at latest result"),
        ],
    )


def chart_card(series: MetricSeries, cutoff: pd.Timestamp | None) -> html.Div:
    """A chart card: name, units, latest-value flag, and the figure."""
    flag_class = f"flag-{series.latest_status}" if series.latest_status != "unknown" else ""
    latest_children: list = [f"Latest {series.latest_display}"]
    if series.latest_status in STATUS_FLAG_TEXT:
        latest_children.append(html.Span(f" {STATUS_FLAG_TEXT[series.latest_status]}", className=flag_class))

    head = [html.H2(series.name)]
    if series.units:
        head.append(html.Span(series.units, className="units"))
    head.append(html.Span(latest_children, className="latest"))

    return html.Div(
        className="chart-card",
        children=[
            html.Div(className="card-head", children=head),
            dcc.Graph(
                figure=make_figure(series, cutoff),
                config={
                    "displaylogo": False,
                    "modeBarButtonsToRemove": ["zoomIn2d", "zoomOut2d", "resetScale2d", "lasso2d", "select2d"],
                },
                style={"height": "280px"},
            ),
        ],
    )


def render_graphs(
    metrics: dict[str, MetricSeries], selected: list[str], cutoff: pd.Timestamp | None
) -> list[html.Div]:
    """Chart cards for the selected metric names, in the given order."""
    return [chart_card(metrics[name], cutoff) for name in selected if name in metrics]


def metric_table(table_rows: list[dict], initial_selection: list[str]) -> dash_table.DataTable:
    return dash_table.DataTable(
        id="metric-table",
        columns=[
            {"name": "", "id": "status_glyph"},
            {"name": "Metric", "id": "name"},
            {"name": "Latest", "id": "latest_display"},
            {"name": "Date", "id": "last_date_display"},
            {"name": "_sort", "id": "last_date_sort"},
        ],
        data=table_rows,
        hidden_columns=["last_date_sort"],
        row_selectable="multi",
        selected_rows=[i for i, r in enumerate(table_rows) if r["id"] in set(initial_selection)],
        selected_row_ids=initial_selection,
        sort_action="native",
        sort_mode="single",
        sort_by=[{"column_id": "last_date_sort", "direction": "desc"}],
        style_as_list_view=True,
        css=[{"selector": ".dash-spreadsheet-menu", "rule": "display: none;"}],
        style_table={"maxHeight": "58vh", "overflowY": "auto"},
        style_header={
            "background": "transparent",
            "fontWeight": "600",
            "color": theme.INK_MUTED,
            "border": "none",
            "borderBottom": f"1px solid {theme.GRIDLINE}",
            "fontFamily": theme.FONT_STACK,
            "fontSize": "0.72rem",
        },
        style_cell={
            "background": "transparent",
            "border": "none",
            "borderBottom": f"1px solid {theme.GRIDLINE}",
            "color": theme.INK_SECONDARY,
            "padding": "0.4rem 0.5rem",
            "fontSize": "0.8rem",
            "fontFamily": theme.FONT_STACK,
            "textAlign": "left",
            "maxWidth": "150px",
            "overflow": "hidden",
            "textOverflow": "ellipsis",
        },
        style_cell_conditional=[
            {"if": {"column_id": "status_glyph"}, "width": "1.4rem", "padding": "0.4rem 0.1rem 0.4rem 0.4rem"},
            {"if": {"column_id": "latest_display"}, "fontVariantNumeric": "tabular-nums"},
        ],
        style_data_conditional=[
            {
                "if": {"column_id": "status_glyph", "filter_query": "{status} = low"},
                "color": theme.STATUS_CRITICAL,
            },
            {
                "if": {"column_id": "status_glyph", "filter_query": "{status} = high"},
                "color": theme.STATUS_CRITICAL,
            },
            {
                "if": {"column_id": "status_glyph", "filter_query": "{status} = in"},
                "color": theme.STATUS_GOOD,
            },
            {"if": {"state": "selected"}, "background": "rgba(57, 135, 229, 0.18)", "border": "none"},
            {"if": {"state": "active"}, "background": "rgba(57, 135, 229, 0.28)", "border": "none"},
        ],
    )


def build_layout(metrics: dict[str, MetricSeries], table_rows: list[dict]) -> html.Div:
    panels = sorted({r["panel"] for r in table_rows if r["panel"]})
    initial_selection = [r["id"] for r in table_rows[:INITIAL_METRIC_COUNT]] or [
        r["id"] for r in table_rows
    ]

    sidebar = html.Aside(
        className="sidebar",
        children=[
            html.Div(
                [
                    html.Label("Search metrics", className="control-label", htmlFor="metric-search"),
                    dcc.Input(
                        id="metric-search",
                        className="search-input",
                        type="text",
                        placeholder="e.g. glucose, LDL…",
                        debounce=False,
                    ),
                ]
            ),
            html.Div(
                [
                    html.Label("Panel", className="control-label"),
                    dcc.Dropdown(
                        id="panel-filter",
                        options=[{"label": p, "value": p} for p in panels],
                        placeholder="All panels",
                        clearable=True,
                    ),
                ]
            ),
            html.Div(
                className="abnormal-toggle",
                children=dcc.Checklist(
                    id="abnormal-only",
                    options=[{"label": "Out-of-range only (latest result)", "value": "on"}],
                    value=[],
                ),
            ),
            html.Div(
                className="selection-actions",
                children=[
                    html.Button("Select all", id="select-all", className="link-button", n_clicks=0),
                    html.Button(
                        "Clear all", id="clear-all", className="link-button", n_clicks=0
                    ),
                    html.Span(id="selection-count", className="selection-count"),
                ],
            ),
            metric_table(table_rows, initial_selection),
        ],
    )

    content = html.Section(
        className="content-area",
        children=[
            dcc.Store(id="selection-store", data=initial_selection),
            html.Div(
                className="filter-row",
                children=[
                    html.Span("Window", className="control-label"),
                    dcc.RadioItems(
                        id="date-window",
                        className="range-pills",
                        options=DATE_WINDOWS,
                        value="all",
                        inline=True,
                    ),
                    html.Button(
                        [html.Span("✦", className="ai-icon"), "Analysis with AI"],
                        id="ai-analyze",
                        className="ai-button",
                        n_clicks=0,
                    ),
                ],
            ),
            dcc.Loading(
                id="ai-loading",
                type="dot",
                color=theme.SERIES,
                children=html.Div(id="ai-commentary"),
            ),
            html.Div(
                id="graphs-container",
                className="graphs-grid",
                children=render_graphs(metrics, initial_selection, None),
            ),
        ],
    )

    return html.Div(
        [
            html.Header(
                className="app-header",
                children=[
                    html.Div(
                        [
                            html.H1("Blood Metrics"),
                            html.P("Lab results over time, with normal ranges", className="subtitle"),
                        ]
                    ),
                    stat_tiles(metrics),
                ],
            ),
            html.Div(className="app-shell", children=[sidebar, content]),
        ]
    )
