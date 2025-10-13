from __future__ import annotations

import argparse
import logging
import os
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, dcc, exceptions, html, dash_table

# Global configuration for loading assets and styling
EXTERNAL_STYLESHEETS = [
    "https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css",
    "https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap",
]
INDEX_STYLE = """
:root {
    color-scheme: light;
}
body {
    margin: 0;
    background: linear-gradient(160deg, #0f172a 0%, #1f2937 60%, #111827 100%);
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    color: #f8fafc;
}
.app-shell {
    display: flex;
    min-height: 100vh;
}
.sidebar {
    width: 380px;
    padding: 2.5rem 2rem;
    backdrop-filter: blur(14px);
    background: rgba(15, 23, 42, 0.68);
    border-right: 1px solid rgba(148, 163, 184, 0.25);
    box-shadow: inset -1px 0 0 rgba(15, 23, 42, 0.3);
}
.sidebar h1 {
    font-size: 1.8rem;
    font-weight: 700;
    margin-bottom: 0.75rem;
    letter-spacing: -0.01em;
}
.sidebar p {
    font-size: 0.85rem;
    color: rgba(203, 213, 225, 0.85);
    margin-bottom: 1.5rem;
}
.selector-card {
    background: rgba(30, 41, 59, 0.7);
    padding: 1.25rem;
    border-radius: 1.1rem;
    border: 1px solid rgba(148, 163, 184, 0.25);
    box-shadow: 0 15px 35px rgba(15, 23, 42, 0.35);
}
.content-area {
    flex: 1;
    padding: 2.5rem 3rem;
    display: flex;
    flex-direction: column;
    gap: 1.75rem;
}
.graphs-grid {
    display: grid;
    gap: 2rem;
}
.chart-card {
    background: rgba(15, 23, 42, 0.68);
    border-radius: 1.2rem;
    padding: 1.75rem;
    border: 1px solid rgba(148, 163, 184, 0.25);
    box-shadow: 0 20px 45px rgba(15, 23, 42, 0.45);
}
.chart-card h2 {
    margin: 0 0 1rem 0;
    font-size: 1.2rem;
    font-weight: 600;
    letter-spacing: -0.01em;
}
.metric-dropdown .Select-control,
.metric-dropdown .Select__control {
    background: rgba(15, 23, 42, 0.8);
    border-color: rgba(148, 163, 184, 0.35);
    color: #f8fafc;
}
.metric-dropdown .Select-menu,
.metric-dropdown .Select__menu {
    background: rgba(15, 23, 42, 0.95);
    border-radius: 0.9rem;
    border: 1px solid rgba(148, 163, 184, 0.25);
}
.metric-dropdown .Select-option,
.metric-dropdown .Select__option {
    background: transparent;
}
.metric-dropdown .Select-option.is-selected,
.metric-dropdown .Select-option.is-focused,
.metric-dropdown .Select__option--is-selected,
.metric-dropdown .Select__option--is-focused {
    background: rgba(56, 189, 248, 0.2);
    color: #38bdf8;
}
@media (max-width: 1200px) {
    .app-shell {
        flex-direction: column;
    }
    .sidebar {
        width: 100%;
        border-right: none;
        border-bottom: 1px solid rgba(148, 163, 184, 0.25);
    }
    .content-area {
        padding: 2rem 1.5rem 3rem;
    }
}
"""


INITIAL_METRIC_COUNT = 10

logger = logging.getLogger("lab_timeseries_grapher")


# ---------- helpers ----------


def coerce_float(x) -> Optional[float]:
    """Try to coerce a cell to float; return None if impossible."""
    if pd.isna(x):
        return None
    s = str(x).strip()
    if s.lower() in {"n/a", "na", "nan", ""}:
        return None
    s = s.replace(",", "")  # remove thousands separators like "3,457"
    try:
        return float(s)
    except Exception:
        return None


def most_common_range(
    low_series: pd.Series, high_series: pd.Series
) -> Optional[Tuple[float, float]]:
    """
    Choose a representative normal range for a test.

    Strategy:
      1) Mode of (low, high) pairs among rows where BOTH are numeric.
      2) If no clear mode, use median(low), median(high) across numeric rows.
    """
    lows = [coerce_float(v) for v in low_series]
    highs = [coerce_float(v) for v in high_series]
    pairs = [(l, h) for l, h in zip(lows, highs) if l is not None and h is not None]

    if pairs:
        counts = Counter(pairs)
        pair, freq = counts.most_common(1)[0]
        # If dominant or only one pair, take it
        if freq >= 2 or len(counts) == 1:
            return float(pair[0]), float(pair[1])

    numeric_lows = [v for v in lows if v is not None]
    numeric_highs = [v for v in highs if v is not None]
    if numeric_lows and numeric_highs:
        return float(np.nanmedian(numeric_lows)), float(np.nanmedian(numeric_highs))

    return None


