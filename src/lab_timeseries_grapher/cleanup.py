"""Find and repair damage in the labs CSV.

Lab exports arrive mangled in a small number of recurring ways, and every one
of these was found in real data rather than imagined:

- the same result written twice, from overlapping report downloads
- a thousands separator eating a value, so "3,457" was stored as 3
- the same truncation inside a reference range, so "1,500 - 7,800" became 500-7
- a units column left blank while the printed value carried the unit
- a units column that contradicts the printed value
- a reference range stored low-high inverted

Each is detected independently and reported as an :class:`Issue`, so the
preview can say exactly what would change before anything is written. The
repairs are deliberately conservative: every one of them recovers information
already present elsewhere in the same row, and none invents a number.

Two kinds are therefore reported without being fixed. Rows that cannot be read
at all are never silently deleted — losing a result is worse than leaving a
mess. And a units column that genuinely contradicts the printed value is left
alone, because choosing a side rescales a result and the row does not contain
enough to choose correctly. Units that merely *look* different — "10^3/µL"
against "x10E3/uL" — are treated as equal rather than as a disagreement.

Deduplication follows the same rule as the importer: when two rows describe the
same test on the same day, the later one wins.
"""

from __future__ import annotations

import csv
import logging
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .data import coerce_float

logger = logging.getLogger("lab_timeseries_grapher")

BACKUP_SUFFIX = ".backup.csv"

# Units seen in blood work. The list is a guard, not a vocabulary: a token has
# to look like one of these before it is copied into the Units column, so a
# stray word from a comment cannot become a unit. Compared case-insensitively
# with micro signs folded, since labs disagree about µ vs u.
_BASE_UNITS: frozenset[str] = frozenset(
    {
        "%", "ratio", "index", "score",
        "g/dl", "g/l", "mg/dl", "mg/l", "mcg/dl", "ug/dl", "ng/dl", "ng/ml",
        "pg/ml", "ug/ml", "mcg/ml", "ng/l", "pg/dl",
        "mmol/l", "umol/l", "mol/l", "nmol/l", "pmol/l", "mmol/mol",
        "meq/l", "mosm/kg", "mosm/l",
        "u/l", "iu/l", "miu/l", "uiu/ml", "miu/ml", "iu/ml", "u/ml",
        "k/ul", "m/ul", "x10e3/ul", "x10e6/ul", "10*3/ul", "10*6/ul",
        "thous/ul", "mill/ul", "cells/ul", "/ul", "k/mm3", "m/mm3",
        "fl", "pg", "ml/min", "ml/min/1.73", "ml/min/1.73m2",
        "mm/hr", "mmhg", "sec", "seconds", "years", "nmol/ml",
    }
)

# Anything that means "no unit recorded".
_BLANK_UNITS = {"", "n/a", "na", "nan", "none", "unitless", "-", "--"}

# Spellings of the same unit. Labs write "10^3/µL", "x10E3/uL" and "K/uL" for
# one thing, and treating those as a disagreement would mean rewriting a
# perfectly readable units column into whatever encoding the report used.
_EQUIVALENT: dict[str, str] = {
    "10^3/ul": "10^3/ul", "x10e3/ul": "10^3/ul", "k/ul": "10^3/ul",
    "10*3/ul": "10^3/ul", "thous/ul": "10^3/ul", "1000/ul": "10^3/ul",
    "10e3/ul": "10^3/ul", "k/mm3": "10^3/ul",
    "10^6/ul": "10^6/ul", "x10e6/ul": "10^6/ul", "m/ul": "10^6/ul",
    "10*6/ul": "10^6/ul", "mill/ul": "10^6/ul", "10e6/ul": "10^6/ul",
    "m/mm3": "10^6/ul",
    "ug/dl": "ug/dl", "mcg/dl": "ug/dl",
    "ug/ml": "ug/ml", "mcg/ml": "ug/ml",
    "ug/l": "ug/l", "mcg/l": "ug/l",
    "mm/hr": "mm/hr", "mm/h": "mm/hr",
    "ml/min/1.73": "ml/min/1.73", "ml/min/1.73m2": "ml/min/1.73",
    "ml/min/1.73m²": "ml/min/1.73",
    "sec": "sec", "seconds": "sec", "s": "sec",
}

# Every spelling the equivalence table knows about is by definition a unit, so
# the two cannot drift apart.
KNOWN_UNITS: frozenset[str] = _BASE_UNITS | frozenset(_EQUIVALENT) | frozenset(
    _EQUIVALENT.values()
)

_LEADING_NUMBER = re.compile(r"^\s*[<>≤≥]?\s*[\d,]+\.?\d*\s*")
_RANGE = re.compile(r"^\s*([<>≤≥]?\s*[\d,]+\.?\d*)\s*(?:-|–|—|to)\s*([\d,]+\.?\d*)")


