"""Population reference ranges, by age and sex.

**Authored from published sources, not from your lab.** Each entry carries the
source it came from. These draw the band on the charts so a series spanning
several labs is judged against one consistent scale; the range your own lab
reported is kept and shown alongside as context.

Reference intervals are assay- and population-specific, and published sources
genuinely disagree — free T4 is 0.9–1.7 ng/dL at Mayo, 0.70–1.48 on one of the
lab reports in this dataset, and 0.8–1.9 on another. Where a lab report and
this table conflict, the lab that ran the sample is the better authority for
that draw, which is why every range here is overridable per metric.

Sources
-------
CMP      MedlinePlus, Comprehensive metabolic panel
         https://medlineplus.gov/ency/article/003468.htm
CBC      StatPearls, Normal and Abnormal Complete Blood Count With Differential
         https://www.ncbi.nlm.nih.gov/books/NBK604207/
LIPID    NCEP ATP III classification, via StatPearls "Cholesterol Levels"
         https://www.ncbi.nlm.nih.gov/books/NBK542294/
FT4      Mayo Clinic Laboratories, T4 (Thyroxine), Free, Serum
         https://endocrinology.testcatalog.org/show/FRT4
A1C      ADA diagnostic thresholds, via StatPearls "Hemoglobin A1C"
         https://www.ncbi.nlm.nih.gov/books/NBK549816/
URIC     MedlinePlus, Uric acid - blood
         https://medlineplus.gov/ency/article/003476.htm
ESR      StatPearls, Erythrocyte Sedimentation Rate
         https://www.ncbi.nlm.nih.gov/books/NBK557485/
PSA      Age-specific PSA reference ranges, community-based study
         https://pubmed.ncbi.nlm.nih.gov/8753735/
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MALE = "male"
FEMALE = "female"


@dataclass(frozen=True)
class Profile:
    """Who the ranges are being selected for."""

    age: int = 60
    sex: str = MALE


@dataclass(frozen=True)
class Reference:
    low: float | None
    high: float | None
    units: str
    source: str
    note: str = ""

    @property
    def band(self) -> tuple[float, float] | None:
        """Only a two-sided range can draw a band."""
        if self.low is None or self.high is None:
            return None
        return (self.low, self.high)


def _psa(profile: Profile) -> Reference:
    """PSA rises with age; thresholds are banded by decade."""
    upper = 2.5 if profile.age < 50 else 3.5 if profile.age < 60 else 4.5 if profile.age < 70 else 6.5
    return Reference(0.0, upper, "ng/mL", "PSA", f"age-specific upper limit for {profile.age}")


def _esr(profile: Profile) -> Reference:
    """Westergren intervals widen with age."""
    high = 22.0 if profile.age >= 70 else 14.0
    return Reference(1.0, high, "mm/h", "ESR", f"men aged {profile.age}")


# (pattern, builder). Ordered — first match wins, narrower patterns first.
RULES: tuple[tuple[str, object], ...] = (
    # --- Thyroid ---
    (r"t4.*free|free.*t4", lambda p: Reference(0.9, 1.7, "ng/dL", "FT4")),
    (r"thyroid stimulating|^tsh", lambda p: Reference(0.4, 4.0, "mIU/L", "FT4", "guideline range")),
    # --- Glucose ---
    (r"hemoglobin a1c|a1c", lambda p: Reference(None, 5.7, "%", "A1C", "below the prediabetes threshold")),
    (r"glucose", lambda p: Reference(70.0, 100.0, "mg/dL", "CMP", "fasting")),
    # --- Lipids: narrower first ---
    (r"non.?hdl", lambda p: Reference(None, 130.0, "mg/dL", "LIPID", "optimal is LDL target + 30")),
    (r"ldl particle|ldl peak|ldl (medium|small|large)|hdl large|apolipoprotein|lipoprotein ?\(a\)",
     lambda p: None),  # particle assays: no consensus interval, keep the lab's
    (r"chol.*hdl ratio|hdl ratio", lambda p: None),
    (r"vldl", lambda p: Reference(2.0, 30.0, "mg/dL", "LIPID")),
    (r"triglyceride|trigl", lambda p: Reference(None, 150.0, "mg/dL", "LIPID", "normal below 150")),
    (r"hdl", lambda p: Reference(40.0, None, "mg/dL", "LIPID", "low below 40; high above 60")),
    (r"ldl", lambda p: Reference(None, 100.0, "mg/dL", "LIPID", "optimal below 100")),
    (r"cholesterol|cholest", lambda p: Reference(None, 200.0, "mg/dL", "LIPID", "desirable below 200")),
    # --- Liver / protein ---
    (r"^alt\b|sgpt", lambda p: Reference(4.0, 36.0, "U/L", "CMP")),
    (r"^ast\b|sgot", lambda p: Reference(8.0, 33.0, "U/L", "CMP")),
    (r"alk.*phos", lambda p: Reference(20.0, 130.0, "U/L", "CMP")),
    (r"bilirubin", lambda p: Reference(0.1, 1.2, "mg/dL", "CMP")),
    (r"^a\s*g\s*ratio|albumin.*globulin", lambda p: Reference(1.1, 2.5, "ratio", "CMP", "derived")),
    (r"globulin", lambda p: Reference(2.0, 3.5, "g/dL", "CMP", "derived from protein minus albumin")),
    (r"albumin", lambda p: Reference(3.4, 5.4, "g/dL", "CMP")),
    (r"total protein|protein, total", lambda p: Reference(6.0, 8.3, "g/dL", "CMP")),
    # --- Kidney / electrolytes ---
    (r"bun.*creatinine|creatinine.*ratio", lambda p: Reference(10.0, 20.0, "ratio", "CMP", "derived")),
    (r"^bun\b|urea nitrogen", lambda p: Reference(6.0, 20.0, "mg/dL", "CMP")),
    (r"creatinine", lambda p: Reference(0.6, 1.3, "mg/dL", "CMP")),
    (r"egfr|ckd.?epi", lambda p: Reference(60.0, None, "mL/min/1.73m²", "CMP", "below 60 suggests CKD")),
    (r"^sodium", lambda p: Reference(135.0, 145.0, "mEq/L", "CMP")),
    (r"^potassium", lambda p: Reference(3.7, 5.2, "mEq/L", "CMP")),
    (r"^chloride", lambda p: Reference(96.0, 106.0, "mEq/L", "CMP")),
    (r"bicarbonate|carbon dioxide|^co2|co2, total|co2 content", lambda p: Reference(23.0, 29.0, "mEq/L", "CMP")),
    (r"^calcium", lambda p: Reference(8.5, 10.2, "mg/dL", "CMP")),
    (r"anion gap", lambda p: Reference(8.0, 16.0, "mmol/L", "CMP")),
    (r"uric acid", lambda p: Reference(4.0, 8.6, "mg/dL", "URIC", "men")),
    (r"osmolality", lambda p: Reference(275.0, 295.0, "mOsm/kg", "CMP")),
    # --- CBC: differentials before parent lines ---
    (r"(%|percent|nfr).*neutrophil|neutrophil.*(%|percent|nfr)", lambda p: Reference(40.0, 60.0, "%", "CBC")),
    (r"neutrophil|abs\.? neut|^anc\b", lambda p: Reference(1500.0, 8000.0, "cells/µL", "CBC", "absolute count")),
    (r"(%|percent|nfr).*lymphocyte|lymphocyte.*(%|percent|nfr)", lambda p: Reference(20.0, 40.0, "%", "CBC")),
    (r"lymphocyte", lambda p: Reference(1000.0, 4000.0, "cells/µL", "CBC", "absolute count")),
    (r"(%|percent|nfr).*monocyte|monocyte.*(%|percent|nfr)", lambda p: Reference(2.0, 8.0, "%", "CBC")),
    (r"monocyte", lambda p: Reference(200.0, 1000.0, "cells/µL", "CBC", "absolute count")),
    (r"(%|percent|nfr).*eosinophil|eosinophil.*(%|percent|nfr)", lambda p: Reference(0.0, 4.0, "%", "CBC")),
    (r"eosinophil", lambda p: Reference(0.0, 500.0, "cells/µL", "CBC", "absolute count")),
    (r"(%|percent|nfr).*basophil|basophil.*(%|percent|nfr)", lambda p: Reference(0.5, 1.0, "%", "CBC")),
    (r"basophil", lambda p: Reference(0.0, 200.0, "cells/µL", "CBC", "absolute count")),
    (r"immature granulocyte|^ig\b|promyelo", lambda p: None),
    (r"nucleated rbc|^nrbc", lambda p: None),
    (r"^mcv|mean corpuscular volume", lambda p: Reference(80.0, 100.0, "fL", "CBC")),
    (r"^mchc|mean corpuscular hgb concentr", lambda p: Reference(32.0, 36.0, "g/dL", "CBC")),
    (r"^mch\b|mean corpuscular hgb", lambda p: Reference(27.0, 32.0, "pg", "CBC")),
    (r"^rdw|distribution width", lambda p: Reference(11.5, 15.0, "%", "CBC")),
    (r"^mpv|^pmv|platelet volume", lambda p: Reference(7.5, 12.5, "fL", "CBC")),
    (r"platelet|^plt", lambda p: Reference(150.0, 400.0, "10^3/µL", "CBC")),
    (r"hematocrit|^hct", lambda p: _by_sex(p, (40.0, 54.0), (36.0, 48.0), "%", "CBC")),
    (r"hemoglobin|^hgb", lambda p: _by_sex(p, (13.0, 18.0), (12.0, 16.0), "g/dL", "CBC")),
    (r"^rbc|red cell|red blood", lambda p: _by_sex(p, (4.6, 6.2), (4.2, 5.4), "10^6/µL", "CBC")),
    (r"^wbc|white cell|white blood|leuk", lambda p: Reference(4500.0, 11000.0, "cells/µL", "CBC")),
    # --- Other ---
    (r"^psa|prostate", _psa),
    (r"sed rate|sedimentation", _esr),
    (r"c.?reactive protein", lambda p: Reference(None, 3.0, "mg/L", "CMP", "cardiac risk cutpoint")),
    (r"vitamin d", lambda p: Reference(30.0, 100.0, "ng/mL", "CMP", "sufficiency")),
    (r"testost", lambda p: Reference(175.0, 781.0, "ng/dL", "CMP", "assay-dependent")),
    (r"prothrombin", lambda p: Reference(11.0, 13.5, "sec", "CMP")),
    (r"troponin|hepatitis|agatson|agatston|cardiac calcium", lambda p: None),
)

_COMPILED = tuple((re.compile(pattern), build) for pattern, build in RULES)


def _by_sex(profile, male, female, units, source):
    low, high = male if profile.sex == MALE else female
    return Reference(low, high, units, source, f"{profile.sex} reference")


def reference_for(test_name: str, profile: Profile | None = None) -> Reference | None:
    """The published reference for a test, or None when this table has none.

    None means "defer to the lab" — the assay has no consensus interval, or
    the measurement is not one this table covers.
    """
    if not test_name:
        return None
    profile = profile or Profile()
    lowered = test_name.strip().lower()
    for pattern, build in _COMPILED:
        if pattern.search(lowered):
            return build(profile)
    return None


# Unit spellings seen across labs, mapped to one canonical name. A reference
# range is only applied when its units can be reconciled with the metric's.
UNIT_ALIASES = {
    "10^3/ul": "k/ul", "x10^3/ul": "k/ul", "10*3/ul": "k/ul", "thousand/ul": "k/ul",
    "x10e3/ul": "k/ul",
    "k/ul": "k/ul", "k/mcl": "k/ul", "x10(9)/l": "k/ul", "10^9/l": "k/ul",
    "cells/ul": "cells/ul", "/ul": "cells/ul",
    "10^6/ul": "m/ul", "x10^6/ul": "m/ul", "million/ul": "m/ul", "m/ul": "m/ul",
    "x10e6/ul": "m/ul", "m/mcl": "m/ul",
    "x10(12)/l": "m/ul", "10^12/l": "m/ul",
    "u/l": "u/l", "units/l": "u/l", "iu/l": "u/l",
    "mg/dl": "mg/dl", "g/dl": "g/dl", "g/l": "g/l",
    "ng/ml": "ng/ml", "ng/dl": "ng/dl", "nmol/l": "nmol/l",
    "meq/l": "meq/l", "mmol/l": "mmol/l",
    "miu/l": "miu/l", "mciu/ml": "miu/l", "uiu/ml": "miu/l",
    "%": "%", "fl": "fl", "pg": "pg", "sec": "sec", "mm/h": "mm/h",
    "mosm/kg": "mosm/kg", "mosm/kg h20": "mosm/kg", "ratio": "ratio",
    "ml/min/1.73m²": "egfr", "ml/min/1.73 m²": "egfr", "ml/min/1.73m*2": "egfr",
    "ml/min/1.73": "egfr", "ml/min/1.73m2": "egfr", "ml/min/1.73 m2": "egfr",
    "mg/l": "mg/l",
}

# Exact, dimensionless conversions between canonical units.
UNIT_SCALES = {
    ("cells/ul", "k/ul"): 0.001,
    ("k/ul", "cells/ul"): 1000.0,
    ("m/ul", "cells/ul"): 1_000_000.0,
    ("cells/ul", "m/ul"): 0.000001,
    ("g/dl", "g/l"): 10.0,
    ("g/l", "g/dl"): 0.1,
}


def canonical_units(units: str) -> str:
    key = " ".join(str(units or "").split()).lower().replace("µ", "u")
    return UNIT_ALIASES.get(key, key)


def convert(value: float, from_units: str, to_units: str) -> float | None:
    """Convert between canonical units, or None when no exact factor is known."""
    a, b = canonical_units(from_units), canonical_units(to_units)
    if a == b:
        return value
    factor = UNIT_SCALES.get((a, b))
    return None if factor is None else value * factor


def reference_in_units(ref: Reference | None, units: str) -> Reference | None:
    """Restate a reference in the metric's own units.

    Returns None when the two cannot be reconciled — applying a range in
    cells/µL to a value recorded in 10^3/µL would misread 2.7 as critically
    low, so deferring to the lab is the only safe answer.
    """
    if ref is None:
        return None
    if not units:
        return ref if canonical_units(ref.units) in {"", "%"} else None

    low = convert(ref.low, ref.units, units) if ref.low is not None else None
    high = convert(ref.high, ref.units, units) if ref.high is not None else None
    if (ref.low is not None and low is None) or (ref.high is not None and high is None):
        return None
    return Reference(low, high, units, ref.source, ref.note)


def describe_reference(ref: Reference | None) -> str:
    """One-line description of a reference range for the UI."""
    if ref is None:
        return ""
    if ref.low is not None and ref.high is not None:
        span = f"{ref.low:g}–{ref.high:g}"
    elif ref.high is not None:
        span = f"below {ref.high:g}"
    elif ref.low is not None:
        span = f"above {ref.low:g}"
    else:
        return ""
    text = f"{span} {ref.units}".strip()
    return f"{text} ({ref.note})" if ref.note else text