def mode_units(series: pd.Series) -> str:
    """Return the most common non-empty/non-'n/a' units string for a test."""
    vals = [str(u).strip() for u in series if str(u).strip().lower() not in {"", "n/a"}]
    if not vals:
        return ""
    return Counter(vals).most_common(1)[0][0]


def prepare_tests(df: pd.DataFrame) -> Dict[str, Dict[str, object]]:
    """Return a dictionary keyed by test name with cleaned time-series data."""
    tests: Dict[str, Dict[str, object]] = {}
    for test_name, sub in df.groupby("Test Name"):
        dfp = sub.copy()
        dfp["Date_parsed"] = pd.to_datetime(dfp["Date"], errors="coerce")
        dfp["Value_Num"] = dfp["Value_Numeric"].apply(coerce_float)
        dfp = dfp.dropna(subset=["Date_parsed", "Value_Num"]).sort_values("Date_parsed")

        if dfp.empty:
            logger.debug("Skipping test '%s': no valid parsed rows remain after cleanup", test_name)
            continue

        last_date = dfp["Date_parsed"].max()
        tests[test_name] = {
            "dates": dfp["Date_parsed"].tolist(),
            "values": dfp["Value_Num"].astype(float).tolist(),
            "band": most_common_range(dfp["Range_Low"], dfp["Range_High"]),
            "units": mode_units(dfp["Units"]),
            "last_date": last_date,
        }

        logger.debug(
            "Prepared test '%s' with %d points%s (last: %s)",
            test_name,
            len(tests[test_name]["dates"]),  # type: ignore[index]
            "" if tests[test_name]["band"] else " (no band)",
            last_date.strftime("%Y-%m-%d") if isinstance(last_date, pd.Timestamp) else "n/a",
        )
    return tests


