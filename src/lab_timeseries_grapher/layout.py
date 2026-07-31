"""Dash layout: header stat tiles, sidebar controls, and chart cards."""

from __future__ import annotations

from datetime import date

import pandas as pd
from dash import dash_table, dcc, html

from . import theme
from .analyses import window_label
from .commentary import configured_model_name
from .conditions import condition_options, effects_for, selected_conditions
from .data import (
    RECENT_MONTHS,
    STATUS_HIGH,
    STATUS_IN,
    STATUS_LOW,
    MetricSeries,
    is_current,
    newest_draw,
    out_of_range_now,
    status_in,
)
from .figures import make_figure
from .reference_ranges import describe_reference, varies_with_profile
from .synonyms import format_synonyms

INITIAL_METRIC_COUNT = 10

STATUS_GLYPH = {STATUS_LOW: "▼", STATUS_HIGH: "▲", STATUS_IN: "●"}
STATUS_FLAG_TEXT = {STATUS_LOW: "▼ low", STATUS_HIGH: "▲ high", STATUS_IN: "● in range"}
# Read against a condition's own band the question is different — "is this what
# the condition looks like?" — so the wording is too: "normal for X", never a
# bare "in range" that could be mistaken for the population verdict. Sitting
# inside the band takes no glyph: the condition's own swatch is already beside
# the words, and a second dot beside it just read as a smudge. ▼/▲ stay, because
# outside even the condition's band is worth a shape of its own.
CONDITION_STATUS_TEXT = {STATUS_LOW: "▼ low", STATUS_HIGH: "▲ high", STATUS_IN: "normal"}

DATE_WINDOWS = [
    {"label": "All", "value": "all"},
    {"label": "5 y", "value": "5"},
    {"label": "2 y", "value": "2"},
    {"label": "1 y", "value": "1"},
]


