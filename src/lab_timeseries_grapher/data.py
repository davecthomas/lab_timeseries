"""Loading, cleaning, and shaping of the labs CSV into per-metric series."""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger("lab_timeseries_grapher")

REQUIRED_COLUMNS = [
    "Date",
    "Test Name",
    "Value_Numeric",
    "Units",
    "Range_Low",
    "Range_High",
]

STATUS_IN = "in"
STATUS_LOW = "low"
STATUS_HIGH = "high"
STATUS_UNKNOWN = "unknown"



def coerce_float(x) -> float | None:
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
) -> tuple[float, float] | None:
    """
    Choose a representative normal range for a test.

    Strategy:
      1) Mode of (low, high) pairs among rows where BOTH are numeric.
      2) If no clear mode, use median(low), median(high) across numeric rows.
    """
    lows = [coerce_float(v) for v in low_series]
    highs = [coerce_float(v) for v in high_series]
    pairs = [(lo, hi) for lo, hi in zip(lows, highs) if lo is not None and hi is not None]

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


BOILERPLATE = ("relative risk", "reference range", "manually entered")


def clean_note(note: str) -> str:
    """Pull the human description out of one Notes cell.

    Notes arrive in several shapes: a bare description, a panel prefix plus
    description ("Liver — Liver-specific enzyme…"), or reference-range
    boilerplate with the description appended after an em dash. Segments are
    split on the em dash, boilerplate is dropped, and the most substantial
    remaining segment wins.
    """
    text = " ".join(str(note).split())
    segments = [s.strip(" .;") for s in text.split("—")]
    useful = [
        s
        for s in segments
        if s and not any(s.lower().startswith(prefix) for prefix in BOILERPLATE)
    ]
    return max(useful, key=len) if useful else ""


def describe(series: pd.Series) -> str:
    """The most common description across a test's rows."""
    notes = [
        clean_note(n)
        for n in series
        if str(n).strip().lower() not in {"", "n/a", "nan"}
    ]
    notes = [n for n in notes if n]
    if not notes:
        return ""
    return Counter(notes).most_common(1)[0][0]


def latest_range(
    low_series: pd.Series, high_series: pd.Series
) -> tuple[float, float] | None:
    """The range from the most recent row that carries one.

    Rows arrive oldest-first. A newer report supersedes an older one, so the
    newest stated range is the one a current result is judged against —
    picking the most *common* range would let two old reports outvote the
    range that came with the latest draw.
    """
    for lo, hi in zip(reversed(list(low_series)), reversed(list(high_series))):
        low, high = coerce_float(lo), coerce_float(hi)
        if low is not None and high is not None:
            return (low, high)
    return None


def mode_str(series: pd.Series) -> str:
    """Return the most common non-empty/non-'n/a' string in a column."""
    vals = [str(u).strip() for u in series if str(u).strip().lower() not in {"", "n/a", "nan"}]
    if not vals:
        return ""
    return Counter(vals).most_common(1)[0][0]


@dataclass
class MetricSeries:
    """One lab test's cleaned time series plus its display metadata."""

    name: str
    dates: list[pd.Timestamp]
    values: list[float]
    display_values: list[str]  # original result strings, e.g. "<0.1"
    band: tuple[float, float] | None  # the band the charts judge against
    units: str
    panel: str
    description: str = ""  # what the test measures, from the CSV's Notes
    lab_band: tuple[float, float] | None = None  # a range carried by the rows
    reference: object = None  # reference_ranges.Reference, when one applies

    @property
    def last_date(self) -> pd.Timestamp:
        return self.dates[-1]

    @property
    def latest_value(self) -> float:
        return self.values[-1]

    @property
    def latest_display(self) -> str:
        return self.display_values[-1]

    def status_of(self, value: float) -> str:
        if self.band is None:
            return STATUS_UNKNOWN
        low, high = self.band
        if value < low:
            return STATUS_LOW
        if value > high:
            return STATUS_HIGH
        return STATUS_IN

    @property
    def latest_status(self) -> str:
        return self.status_of(self.latest_value)

    def point_statuses(self) -> list[str]:
        return [self.status_of(v) for v in self.values]


