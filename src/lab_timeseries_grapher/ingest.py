"""Import an arbitrary lab CSV: infer its columns, then merge it in.

Two problems, kept separate so each can be reasoned about on its own.

**Inference.** An uploaded file will not use this app's column names. Headers
are matched first, since a file that says "Test Name" means it; content
sniffing is the fallback, picking the column that parses as dates, the one
that is mostly numeric, and the one that reads like test names.

**Merge.** A result is identified by its test and its date. When an upload
carries a result for a test and date already present, the uploaded row wins —
a re-issued or corrected report supersedes what was there.
"""

from __future__ import annotations

import csv
import io
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .data import coerce_float

logger = logging.getLogger("lab_timeseries_grapher")


class IngestError(ValueError):
    """Raised with a message safe to show in the UI."""


# Header spellings seen in lab exports, mapped to the column they fill.
HEADER_HINTS: dict[str, tuple[str, ...]] = {
    "Date": ("date", "collected", "collection date", "drawn", "draw date", "resulted",
             "result date", "observation date", "specimen date", "reported"),
    "Test Name": ("test name", "test", "analyte", "component", "marker", "measure",
                  "observation", "name", "description"),
    "Value": ("value", "result", "result value", "observation value", "measurement",
              "numeric result", "qty"),
    "Units": ("units", "unit", "uom", "unit of measure"),
    "Range_Low": ("range low", "range_low", "ref low", "reference low", "low", "min",
                  "lower limit"),
    "Range_High": ("range high", "range_high", "ref high", "reference high", "high",
                   "max", "upper limit"),
    "Typical range": ("typical range", "reference range", "ref range", "normal range",
                      "range"),
    "Panel": ("panel", "group", "category", "profile"),
    "Notes": ("notes", "note", "comment", "comments", "interpretation"),
}


def _norm(text: object) -> str:
    return " ".join(str(text or "").split()).strip().lower().replace("_", " ")


def infer_by_header(columns: list[str]) -> dict[str, str]:
    """Map target column -> source column, by header name."""
    mapping: dict[str, str] = {}
    taken: set[str] = set()
    for target, hints in HEADER_HINTS.items():
        for col in columns:
            if col in taken:
                continue
            n = _norm(col)
            if n in hints or any(n == h for h in hints):
                mapping[target] = col
                taken.add(col)
                break
    # A looser pass for headers that merely contain a hint.
    for target, hints in HEADER_HINTS.items():
        if target in mapping:
            continue
        for col in columns:
            if col in taken:
                continue
            n = _norm(col)
            if any(h in n for h in hints):
                mapping[target] = col
                taken.add(col)
                break
    return mapping


def _date_score(values: pd.Series) -> float:
    parsed = pd.to_datetime(values, errors="coerce")
    return float(parsed.notna().mean())


def _numeric_score(values: pd.Series) -> float:
    return float(sum(coerce_float(v) is not None for v in values) / max(len(values), 1))


def _name_score(values: pd.Series) -> float:
    """Reads like test names: mostly non-numeric text, many distinct values."""
    text = [str(v).strip() for v in values if str(v).strip()]
    if not text:
        return 0.0
    non_numeric = sum(coerce_float(v) is None for v in text) / len(text)
    variety = min(len(set(text)) / len(text), 1.0)
    return non_numeric * (0.5 + 0.5 * variety)


def infer_by_content(df: pd.DataFrame, already: dict[str, str]) -> dict[str, str]:
    """Fill gaps in the mapping by looking at what the columns contain."""
    mapping = dict(already)
    taken = set(mapping.values())
    sample = df.head(50)

    def pick(target: str, score) -> None:
        if target in mapping:
            return
        best, best_score = None, 0.0
        for col in df.columns:
            if col in taken:
                continue
            value = score(sample[col])
            if value > best_score:
                best, best_score = col, value
        if best is not None and best_score >= 0.6:
            mapping[target] = best
            taken.add(best)

    pick("Date", _date_score)
    pick("Value", _numeric_score)
    pick("Test Name", _name_score)
    return mapping


def infer_columns(df: pd.DataFrame) -> dict[str, str]:
    """Map this app's columns onto an uploaded file's columns."""
    mapping = infer_by_content(df, infer_by_header(list(df.columns)))
    missing = [c for c in ("Date", "Test Name", "Value") if c not in mapping]
    if missing:
        raise IngestError(
            "Could not work out which columns hold " + ", ".join(missing).lower()
            + ". Expected headers like Date, Test Name and Result."
        )
    return mapping


def split_range(text: str) -> tuple[float | None, float | None]:
    """Pull low/high out of a '0.8 - 1.9 ng/dL' style reference range."""
    body = str(text or "").strip()
    if not body or body.lower() in {"n/a", "nan", "none"}:
        return (None, None)
    for sep in ("–", "—", " to ", "-"):
        if sep in body:
            left, _, right = body.partition(sep)
            low, high = coerce_float(left), coerce_float(right.split()[0] if right.split() else "")
            if low is not None or high is not None:
                return (low, high)
    return (None, None)


@dataclass
class RowChange:
    test: str
    date: str
    value: str
    replaced: str | None = None  # the value it supersedes, when it does