def build_table_rows(metrics: dict[str, MetricSeries]) -> list[dict]:
    """Sidebar table rows, newest last-draw first."""
    ordered = sorted(metrics.values(), key=lambda m: m.last_date, reverse=True)
    newest = newest_draw(metrics)
    rows = []
    for m in ordered:
        rows.append(
            {
                "id": m.name,
                "name": m.name,
                # Carried on the row so the out-of-range filter and the tile
                # answer the same question; otherwise the list shows a decade
                # of retired test names while the charts show this year's.
                "current": is_current(m, newest),
                "status": m.latest_status,
                "status_glyph": STATUS_GLYPH.get(m.latest_status, ""),
                "latest_display": m.latest_display,
                "last_date_display": m.last_date.strftime("%b %Y"),
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
    out_count = len(out_of_range_now(metrics))

    def tile(label: str, value: str, note: str = "") -> html.Div:
        children = [html.P(label, className="tile-label"), html.P(value, className="tile-value")]
        if note:
            children.append(html.P(note, className="tile-note"))
        return html.Div(className="stat-tile", children=children)

    return html.Div(
        id="stat-tiles",
        className="stat-tiles",
        children=[
            tile("Metrics tracked", str(len(metrics))),
            tile("Lab draws", str(len(all_dates))),
            tile("Latest draw", latest.strftime("%b %Y") if latest is not None else "—"),
            html.Button(
                id="tile-out-of-range",
                className="stat-tile stat-tile-action",
                n_clicks=0,
                title="Chart the metrics that are out of range in recent bloodwork",
                children=[
                    html.P("Out of range", className="tile-label"),
                    html.P(f"▲▼ {out_count}", className="tile-value"),
                    html.P(
                        f"measured in the last {RECENT_MONTHS} months · click to chart",
                        className="tile-note",
                    ),
                ],
            ),
        ],
    )


def condition_legend(selected: list[str] | None) -> html.Div:
    """One legend for the whole chart set, not a repeat on every card.

    Hidden entirely when nothing is selected, so the default view carries no
    explanation for something it is not showing.
    """
    chosen = selected_conditions(selected)
    if not chosen:
        return html.Div(id="condition-legend", className="condition-legend", style={"display": "none"})

    items: list = [
        html.Span("Condition ranges", className="legend-title"),
    ]
    for condition in chosen:
        # A condition with no band gets a hollow swatch: there is nothing
        # shaded on the charts for it, and a filled key would imply there is.
        swatch_class = "legend-swatch" if condition.has_bands else "legend-swatch legend-swatch-empty"
        # Each entry is the control for its own condition: clicking it drops
        # the charts that condition has nothing to say about, leaving the ones
        # it bears on. A key that already names the condition is the obvious
        # place to ask for that.
        items.append(
            html.Button(
                id={"type": "condition-chart", "index": condition.id},
                className="legend-item legend-item-action",
                n_clicks=0,
                title=(
                    f"Show only the charted metrics {condition.label} bears on — "
                    f"{condition.summary} — {condition.source}"
                ),
                children=[
                    html.Span(
                        className=swatch_class,
                        style={
                            "background": condition.color if condition.has_bands else "transparent",
                            "borderColor": condition.color,
                        },
                    ),
                    html.Span(condition.label, className="legend-label"),
                    html.Span(
                        "" if condition.has_bands else " (note only)",
                        className="legend-aside",
                    ),
                ],
            )
        )
    items.append(
        html.Span(
            "Click a condition to keep only the charts it bears on. Shown "
            "alongside the normal range, which is unchanged. Not a diagnosis.",
            className="legend-caveat",
        )
    )
    # Style is set on both branches so a callback can read it either way.
    return html.Div(
        id="condition-legend",
        className="condition-legend",
        children=items,
        style={"display": "flex"},
    )


def profile_governed(metrics: dict[str, MetricSeries]) -> list[str]:
    """Metrics whose band the age/sex settings actually decide.

    Two conditions, and both matter. The reference only supplies a band where
    the rows carry none — a range printed by the lab wins — and the reference
    only moves with the profile for the tests whose published interval is
    age- or sex-banded. Most metrics meet neither, which is why this is worth
    stating rather than leaving the reader to infer it.
    """
    return sorted(
        m.name
        for m in metrics.values()
        if not m.lab_band and m.band and varies_with_profile(m.name)
    )


def profile_scope_note(metrics: dict[str, MetricSeries]) -> str:
    """One line saying what the age and sex inputs currently change."""
    if not metrics:
        return "Used for age and sex specific reference ranges."
    governed = profile_governed(metrics)
    if not governed:
        return (
            "No metric currently depends on these — every result carries a "
            "range from your lab, which takes precedence."
        )
    return (
        f"Sets the range for {len(governed)} of {len(metrics)} metrics. "
        "Elsewhere the range printed by your lab takes precedence."
    )


def condition_readings(series: MetricSeries, condition_effects: list | None) -> list:
    """The latest value read against each condition band that applies.

    A single "low" answers only the population question, which is the wrong
    question for a carrier: 13.3 g/dL is below the population floor *and*
    exactly where beta thalassemia trait puts it. Both readings are shown so
    the reader can see which one they are looking at.

    This adds a reading; it never edits one. The population flag keeps its
    wording, its colour and its glyph, and the sidebar verdict is untouched —
    a condition that could rewrite a flag could hide a real abnormality, which
    is the rule `conditions.py` exists to hold. Only the condition's hue rides
    along here, on the dot, so the extra text cannot read as a second verdict;
    the glyph and the words carry the status on their own.
    """
    readings: list = []
    for applied in condition_effects or []:
        if not applied.band:
            continue  # note-only: nothing to measure the value against
        status = status_in(series.latest_value, applied.band)
        if status not in CONDITION_STATUS_TEXT:
            continue
        readings.append(
            html.Span(
                [
                    html.Span(
                        className="condition-dot",
                        style={"background": applied.condition.color},
                    ),
                    f"{CONDITION_STATUS_TEXT[status]} for {applied.condition.label}",
                ],
                className="latest-condition",
                title=(
                    f"{applied.condition.label} range "
                    f"{applied.band[0]:g}–{applied.band[1]:g} {series.units}".strip()
                ),
            )
        )
    return readings


def chart_card(
    series: MetricSeries,
    cutoff: pd.Timestamp | None,
    condition_effects: list | None = None,
) -> html.Div:
    """A chart card: name, units, latest-value flag, and the figure."""
    flag_class = f"flag-{series.latest_status}" if series.latest_status != "unknown" else ""
    latest_children: list = [f"Latest {series.latest_display}"]
    if series.latest_status in STATUS_FLAG_TEXT:
        latest_children.append(html.Span(f" {STATUS_FLAG_TEXT[series.latest_status]}", className=flag_class))
    latest_children.extend(condition_readings(series, condition_effects))

    head = [html.H2(series.name)]
    if series.units:
        head.append(html.Span(series.units, className="units"))
    head.append(html.Span(latest_children, className="latest"))
    head.append(
        html.Button(
            [html.Span("＋", className="add-icon"), "Add data"],
            id={"type": "card-add", "index": series.name},
            className="card-add",
            n_clicks=0,
            title=f"Add a result to {series.name}",
        )
    )

    body: list = [html.Div(className="card-head", children=head)]
    if series.description:
        body.append(html.P(series.description, className="card-description"))
    aka = format_synonyms(series.name)
    if aka:
        body.append(html.P(aka, className="card-aka"))

    ref = getattr(series, "reference", None)
    if series.lab_band:
        low, high = series.lab_band
        parts: list = [
            html.Span(f"Range {low:g}–{high:g} {series.units}".strip(), className="range-ref")
        ]
        # The reference is what would apply if these rows carried no range.
        if ref is not None and ref.band and ref.band != series.lab_band:
            parts.append(
                html.Span(f"age/sex reference {describe_reference(ref)}", className="range-lab")
            )
        body.append(html.P(parts, className="card-range"))
    elif ref is not None:
        body.append(
            html.P(
                f"Range {describe_reference(ref)} (age/sex reference)", className="card-range"
            )
        )

    # The text notation accompanies the coloured band rather than replacing it:
    # the colour says where, the words say why, and a reader who cannot
    # distinguish the hues still gets the whole message.
    for applied in condition_effects or []:
        body.append(
            html.P(
                [
                    html.Span(
                        className="condition-dot",
                        style={"background": applied.condition.color},
                    ),
                    html.Span(f"{applied.condition.label}: ", className="condition-name"),
                    applied.note,
                ],
                className="card-condition",
            )
        )

    return html.Div(
        className="chart-card",
        children=[
            *body,
            dcc.Graph(
                figure=make_figure(series, cutoff, condition_effects),
                config={
                    "displaylogo": False,
                    "modeBarButtonsToRemove": ["zoomIn2d", "zoomOut2d", "resetScale2d", "lasso2d", "select2d"],
                },
                style={"height": "280px"},
            ),
        ],
    )


def render_graphs(
    metrics: dict[str, MetricSeries],
    selected: list[str],
    cutoff: pd.Timestamp | None,
    conditions_selected: list[str] | None = None,
) -> list[html.Div]:
    """Chart cards for the selected metric names, in the given order."""
    return [
        chart_card(
            metrics[name],
            cutoff,
            effects_for(name, metrics[name].units, conditions_selected),
        )
        for name in selected
        if name in metrics
    ]


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
            # Cell selection and the active cell. Checkbox-selected *rows* are
            # styled in theme.py — Dash's `state` keys do not cover them.
            {"if": {"state": "selected"}, "border": "none"},
            {"if": {"state": "active"}, "border": "none"},
        ],
    )


