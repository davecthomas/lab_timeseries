"""Benign conditions that shift what a normal result looks like.

**This file is authored and cited, not derived from the labs CSV.** Every band
below comes from published literature, named in each condition's `source`.
Correct it freely; do not generate it.

Some people have a persistent, harmless reason for a result to sit outside the
population interval. A thalassemia carrier runs a low MCV for life. Gilbert
syndrome raises bilirubin and does nothing else. Duffy-null individuals have a
neutrophil count below the standard floor with no added infection risk. Flagged
against the population range, these read as findings every single draw.

**These bands are drawn in addition to the normal band, never instead of it.**
That is the whole design. Replacing the band would mean a ticked checkbox could
silently hide a real abnormality — a carrier who later becomes iron deficient
still needs their falling MCV to register. Showing both boundaries lets the
reader see the value, the population range, and the range that this condition
would explain, and decide which they are looking at.

Some entries carry no band at all. Biotin interference is not a shifted
interval, it is an unreliable measurement, and inventing a range for it would
misrepresent what is known. Those contribute a note only.

Nothing here is diagnostic, and a checkbox is not a diagnosis. The notes say
what a pattern is consistent with, never that the reader has the condition.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .reference_ranges import convert


@dataclass(frozen=True)
class Effect:
    """What one condition does to one metric.

    `band` is the interval a result is expected to occupy *given* the
    condition, in `units`. None means the condition affects interpretation
    without defining a range — an assay interference, or a shift too
    situational to bound honestly.
    """

    pattern: str
    note: str
    band: tuple[float, float] | None = None
    units: str = ""


@dataclass(frozen=True)
class Condition:
    id: str
    label: str
    summary: str
    color: str
    source: str
    effects: tuple[Effect, ...]

    @property
    def has_bands(self) -> bool:
        return any(e.band for e in self.effects)


# Colours are chosen to separate from the normal band (green), the series line
# (blue) and the out-of-range flag (red), and from each other by hue rather
# than lightness — the bands overlap, so hue is the only reliable cue. Each
# condition also names itself in text on every card it touches, so the colour
# never carries the meaning alone.
CONDITIONS: tuple[Condition, ...] = (
    Condition(
        id="thalassemia-trait",
        label="Thalassemia trait",
        summary=(
            "Alpha or beta thalassemia carrier. Small red cells for life, with a "
            "normal or raised red cell count — unlike iron deficiency, which "
            "lowers it."
        ),
        color="#a06cd5",
        source=(
            "StatPearls: Beta Thalassemia; Alpha Thalassemia (NCBI Bookshelf). "
            "RDW discrimination: England & Fraser, Lancet 1973; Mentzer, Lancet 1973"
        ),
        effects=(
            # RDW first, and deliberately without a band. The trait makes cells
            # uniformly small, so it does not raise RDW — that is the classic
            # discriminator from iron deficiency, where cells are small *and*
            # variable. Widening RDW here would explain away the one number
            # that says the trait is not the whole story.
            Effect(
                pattern=r"^rdw|distribution width",
                note=(
                    "RDW is typically normal in thalassemia trait — the small "
                    "cells are uniformly small. A raised RDW alongside a low "
                    "MCV points to an additional cause, commonly iron "
                    "deficiency, rather than being explained by the trait."
                ),
            ),
            Effect(
                pattern=r"^mcv|mean corpuscular volume",
                note=(
                    "A low MCV is expected with thalassemia trait, typically "
                    "60–79 fL. What matters is change from your own baseline, "
                    "not the population floor."
                ),
                band=(60.0, 79.0),
                units="fL",
            ),
            Effect(
                pattern=r"^mch\b|mean corpuscular hgb(?! concentr)|mean corpuscular hemoglobin(?! concentration)",
                note=(
                    "A low MCH accompanies the small red cells of thalassemia "
                    "trait, typically 19–26 pg."
                ),
                band=(19.0, 26.0),
                units="pg",
            ),
            Effect(
                pattern=r"^rbc|red cell count|red blood cell|red cells",
                note=(
                    "The red cell count is normal or raised in thalassemia "
                    "trait. A low count alongside a low MCV points elsewhere, "
                    "usually to iron deficiency."
                ),
            ),
            Effect(
                pattern=r"^hemoglobin$|^hemoglobin \(hgb\)|^hgb\b|hgb bld",
                note=(
                    "Hemoglobin runs mildly low in beta thalassemia trait, "
                    "often 11–13.5 g/dL, and is usually normal in alpha trait."
                ),
                band=(11.0, 13.5),
                units="g/dL",
            ),
        ),
    ),
    Condition(
        id="gilbert-syndrome",
        label="Gilbert syndrome",
        summary=(
            "A common inherited variant of bilirubin conjugation, present in "
            "roughly 5% of people. Raises unconjugated bilirubin and affects "
            "nothing else; liver enzymes stay normal."
        ),
        color="#eda100",
        source="StatPearls: Gilbert Syndrome (NCBI Bookshelf)",
        effects=(
            Effect(
                pattern=r"bilirubin",
                note=(
                    "Bilirubin up to about 3 mg/dL is expected with Gilbert "
                    "syndrome, and rises with fasting or illness. Normal ALT "
                    "and AST alongside it is the reassuring pattern."
                ),
                band=(0.2, 3.0),
                units="mg/dL",
            ),
        ),
    ),
    Condition(
        id="duffy-null-anc",
        label="Duffy-null neutrophil count",
        summary=(
            "Also called benign ethnic neutropenia. A Duffy-null genotype, "
            "common in people of African ancestry, gives a lower neutrophil "
            "count with no increase in infection risk."
        ),
        color="#22b8cf",
        source=(
            "Merz & Barrett et al., 'Duffy-null associated neutrophil count', "
            "Blood Advances 2023; ASH guidance on benign ethnic neutropenia"
        ),
        effects=(
            Effect(
                pattern=r"neutrophil|abs\.? neut|^anc\b",
                note=(
                    "A neutrophil count of roughly 1.0–1.5 ×10³/µL is the "
                    "expected range with a Duffy-null genotype, below the "
                    "standard laboratory floor but not neutropenia."
                ),
                band=(1.0, 1.5),
                units="10^3/uL",
            ),
            Effect(
                pattern=r"^wbc|white cell|white blood|leuk",
                note=(
                    "The total white count follows the neutrophil count down "
                    "and can sit just under the standard lower limit."
                ),
            ),
        ),
    ),
    Condition(
        id="high-muscle-mass",
        label="High muscle mass or creatine use",
        summary=(
            "Muscle turnover produces creatinine, so a muscular build, heavy "
            "training, or creatine supplementation raises it without any "
            "change in kidney function."
        ),
        color="#d6409f",
        source=(
            "KDIGO 2024 CKD guideline, on non-GFR determinants of creatinine; "
            "Baxmann et al., Clin J Am Soc Nephrol 2008"
        ),
        effects=(
            Effect(
                pattern=r"^creatinine|serum creatinine",
                note=(
                    "Creatinine runs higher with more muscle — roughly up to "
                    "1.5 mg/dL — with no loss of kidney function. Cystatin C "
                    "is the measurement that avoids this."
                ),
                band=(0.6, 1.5),
                units="mg/dL",
            ),
            Effect(
                pattern=r"egfr|ckd.?epi|^egf result",
                note=(
                    "eGFR is calculated from creatinine, so a muscular build "
                    "makes it read low. It understates kidney function here "
                    "rather than measuring it."
                ),
            ),
        ),
    ),
    Condition(
        id="biotin-supplement",
        label="Biotin supplement",
        summary=(
            "High-dose biotin interferes with many immunoassays. This is a "
            "measurement problem, not a shifted range, so no band is drawn — "
            "the affected results may simply be wrong."
        ),
        color="#c9a227",
        source="FDA Safety Communication, biotin interference with lab tests (2019)",
        effects=(
            Effect(
                pattern=r"thyroid stimulating|^tsh",
                note=(
                    "Biotin can push TSH falsely low. Stopping biotin for a "
                    "few days before a draw removes the interference."
                ),
            ),
            Effect(
                pattern=r"t4|thyroxine|^t3\b|triiodothyronine",
                note="Biotin can push thyroid hormone results falsely high.",
            ),
            Effect(
                pattern=r"troponin",
                note=(
                    "Biotin can push troponin falsely LOW, which is the "
                    "dangerous direction — it can mask cardiac injury."
                ),
            ),
        ),
    ),
    Condition(
        id="non-fasting-draw",
        label="Non-fasting draw",
        summary=(
            "Eating before a draw raises triglycerides and glucose. Affects "
            "the reading, not the person."
        ),
        color="#7f8fa6",
        source="NCEP ATP III; Nordestgaard et al., Eur Heart J 2016 on non-fasting lipids",
        effects=(
            Effect(
                pattern=r"triglyceride|trigl",
                note=(
                    "Triglycerides rise after a meal and can stay up for "
                    "several hours; a fasting draw is the comparable one."
                ),
            ),
            Effect(
                pattern=r"^glucose|blood sugar",
                note=(
                    "Glucose reflects the last meal. Fasting glucose and "
                    "HbA1c are the interpretable measures."
                ),
            ),
        ),
    ),
)

_COMPILED: tuple[tuple[Condition, Effect, re.Pattern], ...] = tuple(
    (condition, effect, re.compile(effect.pattern))
    for condition in CONDITIONS
    for effect in condition.effects
)

def condition_options(selected: list[str] | None = None) -> list[dict]:
    """Checklist options: ticked conditions first, each group alphabetical.

    The authored order of `CONDITIONS` is a table of contents, not a ranking,
    and it leaves the reader scanning for a name. Alphabetical gives every
    condition a predictable place; floating the ticked ones keeps what is
    currently in play together at the top as the list grows.

    Nothing here touches the colours or the bands — those are fields on each
    condition, so re-ordering the control cannot move them.
    """
    chosen = set(selected or ())
    ordered = sorted(CONDITIONS, key=lambda c: (c.id not in chosen, c.label.lower()))
    return [{"label": c.label, "value": c.id} for c in ordered]


CONDITION_OPTIONS = condition_options()


def condition_by_id(condition_id: str) -> Condition | None:
    return next((c for c in CONDITIONS if c.id == condition_id), None)


def selected_conditions(selected: list[str] | None) -> list[Condition]:
    """The chosen conditions, in table order so colours stay stable."""
    chosen = set(selected or ())
    return [c for c in CONDITIONS if c.id in chosen]


@dataclass(frozen=True)
class AppliedEffect:
    """One condition's effect on one metric, with its band in that metric's units."""

    condition: Condition
    note: str
    band: tuple[float, float] | None


def effects_for(
    test_name: str, units: str, selected: list[str] | None
) -> list[AppliedEffect]:
    """Every selected condition's effect on this metric.

    A band is dropped rather than guessed when it cannot be converted into the
    metric's units — the same rule the reference ranges follow, and for the
    same reason: rescaling a boundary wrongly is worse than omitting it.
    """
    if not test_name or not selected:
        return []
    chosen = set(selected)
    lowered = test_name.strip().lower()
    applied: list[AppliedEffect] = []
    seen: set[str] = set()

    for condition, effect, pattern in _COMPILED:
        if condition.id not in chosen or condition.id in seen:
            continue
        if not pattern.search(lowered):
            continue
        seen.add(condition.id)  # first matching effect per condition wins
        band = effect.band
        if band and effect.units and units:
            low = convert(band[0], effect.units, units)
            high = convert(band[1], effect.units, units)
            band = (low, high) if low is not None and high is not None else None
        applied.append(AppliedEffect(condition=condition, note=effect.note, band=band))
    return applied


def conditions_affecting(
    metrics: dict, selected: list[str] | None
) -> dict[str, list[AppliedEffect]]:
    """Effects per metric name, for the metrics any selected condition touches."""
    if not selected:
        return {}
    out: dict[str, list[AppliedEffect]] = {}
    for name, series in metrics.items():
        applied = effects_for(name, getattr(series, "units", ""), selected)
        if applied:
            out[name] = applied
    return out


def metrics_affected_by(metrics: dict, condition_id: str) -> set[str]:
    """The metric names one condition touches, whether or not it draws a band.

    A note-only condition still answers "which results does this bear on?" —
    biotin interference is a reason to look at the thyroid panel even though
    nothing is shaded on it.
    """
    return set(conditions_affecting(metrics, [condition_id]))
