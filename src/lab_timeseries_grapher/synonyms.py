"""Alternate names and abbreviations for lab tests.

**This file is authored, not derived from the labs CSV.** Every other piece of
help text in the app comes out of the data; these are standard nomenclature —
"SGPT" for ALT, "BUN" for urea nitrogen — supplied so a result can be matched
to whatever a different lab, a doctor, or a paper calls it. They name tests;
they do not interpret results. Correct or extend the table below freely.

Rules are ordered and the first match wins, so narrower patterns must come
before broader ones: "Non-hdl-cholesterol" has to be matched before the rule
for HDL, and "HDL Large" before plain HDL.
"""

from __future__ import annotations

import re

# (pattern, alternate names). Patterns run against a lower-cased test name.
SYNONYM_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    # --- Liver ---
    (r"^alt\b|sgpt", ("ALT", "SGPT", "alanine aminotransferase")),
    (r"^ast\b|sgot", ("AST", "SGOT", "aspartate aminotransferase")),
    (r"alk.*phos", ("ALP", "alk phos", "alkaline phosphatase")),
    (r"bilirubin", ("TBIL", "total bilirubin")),
    (r"^a\s*g\s*ratio|albumin.*globulin", ("A/G ratio", "albumin/globulin ratio")),
    (r"globulin", ("GLOB",)),
    (r"albumin", ("ALB",)),
    (r"total protein|^protein, total|protein.*total", ("TP", "total protein", "serum protein")),
    # --- Kidney / electrolytes ---
    (r"bun.*creatinine|creatinine.*ratio", ("BUN/creatinine ratio",)),
    (r"^bun\b|urea nitrogen", ("BUN", "blood urea nitrogen", "urea")),
    (r"creatinine", ("Cr", "serum creatinine")),
    (r"egfr|ckd.?epi|^egf result", ("eGFR", "GFR", "estimated glomerular filtration rate")),
    (r"^sodium|natrium", ("Na", "sodium")),
    (r"^potassium|kalium", ("K", "potassium")),
    (r"^chloride", ("Cl", "chloride")),
    (r"bicarbonate|carbon dioxide|^co2|co2, total|co2 content", ("HCO3", "bicarbonate", "total CO2")),
    (r"anion gap", ("AG", "anion gap")),
    (r"^calcium", ("Ca", "calcium")),
    (r"osmolality", ("Osm", "serum osmolality")),
    (r"uric acid", ("urate",)),
    # --- Glucose ---
    (r"hemoglobin a1c|a1c", ("HbA1c", "A1c", "glycated hemoglobin", "glycohemoglobin")),
    (r"glucose", ("blood sugar", "fasting glucose", "FBG")),
    # --- Lipids: narrower rules first ---
    (r"non.?hdl", ("non-HDL-C", "non-HDL cholesterol")),
    (r"apolipoprotein b|apo.?b", ("ApoB", "apolipoprotein B")),
    (r"lipoprotein ?\(a\)|^lp\(a\)", ("Lp(a)", "lipoprotein little a")),
    (r"ldl particle", ("LDL-P", "LDL particle number")),
    (r"ldl peak size", ("LDL peak particle size",)),
    (r"ldl (medium|small|large)", ("LDL subfraction",)),
    (r"hdl large", ("large HDL particles", "HDL-P large")),
    (r"chol.*hdl ratio|hdl ratio", ("cholesterol/HDL ratio", "TC/HDL ratio")),
    (r"vldl", ("VLDL", "very low-density lipoprotein")),
    (r"hdl", ("HDL", "high-density lipoprotein", "good cholesterol")),
    (r"ldl", ("LDL", "low-density lipoprotein", "bad cholesterol")),
    (r"triglyceride|trigl", ("TG", "trigs", "triglycerides")),
    (r"cholesterol|cholest", ("TC", "total cholesterol")),
    # --- CBC: differentials before the parent cell lines ---
    # A percentage differential is not the absolute count, so "ANC" must not
    # be offered for it. "Nfr" in these lab names is a number fraction.
    (
        r"(%|percent|nfr).*neutrophil|neutrophil.*(%|percent|nfr)",
        ("polys", "PMNs", "segs", "neutrophil percentage"),
    ),
    (
        r"neutrophil|abs\.? neut|^anc\b|preliminary abs neut",
        ("ANC", "absolute neutrophil count", "polys", "PMNs", "segs"),
    ),
    (r"lymphocyte", ("lymphs", "lymphocytes")),
    (r"monocyte", ("monos", "monocytes")),
    (r"eosinophil", ("eos", "eosinophils")),
    (r"basophil", ("basos", "basophils")),
    (
        r"immature granulocyte|^ig\b|promyelo|metamyelo",
        ("IG", "immature granulocytes", "promyelocytes/myelocytes/metamyelocytes"),
    ),
    (r"nucleated rbc|^nrbc", ("nRBC", "nucleated red blood cells")),
    (r"^mcv|mean corpuscular volume", ("MCV", "mean corpuscular volume")),
    (r"^mchc|mean corpuscular hgb concentr", ("MCHC", "mean corpuscular hemoglobin concentration")),
    (r"^mch\b|mean corpuscular hgb", ("MCH", "mean corpuscular hemoglobin")),
    (r"^rdw|distribution width", ("RDW", "red cell distribution width")),
    (r"^mpv|^pmv|platelet volume", ("MPV", "mean platelet volume")),
    (r"platelet|^plt", ("PLT", "platelets", "thrombocytes")),
    (r"hematocrit|^hct", ("HCT", "hematocrit", "packed cell volume")),
    (r"hemoglobin|^hgb|hdlc", ("HGB", "Hb", "haemoglobin")),
    (r"^rbc|red cell|red blood", ("RBC", "red blood cell count", "erythrocytes")),
    (r"^wbc|white cell|white blood|leuk", ("WBC", "white blood cell count", "leukocytes")),
    # --- Endocrine / other ---
    (r"thyroid stimulating|^tsh", ("TSH", "thyrotropin", "thyroid stimulating hormone")),
    (r"t4.*free|free.*t4", ("FT4", "free thyroxine")),
    (r"testost", ("testosterone", "total T")),
    (r"^psa|prostate", ("PSA", "prostate-specific antigen")),
    (r"vitamin d", ("25(OH)D", "25-hydroxyvitamin D", "calcidiol")),
    (r"c.?reactive protein", ("CRP", "C-reactive protein")),
    (r"sed rate|sedimentation", ("ESR", "sed rate", "erythrocyte sedimentation rate")),
    (r"prothrombin", ("PT", "protime", "prothrombin time")),
    (r"troponin", ("cTnI", "cardiac troponin")),
    (r"hepatitis c", ("anti-HCV", "HCV antibody")),
    (r"agatson|agatston|cardiac calcium", ("CAC score", "coronary artery calcium score")),
)

_COMPILED = tuple((re.compile(pattern), names) for pattern, names in SYNONYM_RULES)


def synonyms_for(test_name: str) -> tuple[str, ...]:
    """Alternate names for a test, or an empty tuple when none are known.

    The test's own name is filtered out, so a metric already called "MCV"
    does not list "MCV" as an alias of itself.
    """
    if not test_name:
        return ()
    lowered = test_name.strip().lower()
    for pattern, names in _COMPILED:
        if pattern.search(lowered):
            return tuple(n for n in names if n.lower() != lowered)
    return ()


def format_synonyms(test_name: str) -> str:
    """Alternate names as one display string, or '' when none are known."""
    names = synonyms_for(test_name)
    return f"Also known as: {', '.join(names)}" if names else ""
