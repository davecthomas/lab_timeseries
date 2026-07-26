"""Color tokens and page chrome for the dark dashboard theme.

Palette values follow the validated dataviz reference palette (dark mode,
surface #1a1a19). The good/critical pair fails deutan-CVD separation by
design, so status is never carried by color alone: out-of-range points use
triangle markers and text glyphs alongside the color.
"""

from __future__ import annotations

# Surfaces and ink
PAGE_BG = "#0d0d0d"
SURFACE = "#1a1a19"
INK_PRIMARY = "#ffffff"
INK_SECONDARY = "#c3c2b7"
INK_MUTED = "#898781"
GRIDLINE = "#2c2c2a"
BASELINE = "#383835"
BORDER = "rgba(255, 255, 255, 0.10)"

# Hover tooltips: raised surface with white ink. Plotly picks its own label
# colors otherwise, which lands dark-on-dark against this theme.
TOOLTIP_BG = "#33322f"
TOOLTIP_INK = "#ffffff"

# Data colors (validated against the dark surface)
SERIES = "#3987e5"  # categorical slot 1, dark step
STATUS_GOOD = "#0ca30c"
STATUS_CRITICAL = "#d03b3b"

FONT_STACK = "system-ui, -apple-system, 'Segoe UI', sans-serif"