def normalise_unit(text: object) -> str:
    """A unit reduced to a comparable form: lower case, µ folded to u."""
    s = " ".join(str(text or "").split()).strip().lower()
    return s.replace("µ", "u").replace("μ", "u")


def is_blank_unit(text: object) -> bool:
    return normalise_unit(text) in _BLANK_UNITS


def canonical_unit(text: object) -> str:
    """A unit reduced so equivalent spellings compare equal."""
    normalised = normalise_unit(text)
    # "x10E3/uL" and "10^3/uL" differ only in punctuation the table can't hold.
    stripped = normalised.lstrip("x").replace("**", "^").replace("*", "^")
    return _EQUIVALENT.get(normalised) or _EQUIVALENT.get(stripped) or normalised


def units_agree(a: object, b: object) -> bool:
    """True when two unit strings mean the same thing."""
    return canonical_unit(a) == canonical_unit(b)


def unit_from_value(value: object) -> str:
    """The unit printed after the number in a Value cell, or ''.

    Returns '' unless the trailing text is a recognised unit, so a Value of
    "12 (see note)" contributes nothing rather than a bogus unit.
    """
    body = str(value or "").strip()
    if not body:
        return ""
    remainder = _LEADING_NUMBER.sub("", body).strip()
    if not remainder:
        return ""
    if normalise_unit(remainder) in KNOWN_UNITS:
        return remainder
    return ""


def number_from_value(value: object) -> float | None:
    """The leading number of a Value cell, commas intact.

    This is the number as *printed on the report*, which is why it can be used
    to catch a Value_Numeric that lost a thousands separator.
    """
    body = str(value or "").strip()
    match = re.match(r"^\s*[<>≤≥]?\s*([\d,]+\.?\d*)", body)
    return coerce_float(match.group(1)) if match else None


def bounds_from_range(text: object) -> tuple[float | None, float | None]:
    """Low and high as printed in a 'Typical range' cell."""
    match = _RANGE.match(str(text or "").strip())
    if not match:
        return (None, None)
    return (coerce_float(match.group(1)), coerce_float(match.group(2)))


@dataclass
class Issue:
    """One problem found in one row, and what repairing it would do."""

    kind: str
    test: str
    date: str
    detail: str
    fixable: bool = True


# Display order and headings for the preview.
KIND_LABELS: dict[str, str] = {
    "duplicate": "Duplicate rows removed",
    "conflict": "Conflicting duplicates resolved (newest kept)",
    "truncated_value": "Values restored from a truncated number",
    "truncated_range": "Reference ranges restored from a truncated number",
    "inverted_range": "Reference ranges un-inverted",
    "missing_units": "Missing units filled in from the value",
    "unit_mismatch": "Units that disagree with the printed value (left alone)",
    "unreadable": "Rows with no readable value (left alone)",
}


@dataclass
class CleanupPlan:
    """What a cleanup would do, before anything is written."""

    issues: list[Issue] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    scanned: int = 0

    @property
    def fixable(self) -> list[Issue]:
        return [i for i in self.issues if i.fixable]

    @property
    def total(self) -> int:
        return len(self.fixable)

    def by_kind(self) -> dict[str, list[Issue]]:
        """Issues grouped, in KIND_LABELS order."""
        grouped: dict[str, list[Issue]] = {}
        for kind in KIND_LABELS:
            found = [i for i in self.issues if i.kind == kind]
            if found:
                grouped[kind] = found
        return grouped


def _fmt(number: float) -> str:
    return f"{number:g}"