def ai_pane() -> html.Aside:
    """Right-hand pane: index of session analyses over the active one."""
    return html.Aside(
        id="ai-pane",
        className="ai-pane",
        style={"display": "none"},
        children=[
            html.Div(
                className="ai-pane-head",
                children=[
                    html.Span("✦", className="ai-icon"),
                    html.Span("AI analysis", className="ai-pane-title"),
                    html.Button(
                        "Export all",
                        id="ai-export",
                        className="link-button ai-pane-action",
                        n_clicks=0,
                        title="Download every analysis in this session as markdown",
                    ),
                    html.Button(
                        "✕",
                        id="ai-close",
                        className="icon-button",
                        n_clicks=0,
                        title="Close the analysis pane",
                    ),
                ],
            ),
            html.Div(id="ai-index", className="ai-index"),
            # The request can run for tens of seconds; without this the pane
            # looks idle and invites clicks mid-flight.
            dcc.Loading(
                id="ai-loading",
                type="dot",
                color=theme.SERIES,
                children=html.Div(id="ai-pane-body", className="ai-pane-body"),
            ),
        ],
    )


def index_row(entry: dict, active_id: str | None, current_key: str | None) -> html.Div:
    """One row in the analyses index."""
    classes = ["ai-index-row"]
    if entry["id"] == active_id:
        classes.append("is-active")
    tags = [f"{entry['count']} metric(s)", window_label(entry.get("window")), entry.get("created", "")]
    if current_key is not None and entry.get("key") == current_key:
        tags.append("current selection")
    return html.Div(
        className=" ".join(classes),
        children=html.Button(
            id={"type": "ai-index-item", "index": entry["id"]},
            className="ai-index-button",
            n_clicks=0,
            children=[
                html.Span(entry["label"], className="ai-index-label"),
                html.Span(" · ".join(t for t in tags if t), className="ai-index-meta"),
            ],
        ),
    )