@dataclass
class Plan:
    """What an upload would do, before anything is written."""

    mapping: dict[str, str] = field(default_factory=dict)
    added: list[RowChange] = field(default_factory=list)
    replaced: list[RowChange] = field(default_factory=list)
    skipped: int = 0
    rows: list[list[str]] = field(default_factory=list)  # the merged file

    @property
    def total(self) -> int:
        return len(self.added) + len(self.replaced)


def build_plan(csv_path: Path, uploaded: pd.DataFrame) -> Plan:
    """Work out the merge without touching the file."""
    mapping = infer_columns(uploaded)

    with csv_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    if not rows:
        raise IngestError("The existing labs CSV is empty.")
    header = rows[0]
    idx = {col: i for i, col in enumerate(header)}
    if "Date" not in idx or "Test Name" not in idx:
        raise IngestError("The existing labs CSV has no Date or Test Name column.")

    # Existing rows by (test, day), so an upload can supersede them.
    existing: dict[tuple[str, str], int] = {}
    for position, row in enumerate(rows[1:], start=1):
        if len(row) != len(header):
            continue
        stamp = pd.to_datetime(row[idx["Date"]], errors="coerce")
        if pd.notna(stamp):
            existing[(row[idx["Test Name"]].strip(), f"{stamp:%Y-%m-%d}")] = position

    plan = Plan(mapping=mapping)
    seen_in_upload: dict[tuple[str, str], int] = {}

    for _, incoming in uploaded.iterrows():
        name = str(incoming[mapping["Test Name"]]).strip()
        stamp = pd.to_datetime(incoming[mapping["Date"]], errors="coerce")
        number = coerce_float(incoming[mapping["Value"]])
        if not name or pd.isna(stamp) or number is None:
            plan.skipped += 1
            continue

        day = f"{stamp:%Y-%m-%d}"
        key = (name, day)
        units = str(incoming[mapping["Units"]]).strip() if "Units" in mapping else ""
        low = high = None
        if "Range_Low" in mapping:
            low = coerce_float(incoming[mapping["Range_Low"]])
        if "Range_High" in mapping:
            high = coerce_float(incoming[mapping["Range_High"]])
        if (low is None or high is None) and "Typical range" in mapping:
            low2, high2 = split_range(incoming[mapping["Typical range"]])
            low, high = (low if low is not None else low2), (high if high is not None else high2)

        display = f"{number:g} {units}".strip()
        row = [""] * len(header)

        # Carry metadata forward from an existing row for this test.
        template_at = existing.get(key)
        if template_at is None:
            template_at = next(
                (i for (t, _), i in existing.items() if t == name), None
            )
        if template_at is not None:
            row = list(rows[template_at])

        row[idx["Date"]] = day
        row[idx["Test Name"]] = name
        if "Value" in idx:
            row[idx["Value"]] = display
        if "Value_Numeric" in idx:
            row[idx["Value_Numeric"]] = f"{number:g}"
        if units and "Units" in idx:
            row[idx["Units"]] = units
        if low is not None and "Range_Low" in idx:
            row[idx["Range_Low"]] = f"{low:g}"
        if high is not None and "Range_High" in idx:
            row[idx["Range_High"]] = f"{high:g}"
        if low is not None and high is not None and "Typical range" in idx:
            row[idx["Typical range"]] = f"{low:g} - {high:g} {units}".strip()
        if "Panel" in mapping and "Panel" in idx:
            panel = str(incoming[mapping["Panel"]]).strip()
            if panel:
                row[idx["Panel"]] = panel

        at = existing.get(key)
        if at is not None:
            previous = rows[at][idx["Value"]] if "Value" in idx else ""
            rows[at] = row
            plan.replaced.append(RowChange(name, day, display, previous))
        elif key in seen_in_upload:
            # The upload repeats itself; later wins, same rule.
            rows[seen_in_upload[key]] = row
            plan.replaced.append(RowChange(name, day, display, "earlier row in this upload"))
        else:
            rows.append(row)
            seen_in_upload[key] = len(rows) - 1
            plan.added.append(RowChange(name, day, display))

    plan.rows = rows
    return plan


def read_uploaded(content: bytes) -> pd.DataFrame:
    """Parse uploaded bytes as a CSV."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = content.decode("latin-1")
        except Exception as exc:  # pragma: no cover - defensive
            raise IngestError("Could not read the file as text.") from exc
    try:
        df = pd.read_csv(io.StringIO(text), dtype=str).fillna("")
    except pd.errors.EmptyDataError as exc:
        raise IngestError("That file has no rows.") from exc
    except Exception as exc:
        raise IngestError(f"Could not read that file as CSV: {exc}") from exc
    if df.empty:
        raise IngestError("That file has no rows.")
    return df


def commit_plan(csv_path: Path, plan: Plan) -> None:
    """Write a plan's merged rows, atomically."""
    if not plan.rows:
        raise IngestError("Nothing to write.")
    fd, tmp = tempfile.mkstemp(dir=str(csv_path.parent), suffix=".csv")
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerows(plan.rows)
        os.replace(tmp, csv_path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise
    logger.info(
        "Imported CSV: %d added, %d replaced, %d skipped",
        len(plan.added), len(plan.replaced), plan.skipped,
    )