INDEX_STYLE = """
:root {
    color-scheme: dark;
}
* { box-sizing: border-box; }
body {
    margin: 0;
    background: #0d0d0d;
    font-family: system-ui, -apple-system, 'Segoe UI', sans-serif;
    color: #ffffff;
}
.app-header {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 1.5rem 2.5rem;
    padding: 1.25rem 2rem;
    border-bottom: 1px solid #2c2c2a;
    position: sticky;
    top: 0;
    z-index: 20;
    background: #0d0d0d;
}
.app-header h1 {
    font-size: 1.15rem;
    font-weight: 650;
    margin: 0;
    letter-spacing: -0.01em;
}
.app-header .subtitle {
    margin: 0.15rem 0 0;
    font-size: 0.8rem;
    color: #898781;
}
.stat-tiles {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    margin-left: auto;
}
.stat-tile {
    background: #1a1a19;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 12px;
    padding: 0.6rem 1.1rem;
    min-width: 7.5rem;
}
.stat-tile .tile-label {
    font-size: 0.7rem;
    color: #898781;
    margin: 0 0 0.15rem;
}
.stat-tile .tile-value {
    font-size: 1.35rem;
    font-weight: 600;
    margin: 0;
}
.stat-tile .tile-note {
    font-size: 0.7rem;
    color: #898781;
    margin: 0.1rem 0 0;
}
.app-shell {
    display: flex;
    align-items: flex-start;
    min-height: calc(100vh - 4.5rem);
}
.sidebar {
    width: 350px;
    flex-shrink: 0;
    padding: 1.5rem 1.25rem 2rem;
    border-right: 1px solid #2c2c2a;
    display: flex;
    flex-direction: column;
    gap: 0.9rem;
    position: sticky;
    top: 6.5rem;
    max-height: calc(100vh - 6.5rem);
    overflow-y: auto;
}
.selection-actions {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}
.link-button {
    background: none;
    border: none;
    padding: 0;
    font-family: inherit;
    font-size: 0.78rem;
    color: #3987e5;
    cursor: pointer;
    text-decoration: underline;
    text-underline-offset: 2px;
}
.link-button:hover { color: #ffffff; }
.selection-count {
    margin-left: auto;
    font-size: 0.72rem;
    color: #898781;
    font-variant-numeric: tabular-nums;
}
.sidebar .control-label {
    font-size: 0.7rem;
    color: #898781;
    display: block;
    margin-bottom: 0.3rem;
}
.search-input, .Select-control, .Select__control {
    width: 100%;
    background: #1a1a19 !important;
    border: 1px solid rgba(255, 255, 255, 0.10) !important;
    border-radius: 8px;
    color: #ffffff !important;
    font-family: inherit;
    font-size: 0.85rem;
    padding: 0.45rem 0.6rem;
}
.search-input:focus { outline: 1px solid #3987e5; }
.Select-menu-outer, .Select__menu, .VirtualizedSelectOption {
    background: #1a1a19 !important;
    color: #ffffff !important;
    border: 1px solid rgba(255, 255, 255, 0.10);
}
.Select-value-label, .Select__single-value, .Select-placeholder { color: #c3c2b7 !important; }
.VirtualizedSelectFocusedOption { background: rgba(57, 135, 229, 0.2) !important; }
.abnormal-toggle label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.85rem;
    color: #c3c2b7;
    cursor: pointer;
}
.content-area {
    flex: 1;
    min-width: 0;
    padding: 1.5rem 2rem 3rem;
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
}
.filter-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}
.filter-row .control-label { font-size: 0.75rem; color: #898781; }
.range-pills { display: flex; gap: 0.4rem; }
.range-pills label {
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 999px;
    padding: 0.3rem 0.85rem;
    font-size: 0.78rem;
    color: #c3c2b7;
    cursor: pointer;
}
.range-pills input { display: none; }
.range-pills label:has(input:checked) {
    border-color: #3987e5;
    color: #ffffff;
    background: rgba(57, 135, 229, 0.15);
}
.ai-button {
    margin-left: auto;
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    border: 1px solid rgba(57, 135, 229, 0.55);
    border-radius: 999px;
    background: rgba(57, 135, 229, 0.12);
    color: #ffffff;
    font-family: inherit;
    font-size: 0.82rem;
    padding: 0.4rem 1rem;
    cursor: pointer;
}
.ai-button:hover { background: rgba(57, 135, 229, 0.24); }
.ai-button:disabled { opacity: 0.5; cursor: not-allowed; }
.ai-icon { color: #3987e5; font-size: 0.95rem; line-height: 1; }
.ai-panel {
    background: #1a1a19;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-left: 3px solid #3987e5;
    border-radius: 12px;
    padding: 1.1rem 1.35rem;
    font-size: 0.88rem;
    line-height: 1.55;
    color: #c3c2b7;
}
.ai-panel .ai-panel-head {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    font-size: 0.72rem;
    color: #898781;
    margin-bottom: 0.6rem;
}
.ai-panel h2 { font-size: 1rem; color: #ffffff; margin: 1rem 0 0.4rem; }
.ai-panel h3 { font-size: 0.9rem; color: #ffffff; margin: 0.9rem 0 0.3rem; }
.ai-panel p { margin: 0 0 0.6rem; }
.ai-panel ul { margin: 0 0 0.6rem; padding-left: 1.2rem; }
.ai-panel strong { color: #ffffff; }
.ai-panel.ai-error { border-left-color: #d03b3b; }
.modal-backdrop {
    position: fixed;
    inset: 0;
    z-index: 100;
    background: rgba(0, 0, 0, 0.65);
    align-items: center;
    justify-content: center;
    padding: 1.5rem;
}
.modal-card {
    background: #1a1a19;
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 14px;
    padding: 1.5rem 1.6rem 1.25rem;
    max-width: 30rem;
    box-shadow: 0 18px 48px rgba(0, 0, 0, 0.55);
}
.modal-card h2 {
    margin: 0 0 0.7rem;
    font-size: 1.05rem;
    font-weight: 600;
    color: #ffffff;
}
.modal-card p {
    margin: 0 0 0.7rem;
    font-size: 0.88rem;
    line-height: 1.5;
    color: #c3c2b7;
}
.modal-card .modal-note { color: #898781; font-size: 0.8rem; }
.modal-card strong { color: #ffffff; }
.modal-remember label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.82rem;
    color: #c3c2b7;
    cursor: pointer;
    margin: 0.9rem 0 1.1rem;
}
.modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.6rem;
}
.modal-button {
    border: 1px solid rgba(255, 255, 255, 0.18);
    border-radius: 999px;
    background: transparent;
    color: #ffffff;
    font-family: inherit;
    font-size: 0.85rem;
    padding: 0.45rem 1.2rem;
    cursor: pointer;
}
.modal-button:hover { background: rgba(255, 255, 255, 0.08); }
.modal-button-primary {
    border-color: #3987e5;
    background: rgba(57, 135, 229, 0.22);
}
.modal-button-primary:hover { background: rgba(57, 135, 229, 0.36); }
.split-pane {
    display: flex;
    gap: 1.25rem;
    align-items: flex-start;
    min-width: 0;
}
.graphs-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(430px, 1fr));
    gap: 1.25rem;
    flex: 1;
    min-width: 0;
}
/* With the pane open the charts get one column, so both stay readable. */
.split-pane.is-split .graphs-grid {
    grid-template-columns: minmax(0, 1fr);
}
.ai-pane {
    width: 30rem;
    max-width: 42%;
    flex-shrink: 0;
    flex-direction: column;
    background: #1a1a19;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-left: 3px solid #3987e5;
    border-radius: 12px;
    position: sticky;
    top: 6.5rem;
    max-height: calc(100vh - 7.5rem);
    overflow: hidden;
}
.ai-pane-head {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.8rem 0.9rem;
    border-bottom: 1px solid #2c2c2a;
    flex-shrink: 0;
}
.ai-pane-title {
    font-size: 0.78rem;
    color: #c3c2b7;
    letter-spacing: 0.01em;
}
.ai-pane-action { margin-left: auto; font-size: 0.75rem; }
.icon-button {
    background: none;
    border: none;
    color: #898781;
    font-size: 0.95rem;
    line-height: 1;
    padding: 0.15rem 0.3rem;
    cursor: pointer;
    border-radius: 6px;
}
.icon-button:hover { color: #ffffff; background: rgba(255, 255, 255, 0.08); }
.ai-index {
    flex-shrink: 0;
    max-height: 11rem;
    overflow-y: auto;
    border-bottom: 1px solid #2c2c2a;
}
.ai-index:empty { display: none; }
.ai-index-heading {
    font-size: 0.68rem;
    color: #898781;
    padding: 0.5rem 0.9rem 0.2rem;
}
.ai-index-row + .ai-index-row { border-top: 1px solid rgba(255, 255, 255, 0.05); }
.ai-index-button {
    display: block;
    width: 100%;
    text-align: left;
    background: none;
    border: none;
    border-left: 2px solid transparent;
    padding: 0.45rem 0.9rem;
    font-family: inherit;
    cursor: pointer;
}
.ai-index-button:hover { background: rgba(255, 255, 255, 0.05); }
.ai-index-row.is-active .ai-index-button {
    border-left-color: #3987e5;
    background: rgba(57, 135, 229, 0.12);
}
.ai-index-label {
    display: block;
    font-size: 0.82rem;
    color: #ffffff;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.ai-index-meta {
    display: block;
    font-size: 0.7rem;
    color: #898781;
    margin-top: 0.1rem;
}
.ai-pane-body {
    overflow-y: auto;
    padding: 0.9rem 1.1rem 1.2rem;
    font-size: 0.86rem;
    line-height: 1.55;
    color: #c3c2b7;
}
.ai-body-head {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
}
.ai-body-title {
    font-size: 0.8rem;
    color: #ffffff;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.ai-body-title.is-error { color: #d03b3b; }
.copy-button {
    margin-left: auto;
    color: #898781;
    flex-shrink: 0;
}
.copy-button:hover { color: #ffffff; }
.ai-pane-body h2 { font-size: 0.95rem; color: #ffffff; margin: 0.9rem 0 0.35rem; }
.ai-pane-body h3 { font-size: 0.86rem; color: #ffffff; margin: 0.8rem 0 0.3rem; }
.ai-pane-body p { margin: 0 0 0.55rem; }
.ai-pane-body ul { margin: 0 0 0.55rem; padding-left: 1.1rem; }
.ai-pane-body strong { color: #ffffff; }
@media (max-width: 1400px) {
    .split-pane { flex-direction: column; }
    .ai-pane {
        width: 100%;
        max-width: none;
        position: static;
        max-height: none;
        order: -1;
    }
    .ai-pane-body { max-height: 26rem; }
}
.chart-card {
    background: #1a1a19;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 12px;
    padding: 1.1rem 1.25rem 0.75rem;
    min-width: 0;
}
.chart-card .card-head {
    display: flex;
    align-items: baseline;
    gap: 0.6rem;
    flex-wrap: wrap;
    margin-bottom: 0.35rem;
}
.chart-card h2 {
    margin: 0;
    font-size: 0.95rem;
    font-weight: 600;
    letter-spacing: -0.01em;
}
.chart-card .units { font-size: 0.75rem; color: #898781; }
.chart-card .latest {
    margin-left: auto;
    font-size: 0.8rem;
    color: #c3c2b7;
}
.chart-card .latest .flag-high, .chart-card .latest .flag-low { color: #d03b3b; font-weight: 600; }
.chart-card .latest .flag-in { color: #0ca30c; font-weight: 600; }
.empty-note {
    color: #898781;
    font-size: 0.85rem;
}
@media (max-width: 1100px) {
    .app-shell { flex-direction: column; }
    .sidebar { width: 100%; border-right: none; border-bottom: 1px solid #2c2c2a; }
    .stat-tiles { margin-left: 0; }
}
"""


# AI commentary is model-generated markdown. Images are the one element that
# would fetch a remote URL on render, so pin them to local/inline sources; a
# crafted result string cannot turn a chart into a beacon. Scoped to img-src
# only, since Dash and Plotly need inline scripts and styles.
CSP_IMG = "img-src 'self' data: blob:;"


def index_string() -> str:
    """Dash index template with the theme's inline stylesheet."""
    return (
        "<!DOCTYPE html>"
        "<html>"
        "<head>"
        "{%metas%}"
        f'<meta http-equiv="Content-Security-Policy" content="{CSP_IMG}">'
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