def prepare_tests(df: pd.DataFrame, profile=None) -> dict[str, MetricSeries]:
    """Return a dictionary keyed by test name with cleaned time-series data.

    A published reference range for the profile draws the band when one
    applies in the metric's own units, so a series spanning several labs is
    judged consistently. The lab's own range is kept as `lab_band`.
    """
    from .reference_ranges import Profile, reference_for, reference_in_units

    profile = profile or Profile()
    tests: dict[str, MetricSeries] = {}
    has_value_col = "Value" in df.columns
    has_panel_col = "Panel" in df.columns
    has_notes_col = "Notes" in df.columns

    for test_name, sub in df.groupby("Test Name"):
        dfp = sub.copy()
        dfp["Date_parsed"] = pd.to_datetime(dfp["Date"], errors="coerce")
        dfp["Value_Num"] = dfp["Value_Numeric"].apply(coerce_float)
        dfp = dfp.dropna(subset=["Date_parsed", "Value_Num"]).sort_values("Date_parsed")

        if dfp.empty:
            logger.debug("Skipping test '%s': no valid parsed rows remain after cleanup", test_name)
            continue

        if has_value_col:
            displays = [
                str(v).strip() if str(v).strip().lower() not in {"", "n/a", "nan"} else f"{n:g}"
                for v, n in zip(dfp["Value"], dfp["Value_Num"])
            ]
        else:
            displays = [f"{n:g}" for n in dfp["Value_Num"]]

        units = mode_str(dfp["Units"])
        lab_band = latest_range(dfp["Range_Low"], dfp["Range_High"])
        reference = reference_in_units(reference_for(str(test_name), profile), units)


        tests[str(test_name)] = MetricSeries(
            name=str(test_name),
            dates=dfp["Date_parsed"].tolist(),
            values=dfp["Value_Num"].astype(float).tolist(),
            display_values=displays,
            # A row that carries a range states the range for that result, so
            # it is the override; the age/sex reference fills in only where no
            # row supplied one. How a row arrived carries no weight — an entry
            # typed into the dialog is a row like any other.
            band=lab_band or (reference.band if reference and reference.band else None),
            units=units,
            panel=mode_str(dfp["Panel"]) if has_panel_col else "",
            description=describe(dfp["Notes"]) if has_notes_col else "",
            lab_band=lab_band,
            reference=reference,
        )

        logger.debug(
            "Prepared test '%s' with %d points%s (last: %s)",
            test_name,
            len(tests[str(test_name)].dates),
            "" if tests[str(test_name)].band else " (no band)",
            tests[str(test_name)].last_date.strftime("%Y-%m-%d"),
        )
    return tests


def data_dir() -> Path:
    """Return the project's /data directory."""
    return Path(__file__).resolve().parents[2] / "data"


def resolve_csv_path(csv_arg: str) -> Path:
    """
    Resolve the CSV path relative to the project /data directory.

    Resolution order:
      1. An absolute path that exists is used as-is.
      2. A filename found under the project's /data directory is used.
      3. If the named file is absent, fall back to the single CSV in /data
         (the data files are gitignored, so their names vary per machine).

    The returned path may not exist; the caller is expected to check.
    """
    raw = Path(csv_arg)
    if raw.is_absolute() and raw.exists():
        return raw

    candidate = data_dir() / raw.name
    if candidate.exists():
        return candidate

    csvs = sorted(data_dir().glob("*.csv"))
    if len(csvs) == 1:
        logger.info(
            "Default CSV %s not found; using the only CSV in /data: %s", raw.name, csvs[0].name
        )
        return csvs[0]

    return candidate


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


def validate_schema(df: pd.DataFrame) -> None:
    """Exit with a clear message when required columns are missing."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        logger.error("CSV missing required columns: %s", missing)
        raise SystemExit(f"Missing required columns: {missing}")