def make_figure(test_name: str, payload: Dict[str, object]) -> go.Figure:
    """Create a Plotly figure for a lab test with a translucent normal band."""
    dates: List[pd.Timestamp] = payload["dates"]  # type: ignore[assignment]
    values: List[float] = payload["values"]  # type: ignore[assignment]
    band: Optional[Tuple[float, float]] = payload["band"]  # type: ignore[assignment]
    units: str = payload["units"]  # type: ignore[assignment]

    fig = go.Figure()
    if band is not None:
        low, high = band
        fig.add_trace(
            go.Scatter(
                x=dates + dates[::-1],
                y=[high] * len(dates) + [low] * len(dates),
                fill="toself",
                fillcolor="rgba(94, 234, 212, 0.18)",
                line=dict(color="rgba(0,0,0,0)"),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    fig.add_trace(
        go.Scatter(
            x=dates,
            y=values,
            mode="lines+markers",
            line=dict(color="#38bdf8", width=3),
            marker=dict(size=9, color="#0ea5e9", line=dict(color="#e0f2fe", width=1)),
            hovertemplate="<b>%{y:.2f}</b><br>%{x|%b %d, %Y}<extra></extra>",
            showlegend=False,
        )
    )

    title = test_name
    if units and units.lower() not in {"n/a", "unitless"}:
        title = f"{title} · {units}"

    fig.update_layout(
        title=dict(text=title, x=0.0, font=dict(size=20, family="Inter")),
        margin=dict(l=40, r=24, t=60, b=50),
        paper_bgcolor="rgba(15, 23, 42, 0)",
        plot_bgcolor="rgba(15, 23, 42, 0.55)",
        font=dict(color="#f8fafc"),
        xaxis=dict(
            title=dict(text="Date", font=dict(size=14)),
            gridcolor="rgba(148, 163, 184, 0.18)",
            tickfont=dict(size=12),
        ),
        yaxis=dict(
            title=dict(text="Value", font=dict(size=14)),
            gridcolor="rgba(148, 163, 184, 0.18)",
            tickfont=dict(size=12),
            zeroline=False,
        ),
    )
    return fig


def resolve_csv_path(csv_arg: str) -> Path:
    """
    Resolve the CSV path relative to the project /data directory.

    Accepts an absolute path or a filename. Filenames are looked up under the
    project's data directory.
    """
    raw = Path(csv_arg)
    if raw.is_absolute() and raw.exists():
        return raw

    project_root = Path(__file__).resolve().parents[2]
    data_dir = project_root / "data"
    candidate = data_dir / raw.name
    return candidate


def configure_logging(log_level: str) -> None:
    """Configure root logging once."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    if logging.getLogger().handlers:
        logging.getLogger().setLevel(level)
        return

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    logger.debug("Logging initialised at %s level", log_level.upper())


def load_dataframe(csv_path: Path) -> pd.DataFrame:
    """Read the CSV file with defensive checks."""
    try:
        df = pd.read_csv(csv_path, dtype=str)
    except FileNotFoundError:
        logger.error("CSV not found at %s", csv_path)
        raise
    except pd.errors.EmptyDataError as exc:
        logger.error("CSV at %s is empty", csv_path)
        raise SystemExit("Input CSV is empty.") from exc
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Unexpected error reading CSV %s", csv_path)
        raise SystemExit(f"Failed to read CSV: {exc}") from exc

    logger.info("Loaded CSV %s with %d rows and %d columns", csv_path, df.shape[0], df.shape[1])
    return df.fillna("n/a")


# ---------- main ----------


def main():
    ap = argparse.ArgumentParser(
        description="Plot per-test time series with green normal bands"
    )
    ap.add_argument("--csv", default="labs_results.csv", help="CSV filename or path to load")
    ap.add_argument("--host", default="127.0.0.1", help="Host interface for the web server")
    ap.add_argument("--port", type=int, default=8050, help="Port for the web server")
    ap.add_argument("--debug", action="store_true", help="Run Dash in debug mode")
    ap.add_argument(
        "--log-level",
        default=os.getenv("LAB_TS_LOG_LEVEL", "INFO"),
        help="Python logging level (e.g. DEBUG, INFO, WARNING)",
    )
    args = ap.parse_args()

    configure_logging(args.log_level)

    csv_path = resolve_csv_path(args.csv)
    if not csv_path.exists():
        logger.error("CSV not found at resolved path %s", csv_path)
        raise SystemExit(f"CSV not found at {csv_path}. Expected inside the /data directory.")

    logger.info("Resolved CSV path: %s", csv_path)

    df = load_dataframe(csv_path)

    # Minimal schema validation
    required = [
        "Date",
        "Test Name",
        "Value_Numeric",
        "Units",
        "Range_Low",
        "Range_High",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        logger.error("CSV missing required columns: %s", missing)
        raise SystemExit(f"Missing required columns: {missing}")

    prepared = prepare_tests(df)
    if not prepared:
        logger.error("CSV yielded no plottable rows after preprocessing")
        raise SystemExit("No plottable rows were found in the CSV.")

    sorted_metrics = sorted(
        prepared.items(),
        key=lambda kv: (
            kv[1].get("last_date") if isinstance(kv[1].get("last_date"), pd.Timestamp) else pd.Timestamp.min
        ),
        reverse=True,
    )
    logger.info("Prepared %d metrics for display", len(sorted_metrics))

    table_rows = []
    for metric, payload in sorted_metrics:
        last_date: Optional[pd.Timestamp] = payload.get("last_date")  # type: ignore[assignment]
        table_rows.append(
            {
                "id": metric,
                "name": metric,
                "last_date_display": last_date.strftime("%m/%y") if isinstance(last_date, pd.Timestamp) else "—",
                "last_date_sort": last_date.strftime("%Y-%m-%d") if isinstance(last_date, pd.Timestamp) else "",
            }
        )

    initial_selection_ids = [row["id"] for row in table_rows[:INITIAL_METRIC_COUNT]]
    if not initial_selection_ids:
        initial_selection_ids = [row["id"] for row in table_rows]

    app = Dash(__name__, external_stylesheets=EXTERNAL_STYLESHEETS)
    app.title = "Lab Metrics • Time Series Explorer"
    app.index_string = (
        "<!DOCTYPE html>"
        "<html>"
        "<head>"
        "{%metas%}"
        "<title>{%title%}</title>"
        "{%favicon%}"
        "{%css%}"
        f"<style>{INDEX_STYLE}</style>"
        "</head>"
        "<body>"
        "{%app_entry%}"
        "<footer>{%config%}{%scripts%}{%renderer%}</footer>"
        "</body>"
        "</html>"
    )

    def render_graphs(selected: List[str]) -> List[html.Div]:
        cards: List[html.Div] = []
        for metric in selected:
            dataset = prepared.get(metric)
            if dataset is None:
                logger.warning("Requested metric '%s' missing from prepared dataset", metric)
                continue
            cards.append(
                html.Div(
                    className="chart-card",
                    children=[
                        html.H2(metric),
                        dcc.Graph(
                            figure=make_figure(metric, dataset),
                            config={
                                "displaylogo": False,
                                "modeBarButtonsToRemove": ["zoomIn2d", "zoomOut2d", "resetScale2d"],
                            },
                            style={"height": "25vh", "minHeight": "240px"},
                        ),
                    ],
                )
            )
        return cards

    app.layout = html.Div(
        className="app-shell",
        children=[
            html.Aside(
                className="sidebar",
                children=[
                    html.H1("Lab Metrics Explorer"),
                    html.P(
                        "Select one or more metrics to explore richly styled, interactive time series charts."
                    ),
                    html.Div(
                        className="selector-card",
                        children=[
                            html.Label("Metrics"),
                            dash_table.DataTable(
                                id="metric-table",
                                columns=[
                                    {"name": "Date", "id": "last_date_display"},
                                    {"name": "Metric", "id": "name"},
                                    {"name": "_sort", "id": "last_date_sort"},
                                ],
                                data=table_rows,
                                hidden_columns=["last_date_sort"],
                                row_selectable="multi",
                                selected_row_ids=initial_selection_ids,
                                sort_action="native",
                                sort_mode="single",
                                sort_by=[{"column_id": "last_date_sort", "direction": "desc"}],
                                style_as_list_view=True,
                                css=[{"selector": ".dash-spreadsheet-menu", "rule": "display: none;"}],
                                style_table={"maxHeight": "70vh", "overflowY": "auto"},
                                style_header={
                                    "background": "rgba(148, 163, 184, 0.12)",
                                    "fontWeight": "600",
                                    "color": "#e2e8f0",
                                    "border": "none",
                                    "fontFamily": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
                                    "fontSize": "0.8rem",
                                    "letterSpacing": "0.05em",
                                },
                                style_cell={
                                    "background": "transparent",
                                    "border": "none",
                                    "color": "#f8fafc",
                                    "padding": "0.5rem 0.7rem",
                                    "fontSize": "0.85rem",
                                    "fontFamily": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
                                    "letterSpacing": "-0.01em",
                                    "textAlign": "left",
                                },
                                style_data_conditional=[
                                    {
                                        "if": {"state": "selected"},
                                        "background": "#f8fafc",
                                        "color": "#0f172a",
                                    },
                                    {
                                        "if": {"state": "active"},
                                        "background": "rgba(248, 250, 252, 0.75)",
                                        "color": "#0f172a",
                                    },
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            html.Section(
                className="content-area",
                children=[
                    html.Div(
                        id="graphs-container",
                        className="graphs-grid",
                        children=render_graphs(initial_selection_ids),
                    )
                ],
            ),
        ],
    )

    @app.callback(
        Output("graphs-container", "children"),
        Input("metric-table", "derived_virtual_data"),
        Input("metric-table", "selected_row_ids"),
    )
    def update_graphs(
        visible_rows: Optional[List[Dict[str, str]]], selected_row_ids: Optional[List[str]]
    ) -> List[html.Div]:
        data_rows = visible_rows if visible_rows is not None else table_rows

        if not selected_row_ids:
            logger.debug("Metric selection cleared; prompting user for selection")
            return [
                html.Div(
                    className="chart-card",
                    children=[
                        html.H2("Select a metric to begin"),
                        html.P(
                            "Use the sortable metrics table to choose which lab metrics to visualize."
                        ),
                    ],
                )
            ]

        selected_set = set(selected_row_ids)
        ordered_selected = [row["id"] for row in data_rows if row.get("id") in selected_set]

        rendered = render_graphs(ordered_selected)
        if not rendered:
            logger.warning(
                "No graphs could be rendered for selection: %s", ", ".join(selected_row_ids)
            )
        return rendered

    try:
        logger.info("Starting Dash server on %s:%s (debug=%s)", args.host, args.port, args.debug)
        app.run(host=args.host, port=args.port, debug=args.debug)
    except OSError as exc:
        logger.exception("Failed to start Dash server")
        raise SystemExit(f"Could not start the web server: {exc}") from exc
    except exceptions.PreventUpdate:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Unexpected error while running Dash server")
        raise SystemExit(f"Unexpected error while running Dash: {exc}") from exc


if __name__ == "__main__":
    main()