def render_index(
    entries: list[dict] | None, active_id: str | None, current_key: str | None
) -> list:
    """The index list, newest analysis first."""
    entries = entries or []
    if not entries:
        return []
    return [
        html.Div("This session", className="ai-index-heading"),
        *[index_row(e, active_id, current_key) for e in entries],
    ]


def render_analysis(entry: dict | None) -> list:
    """The active analysis body, with a copy control."""
    if entry is None:
        return [
            html.P(
                "Select an analysis from the list, or run a new one.",
                className="empty-note",
            )
        ]
    return [
        html.Div(
            className="ai-body-head",
            children=[
                html.Span(entry["label"], className="ai-body-title"),
                dcc.Clipboard(
                    target_id="ai-body-text",
                    className="copy-button",
                    title="Copy this analysis",
                ),
            ],
        ),
        html.Div(
            id="ai-body-text",
            className="ai-body-text",
            children=dcc.Markdown(entry.get("text", "")),
        ),
    ]


def ai_error(message: str) -> list:
    """Error state shown inside the pane body."""
    return [
        html.Div(
            className="ai-body-head",
            children=html.Span("Analysis unavailable", className="ai-body-title is-error"),
        ),
        html.P(message, className="empty-note"),
    ]


def entry_dialog(metric_names: list[str]) -> html.Div:
    """Manual measurement entry.

    The metric is chosen inside the dialog rather than required beforehand:
    gating the button on "exactly one selected" left it disabled and faint on
    load, which read as the feature being absent.
    """
    return html.Div(
        id="entry-modal",
        className="modal-backdrop",
        style={"display": "none"},
        children=html.Div(
            className="modal-card",
            children=[
                html.P("Add a result", className="entry-eyebrow"),
                html.Div(
                    className="entry-picker",
                    children=[
                        html.Label("Metric", className="control-label", htmlFor="entry-metric-select"),
                        dcc.Dropdown(
                            id="entry-metric-select",
                            options=[{"label": n, "value": n} for n in metric_names],
                            placeholder="Choose a metric…",
                            clearable=False,
                            optionHeight=44,
                        ),
                    ],
                ),
                html.H2(id="entry-metric", className="entry-metric"),
                html.P(id="entry-units", className="entry-units"),
                html.P(id="entry-description", className="entry-description"),
                html.P(id="entry-aka", className="entry-aka"),
                html.Div(
                    className="entry-fields",
                    children=[
                        html.Div(
                            [
                                html.Label("Date", className="control-label", htmlFor="entry-date"),
                                # with_portal opens the calendar as a centred
                                # overlay: it reads as a picker rather than a
                                # text field, and cannot be clipped by the
                                # dialog it sits inside.
                                dcc.DatePickerSingle(
                                    id="entry-date",
                                    display_format="MMM D, YYYY",
                                    placeholder="Pick a date",
                                    className="entry-date",
                                    with_portal=True,
                                    clearable=True,
                                    max_date_allowed=date.today(),
                                    initial_visible_month=date.today(),
                                ),
                            ]
                        ),
                        html.Div(
                            [
                                html.Label("Value", className="control-label", htmlFor="entry-value"),
                                dcc.Input(
                                    id="entry-value",
                                    className="search-input",
                                    type="number",
                                    debounce=False,
                                    placeholder="e.g. 4.6",
                                ),
                            ]
                        ),
                    ],
                ),
                html.Div(
                    className="entry-fields entry-range",
                    children=[
                        html.Div(
                            [
                                html.Label("Units", className="control-label", htmlFor="entry-units-input"),
                                dcc.Input(id="entry-units-input", className="search-input", type="text"),
                            ]
                        ),
                        html.Div(
                            [
                                html.Label("Normal range", className="control-label"),
                                html.Div(
                                    className="range-pair",
                                    children=[
                                        dcc.Input(
                                            id="entry-range-low", className="search-input",
                                            type="number", placeholder="low",
                                        ),
                                        html.Span("to", className="range-sep"),
                                        dcc.Input(
                                            id="entry-range-high", className="search-input",
                                            type="number", placeholder="high",
                                        ),
                                    ],
                                ),
                            ]
                        ),
                    ],
                ),
                html.P(
                    "Pre-filled from the age and sex reference. Change it only if your "
                    "lab report says something different.",
                    className="entry-hint",
                ),
                html.P(id="entry-error", className="entry-error"),
                html.Div(
                    className="modal-actions",
                    children=[
                        html.Button("Cancel", id="entry-cancel", className="modal-button", n_clicks=0),
                        html.Button(
                            "Save result",
                            id="entry-save",
                            className="modal-button modal-button-primary",
                            n_clicks=0,
                        ),
                    ],
                ),
            ],
        ),
    )