def build_cleanup_plan(csv_path: Path) -> CleanupPlan:
    """Scan the CSV and work out every repair, without touching the file."""
    with Path(csv_path).open(newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    if not rows:
        return CleanupPlan()

    header = rows[0]
    idx = {col: i for i, col in enumerate(header)}
    plan = CleanupPlan(scanned=len(rows) - 1)

    def cell(row: list[str], col: str) -> str:
        at = idx.get(col)
        return row[at] if at is not None and at < len(row) else ""

    def put(row: list[str], col: str, text: str) -> bool:
        at = idx.get(col)
        if at is None or at >= len(row):
            return False
        row[at] = text
        return True

    cleaned: list[list[str]] = [header]
    # Where each (test, day) landed in `cleaned`, so a later row can supersede it.
    seen: dict[tuple[str, str], int] = {}

    for row in rows[1:]:
        if len(row) != len(header):
            plan.issues.append(
                Issue("unreadable", cell(row, "Test Name"), cell(row, "Date"),
                      f"row has {len(row)} fields, expected {len(header)}", fixable=False)
            )
            cleaned.append(row)
            continue

        row = list(row)
        name = cell(row, "Test Name").strip()
        stamp = pd.to_datetime(cell(row, "Date"), errors="coerce")
        day = f"{stamp:%Y-%m-%d}" if pd.notna(stamp) else cell(row, "Date").strip()
        value_text = cell(row, "Value")

        # --- a value that lost a thousands separator ---
        printed = number_from_value(value_text)
        stored = coerce_float(cell(row, "Value_Numeric"))
        if printed is not None and stored is not None and abs(printed - stored) > 1e-9:
            plan.issues.append(
                Issue("truncated_value", name, day, f"{_fmt(stored)} → {_fmt(printed)}")
            )
            put(row, "Value_Numeric", _fmt(printed))
        elif printed is not None and stored is None and cell(row, "Value_Numeric").strip():
            plan.issues.append(
                Issue("truncated_value", name, day,
                      f"{cell(row, 'Value_Numeric')!r} → {_fmt(printed)}")
            )
            put(row, "Value_Numeric", _fmt(printed))

        # --- a range whose bounds disagree with the range as printed ---
        low_text, high_text = bounds_from_range(cell(row, "Typical range"))
        low = coerce_float(cell(row, "Range_Low"))
        high = coerce_float(cell(row, "Range_High"))
        if low_text is not None and high_text is not None and (
            (low is not None and abs(low_text - low) > 1e-9)
            or (high is not None and abs(high_text - high) > 1e-9)
        ):
            plan.issues.append(
                Issue("truncated_range", name, day,
                      f"{_fmt(low) if low is not None else '?'}"
                      f"–{_fmt(high) if high is not None else '?'}"
                      f" → {_fmt(low_text)}–{_fmt(high_text)}")
            )
            put(row, "Range_Low", _fmt(low_text))
            put(row, "Range_High", _fmt(high_text))
            low, high = low_text, high_text

        # --- a range stored the wrong way round ---
        if low is not None and high is not None and low > high:
            plan.issues.append(
                Issue("inverted_range", name, day, f"{_fmt(low)}–{_fmt(high)} → {_fmt(high)}–{_fmt(low)}")
            )
            put(row, "Range_Low", _fmt(high))
            put(row, "Range_High", _fmt(low))

        # --- units missing from the column but printed in the value ---
        printed_unit = unit_from_value(value_text)
        column_unit = cell(row, "Units")
        if printed_unit:
            if is_blank_unit(column_unit):
                plan.issues.append(
                    Issue("missing_units", name, day, f"units set to {printed_unit}")
                )
                put(row, "Units", printed_unit)
            elif not units_agree(column_unit, printed_unit):
                # Reported, not repaired. Which side is wrong cannot be decided
                # from the row alone: a real case in this data had *both* the
                # column and the printed value saying g/dL for a free T4 that
                # was ng/dL, and only the reference range gave it away. Guessing
                # a unit silently rescales a result, so this one needs a human.
                plan.issues.append(
                    Issue("unit_mismatch", name, day,
                          f"column says {column_unit}, value says {printed_unit}",
                          fixable=False)
                )

        # --- a row carrying no usable number at all ---
        if printed is None and coerce_float(cell(row, "Value_Numeric")) is None:
            plan.issues.append(
                Issue("unreadable", name, day, f"value {value_text!r} has no number",
                      fixable=False)
            )
            cleaned.append(row)
            continue

        # --- the same test on the same day, twice ---
        key = (name, day)
        at = seen.get(key)
        if at is None:
            seen[key] = len(cleaned)
            cleaned.append(row)
            continue

        previous = cleaned[at]
        same = coerce_float(cell(previous, "Value_Numeric")) == coerce_float(
            cell(row, "Value_Numeric")
        )
        if same:
            plan.issues.append(
                Issue("duplicate", name, day, f"{cell(row, 'Value')} recorded twice")
            )
        else:
            plan.issues.append(
                Issue("conflict", name, day,
                      f"{cell(previous, 'Value')} and {cell(row, 'Value')} — keeping "
                      f"{cell(row, 'Value')}")
            )
        cleaned[at] = row  # later row wins, as with an import

    plan.rows = cleaned
    return plan


def commit_cleanup(csv_path: Path, plan: CleanupPlan) -> Path:
    """Write the repaired rows, keeping one backup. Returns the backup path.

    The backup is a single fixed filename rather than a timestamped one: this
    file is personal health data, and quietly accumulating copies of it every
    time the button is pressed is its own kind of mess.
    """
    csv_path = Path(csv_path)
    if not plan.rows:
        raise ValueError("Nothing to write.")

    backup = csv_path.with_suffix(BACKUP_SUFFIX)
    shutil.copy2(csv_path, backup)

    fd, tmp = tempfile.mkstemp(dir=str(csv_path.parent), suffix=".csv")
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerows(plan.rows)
        os.replace(tmp, csv_path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise

    counts = {kind: len(found) for kind, found in plan.by_kind().items()}
    logger.info("Cleaned labs CSV (%s); backup at %s", counts, backup.name)
    return backup
