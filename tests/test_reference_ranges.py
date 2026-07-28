import pytest

from lab_timeseries_grapher.reference_ranges import (
    Profile,
    canonical_units,
    convert,
    describe_reference,
    reference_for,
    reference_in_units,
)

MALE60 = Profile(age=60, sex="male")


class TestReferenceLookup:
    def test_known_test(self):
        ref = reference_for("ALT (sgpt)", MALE60)
        assert (ref.low, ref.high, ref.units) == (4.0, 36.0, "U/L")

    def test_unknown_test_defers_to_lab(self):
        assert reference_for("Fictional Assay 9000", MALE60) is None

    def test_particle_assays_defer_to_lab(self):
        for name in ("LDL Particle Number", "HDL Large", "Lipoprotein (a)"):
            assert reference_for(name, MALE60) is None, name

    def test_blank_name(self):
        assert reference_for("", MALE60) is None


class TestSexSpecific:
    def test_hemoglobin_differs_by_sex(self):
        male = reference_for("Hemoglobin", Profile(60, "male"))
        female = reference_for("Hemoglobin", Profile(60, "female"))
        assert male.band == (13.0, 18.0)
        assert female.band == (12.0, 16.0)


class TestAgeSpecific:
    @pytest.mark.parametrize("age,upper", [(45, 2.5), (55, 3.5), (65, 4.5), (75, 6.5)])
    def test_psa_upper_limit_rises_with_age(self, age, upper):
        assert reference_for("PSA", Profile(age, "male")).high == upper

    def test_esr_widens_after_seventy(self):
        assert reference_for("Sed Rate", Profile(60, "male")).high == 14.0
        assert reference_for("Sed Rate", Profile(75, "male")).high == 22.0


class TestOrdering:
    def test_non_hdl_is_not_hdl(self):
        assert reference_for("Non-hdl-cholesterol", MALE60).high == 130.0

    def test_a1c_is_not_hemoglobin(self):
        assert reference_for("Hemoglobin A1C", MALE60).high == 5.7

    def test_percentage_differential_is_not_the_absolute_count(self):
        pct = reference_for("% Neutrophils", MALE60)
        absolute = reference_for("Absolute Neutrophils", MALE60)
        assert (pct.low, pct.high, pct.units) == (40.0, 60.0, "%")
        assert absolute.units == "cells/µL"


class TestUnitReconciliation:
    """Applying a cells/µL range to a value recorded in 10^3/µL would read
    2.7 as critically low, so units must reconcile or the lab range stands."""

    def test_canonical_spellings_collapse(self):
        for spelling in ("10^3/µL", "K/mcL", "Thousand/uL", "x10E3/uL", "x10(9)/L"):
            assert canonical_units(spelling) == "k/ul", spelling

    def test_absolute_count_is_scaled_not_misapplied(self):
        ref = reference_in_units(reference_for("Absolute Neutrophils", MALE60), "10^3/µL")
        assert ref.band == (1.5, 8.0)

    def test_same_units_pass_through(self):
        ref = reference_in_units(reference_for("Abs. Neut Ct.", MALE60), "cells/µL")
        assert ref.band == (1500.0, 8000.0)

    def test_irreconcilable_units_defer_to_lab(self):
        # ng/dL cannot be converted to mg/dL without an assay-specific factor.
        assert reference_in_units(reference_for("T4, Free", MALE60), "mg/dL") is None

    def test_conversion_returns_none_when_unknown(self):
        assert convert(1.0, "ng/dL", "mg/dL") is None
        assert convert(2.0, "g/dL", "g/L") == 20.0


class TestDescribeReference:
    def test_two_sided(self):
        assert describe_reference(reference_for("ALT", MALE60)) == "4–36 U/L"

    def test_upper_bound_only(self):
        assert "below 100" in describe_reference(reference_for("LDL-Cholesterol", MALE60))

    def test_lower_bound_only(self):
        assert "above 40" in describe_reference(reference_for("HDL-Cholesterol", MALE60))

    def test_none(self):
        assert describe_reference(None) == ""