def upload_dialog() -> html.Div:
    """Import a CSV. Nothing is written until the preview is confirmed."""
    return html.Div(
        id="upload-modal",
        className="modal-backdrop",
        style={"display": "none"},
        children=html.Div(
            className="modal-card modal-wide",
            children=[
                html.P("Import results", className="entry-eyebrow"),
                html.H2("Upload a lab CSV", className="entry-metric"),
                html.P(
                    "Columns are worked out from the file. A result for a test and date "
                    "you already have is replaced by the uploaded one.",
                    className="entry-description",
                ),
                dcc.Upload(
                    id="upload-csv",
                    className="upload-drop",
                    multiple=False,
                    children=html.Div(["Drop a CSV here, or ", html.Span("browse", className="upload-link")]),
                ),
                html.Div(id="upload-preview", className="upload-preview"),
                html.P(id="upload-error", className="entry-error"),
                html.Div(
                    className="modal-actions",
                    children=[
                        html.Button("Cancel", id="upload-cancel", className="modal-button", n_clicks=0),
                        html.Button(
                            "Import", id="upload-confirm",
                            className="modal-button modal-button-primary", n_clicks=0, disabled=True,
                        ),
                    ],
                ),
            ],
        ),
    )


def render_upload_preview(plan) -> list:
    """What the import would do, before it does it."""
    mapped = ", ".join(f"{k} ← {v}" for k, v in plan.mapping.items())
    summary = [
        html.Div(
            className="upload-counts",
            children=[
                html.Span(f"{len(plan.added)} added", className="count-add"),
                html.Span(f"{len(plan.replaced)} replaced", className="count-replace"),
                html.Span(f"{plan.skipped} skipped", className="count-skip"),
            ],
        ),
        html.P(f"Columns read as: {mapped}", className="upload-mapping"),
    ]
    if plan.replaced:
        summary.append(html.P("Replacing:", className="upload-subhead"))
        summary.append(
            html.Ul(
                [
                    html.Li(f"{c.test} · {c.date} · {c.replaced} → {c.value}")
                    for c in plan.replaced[:8]
                ]
                + ([html.Li(f"…and {len(plan.replaced) - 8} more")] if len(plan.replaced) > 8 else [])
            )
        )
    if plan.added:
        summary.append(html.P("Adding:", className="upload-subhead"))
        summary.append(
            html.Ul(
                [html.Li(f"{c.test} · {c.date} · {c.value}") for c in plan.added[:8]]
                + ([html.Li(f"…and {len(plan.added) - 8} more")] if len(plan.added) > 8 else [])
            )
        )
    return summary


