from lab_timeseries_grapher.synonyms import SYNONYM_RULES, format_synonyms, synonyms_for


class TestSynonymsFor:
    def test_known_abbreviation(self):
        assert "SGPT" in synonyms_for("ALT (sgpt)")

    def test_matching_is_case_insensitive(self):
        assert synonyms_for("alt") == synonyms_for("ALT")

    def test_unknown_test_returns_empty(self):
        assert synonyms_for("Fictional Assay 9000") == ()

    def test_blank_name(self):
        assert synonyms_for("") == ()

    def test_a_test_is_not_its_own_synonym(self):
        assert "MCV" not in synonyms_for("MCV")
        assert "mean corpuscular volume" in synonyms_for("MCV")


class TestRuleOrdering:
    """Narrower patterns must be reached before broader ones."""

    def test_non_hdl_does_not_match_hdl(self):
        names = synonyms_for("Non-hdl-cholesterol")
        assert "non-HDL-C" in names
        assert "high-density lipoprotein" not in names

    def test_hdl_large_does_not_match_plain_hdl(self):
        assert "large HDL particles" in synonyms_for("HDL Large")

    def test_ldl_particle_number_is_not_plain_ldl(self):
        names = synonyms_for("LDL Particle Number")
        assert "LDL-P" in names
        assert "low-density lipoprotein" not in names

    def test_bun_creatinine_ratio_is_not_bun(self):
        names = synonyms_for("Bun Creatinine Ratio")
        assert "BUN/creatinine ratio" in names
        assert "blood urea nitrogen" not in names

    def test_a1c_is_not_plain_hemoglobin(self):
        names = synonyms_for("Hemoglobin A1C")
        assert "HbA1c" in names
        assert "haemoglobin" not in names

    def test_mchc_is_not_mch(self):
        assert "mean corpuscular hemoglobin concentration" in synonyms_for("MCHC")
        assert "mean corpuscular volume" not in synonyms_for("MCH")


class TestClinicalAccuracy:
    """A percentage differential is not an absolute count; offering 'ANC'
    for a percentage would misname the measurement."""

    def test_percentage_neutrophils_are_not_called_anc(self):
        for name in ("% Neutrophils", "Neutrophils %", "Neutrophils, Percent",
                     "Neutrophils Leuk Nfr Bld Auto"):
            names = synonyms_for(name)
            assert "ANC" not in names, name
            assert "absolute neutrophil count" not in names, name
            assert "polys" in names, name

    def test_absolute_neutrophils_are_called_anc(self):
        for name in ("Absolute Neutrophils", "ANC (absolute Neutrophils)",
                     "Abs. Neut Ct.", "Neutrophils, Absolute Count"):
            assert "absolute neutrophil count" in synonyms_for(name), name


class TestFormatSynonyms:
    def test_renders_a_prefixed_list(self):
        assert format_synonyms("MCV").startswith("Also known as: ")

    def test_empty_for_unknown(self):
        assert format_synonyms("Fictional Assay 9000") == ""


class TestRuleTable:
    def test_every_rule_supplies_at_least_one_name(self):
        for pattern, names in SYNONYM_RULES:
            assert names, pattern

    def test_no_duplicate_names_within_a_rule(self):
        for pattern, names in SYNONYM_RULES:
            assert len(set(names)) == len(names), pattern
