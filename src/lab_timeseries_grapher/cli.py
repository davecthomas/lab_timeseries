"""Command-line entry point: load the CSV and serve the Dash app."""

from __future__ import annotations

import argparse
import logging
import os

from dash import exceptions

from .app import create_app
from .data import (
    data_dir,
    load_dataframe,
    prepare_tests,
    resolve_csv_path,
    validate_schema,
)

logger = logging.getLogger("lab_timeseries_grapher")


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


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Explore per-test lab time series with normal-range bands"
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
        available = sorted(p.name for p in data_dir().glob("*.csv"))
        hint = (
            f" Available CSVs in /data: {', '.join(available)}."
            if available
            else " No CSVs found in /data."
        )
        raise SystemExit(f"CSV not found at {csv_path}. Expected inside the /data directory.{hint}")

    logger.info("Resolved CSV path: %s", csv_path)

    df = load_dataframe(csv_path)
    validate_schema(df)

    metrics = prepare_tests(df)
    if not metrics:
        logger.error("CSV yielded no plottable rows after preprocessing")
        raise SystemExit("No plottable rows were found in the CSV.")
    logger.info("Prepared %d metrics for display", len(metrics))

    app = create_app(metrics)

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