def cleanup_dialog() -> html.Div:
    """Repair the labs CSV. Nothing is written until the report is confirmed."""
    return html.Div(
        id="cleanup-modal",
        className="modal-backdrop",
        style={"display": "none"},
        children=html.Div(
            className="modal-card modal-wide",
            children=[
                html.P("Maintenance", className="entry-eyebrow"),
                html.H2("Clean up data", className="entry-metric"),
                html.P(
                    "Checks every row for duplicates, values and ranges broken by a "
                    "thousands separator, and missing or contradictory units. Nothing "
                    "is changed until you confirm, and the file is backed up first.",
                    className="entry-description",
                ),
                html.Div(id="cleanup-report", className="upload-preview"),
                html.P(id="cleanup-error", className="entry-error"),
                html.Div(
                    className="modal-actions",
                    children=[
                        html.Button("Cancel", id="cleanup-cancel", className="modal-button", n_clicks=0),
                        html.Button(
                            "Apply fixes", id="cleanup-confirm",
                            className="modal-button modal-button-primary", n_clicks=0, disabled=True,
                        ),
                    ],
                ),
            ],
        ),
    )


def render_cleanup_preview(plan) -> list:
    """What the cleanup would repair, grouped by kind, before it repairs it."""
    from .cleanup import KIND_LABELS

    grouped = plan.by_kind()
    if not grouped:
        return [
            html.P(
                f"Nothing to fix — all {plan.scanned} rows look sound.",
                className="cleanup-clean",
            )
        ]

    report: list = [
        html.Div(
            className="upload-counts",
            children=[
                html.Span(f"{plan.total} to fix", className="count-replace"),
                html.Span(f"{plan.scanned} rows scanned", className="count-skip"),
            ],
        )
    ]
    for kind, issues in grouped.items():
        # Unreadable rows are reported so they are not a surprise, but they are
        # not repaired, so the heading has to say so rather than imply a fix.
        report.append(
            html.P(f"{KIND_LABELS[kind]} ({len(issues)})", className="upload-subhead")
        )
        report.append(
            html.Ul(
                [html.Li(f"{i.test} · {i.date} · {i.detail}") for i in issues[:8]]
                + ([html.Li(f"…and {len(issues) - 8} more")] if len(issues) > 8 else [])
            )
        )
    return report


