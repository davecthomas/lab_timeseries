"""Plotly figure construction for metric time series."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from . import theme
from .data import STATUS_HIGH, STATUS_LOW, MetricSeries

STATUS_HOVER = {STATUS_LOW: "Below range", STATUS_HIGH: "Above range"}
STATUS_SYMBOL = {STATUS_LOW: "triangle-down", STATUS_HIGH: "triangle-up"}


def filter_window(series: MetricSeries, cutoff: pd.Timestamp | None) -> list[int]:
    """Indices of points at or after the cutoff (all points when cutoff is None)."""
    if cutoff is None:
        return list(range(len(series.dates)))
    return [i for i, d in enumerate(series.dates) if d >= cutoff]


def label_with_units(display: str, units: str) -> str:
    """Add units to a display value, unless the source string already carries them."""
    if not units:
        return display
    if display.strip().casefold().endswith(units.strip().casefold()):
        return display
    return f"{display} {units}"


def make_figure(series: MetricSeries, cutoff: pd.Timestamp | None = None) -> go.Figure:
    """Build a themed time-series figure with the normal band and range flags."""
    idx = filter_window(series, cutoff)
    dates = [series.dates[i] for i in idx]
    values = [series.values[i] for i in idx]
    displays = [series.display_values[i] for i in idx]
    statuses = [series.status_of(v) for v in values]

    fig = go.Figure()

    if series.band is not None:
        low, high = series.band
        fig.add_hrect(
            y0=low,
            y1=high,
            fillcolor=theme.STATUS_GOOD,
            opacity=0.10,
            line_width=0,
        )

    labels = [label_with_units(d, series.units) for d in displays]
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=values,
            mode="lines+markers",
            line={"color": theme.SERIES, "width": 2, "shape": "linear"},
            marker={
                "size": 8,
                "color": theme.SERIES,
                "line": {"color": theme.SURFACE, "width": 2},
            },
            customdata=labels,
            hovertemplate="<b>%{customdata}</b><br>%{x|%b %d, %Y}<extra></extra>",
            showlegend=False,
        )
    )

    flagged = [
        (d, v, label, s)
        for d, v, label, s in zip(dates, values, labels, statuses)
        if s in STATUS_HOVER
    ]
    if flagged:
        fig.add_trace(
            go.Scatter(
                x=[f[0] for f in flagged],
                y=[f[1] for f in flagged],
                mode="markers",
                marker={
                    "size": 11,
                    "color": theme.STATUS_CRITICAL,
                    "symbol": [STATUS_SYMBOL[f[3]] for f in flagged],
                    "line": {"color": theme.SURFACE, "width": 2},
                },
                customdata=[[f[2], STATUS_HOVER[f[3]]] for f in flagged],
                hovertemplate=(
                    "<b>%{customdata[0]}</b> · %{customdata[1]}"
                    "<br>%{x|%b %d, %Y}<extra></extra>"
                ),
                showlegend=False,
            )
        )

    if not dates:
        fig.add_annotation(
            text="No results in this window",
            showarrow=False,
            font={"color": theme.INK_MUTED, "size": 13},
        )

    # A lone point makes Plotly zoom to a sub-second axis; pad it to a year
    xaxis_range = None
    if len(dates) == 1:
        xaxis_range = [dates[0] - pd.DateOffset(months=6), dates[0] + pd.DateOffset(months=6)]

    fig.update_layout(
        margin={"l": 48, "r": 16, "t": 12, "b": 40},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": theme.INK_SECONDARY, "family": theme.FONT_STACK, "size": 12},
        hoverlabel={
            "bgcolor": theme.TOOLTIP_BG,
            "bordercolor": theme.SERIES,
            "font": {"color": theme.TOOLTIP_INK, "size": 13, "family": theme.FONT_STACK},
        },
        hovermode="closest",
        xaxis={
            "range": xaxis_range,
            "gridcolor": theme.GRIDLINE,
            "griddash": "solid",
            "gridwidth": 1,
            "linecolor": theme.BASELINE,
            "tickfont": {"size": 11, "color": theme.INK_SECONDARY},
        },
        yaxis={
            "title": {
                "text": series.units or None,
                "font": {"size": 11, "color": theme.INK_SECONDARY},
            },
            "gridcolor": theme.GRIDLINE,
            "griddash": "solid",
            "gridwidth": 1,
            "linecolor": theme.BASELINE,
            "tickfont": {"size": 11, "color": theme.INK_SECONDARY},
            "zeroline": False,
        },
    )
    return fig