def consent_dialog(model_name: str) -> html.Div:
    """First-run confirmation before any lab values leave the machine."""
    return html.Div(
        id="ai-consent-modal",
        className="modal-backdrop",
        style={"display": "none"},
        children=html.Div(
            className="modal-card",
            children=[
                html.H2("Share your health data?"),
                html.P(
                    [
                        "The selected lab results — values, dates, and reference "
                        "ranges — will be sent to ",
                        html.Strong(model_name),
                        " to generate the commentary.",
                    ]
                ),
                html.P(
                    "Nothing is sent until you agree, and only the metrics you selected go.",
                    className="modal-note",
                ),
                dcc.Checklist(
                    id="consent-remember",
                    className="modal-remember",
                    options=[{"label": "Don't ask again", "value": "on"}],
                    value=[],
                ),
                html.Div(
                    className="modal-actions",
                    children=[
                        html.Button("No", id="consent-no", className="modal-button", n_clicks=0),
                        html.Button(
                            "Yes, send",
                            id="consent-yes",
                            className="modal-button modal-button-primary",
                            n_clicks=0,
                        ),
                    ],
                ),
            ],
        ),
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
                className="profile-row",
                children=[
                    html.Div(
                        [
                            html.Label("Age", className="control-label", htmlFor="profile-age"),
                            dcc.Input(
                                id="profile-age", className="search-input", type="number",
                                min=0, max=120, step=1, debounce=True,
                            ),
                        ]
                    ),
                    html.Div(
                        [
                            html.Label("Sex", className="control-label"),
                            dcc.RadioItems(
                                id="profile-sex",
                                className="sex-pills",
                                options=[
                                    {"label": "Male", "value": "male"},
                                    {"label": "Female", "value": "female"},
                                ],
                                inline=True,
                            ),
                        ]
                    ),
                ],
            ),
            html.P(
                profile_scope_note(metrics),
                id="profile-scope",
                className="profile-hint",
                title="These settings only apply where your lab printed no range",
            ),
            html.Div(
                className="conditions-block",
                children=[
                    html.Label("Relevant conditions", className="control-label"),
                    dcc.Checklist(
                        id="conditions-select",
                        className="conditions-list",
                        # Alphabetical to start; a callback re-sorts on every
                        # tick so the selected ones lead.
                        options=condition_options(),
                        value=[],
                        labelClassName="conditions-item",
                    ),
                    html.P(
                        "Draws an extra range where a benign condition explains "
                        "a result. The normal range and the out-of-range flags "
                        "do not change.",
                        className="profile-hint",
                    ),
                ],
            ),
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
                    options=[{"label": "Out of range in recent bloodwork", "value": "on"}],
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
            html.Button(
                [html.Span("＋", className="add-icon"), "Add a result"],
                id="entry-open-sidebar",
                className="sidebar-add",
                n_clicks=0,
                title="Record a new lab result",
            ),
            metric_table(table_rows, initial_selection),
        ],
    )

    content = html.Section(
        className="content-area",
        children=[
            dcc.Store(id="selection-store", data=initial_selection),
            # Consent outlives the tab; analyses last the session; the run
            # counter is per-page.
            dcc.Store(id="ai-consent-store", storage_type="local"),
            dcc.Store(id="ai-analyses", storage_type="session", data=[]),
            dcc.Store(id="ai-active", storage_type="session"),
            dcc.Store(id="ai-visible", storage_type="session", data=False),
            dcc.Store(id="ai-run-count", data=0),
            dcc.Store(id="ai-last-run", data=0),
            # Bumped when a manual entry lands, so the table, tiles and charts
            # re-read the reloaded data.
            dcc.Store(id="data-version", data=0),
            dcc.Store(id="upload-plan"),
            dcc.Store(id="cleanup-plan"),
            dcc.Download(id="ai-download"),
            dcc.Download(id="metrics-download"),
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
                        [html.Span("＋", className="add-icon"), "Add data"],
                        id="entry-open",
                        className="add-button",
                        n_clicks=0,
                    ),
                    html.Button(
                        [html.Span("↑", className="add-icon"), "Import CSV"],
                        id="upload-open",
                        className="add-button add-button-quiet",
                        n_clicks=0,
                    ),
                    html.Button(
                        [html.Span("✓", className="add-icon"), "Clean up data"],
                        id="cleanup-open",
                        className="add-button add-button-quiet",
                        n_clicks=0,
                    ),
                    html.Button(
                        [html.Span("✦", className="ai-icon"), "Analysis with AI"],
                        id="ai-analyze",
                        className="ai-button",
                        n_clicks=0,
                    ),
                ],
            ),
            html.Div(
                id="split-pane",
                className="split-pane",
                children=[
                    html.Div(
                        className="graphs-column",
                        children=[
                            condition_legend([]),
                            html.Div(
                                id="graphs-container",
                                className="graphs-grid",
                                children=render_graphs(metrics, initial_selection, None),
                            ),
                        ],
                    ),
                    ai_pane(),
                ],
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
                    html.Button(
                        # ↓ rather than a download glyph: U+2B73 and friends
                        # have no coverage in the system font and render as
                        # tofu. This matches the ▲▼● already used elsewhere.
                        [html.Span("↓", className="export-icon"), "Export CSV"],
                        id="export-csv",
                        className="export-button",
                        n_clicks=0,
                    ),
                ],
            ),
            html.Div(className="app-shell", children=[sidebar, content]),
            consent_dialog(configured_model_name()),
            entry_dialog(sorted(metrics)),
            upload_dialog(),
            cleanup_dialog(),
        ]
    )
