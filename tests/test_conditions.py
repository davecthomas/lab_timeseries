import pandas as pd
import pytest

from lab_timeseries_grapher import conditions
from lab_timeseries_grapher.data import MetricSeries
from lab_timeseries_grapher.figures import make_figure
from lab_timeseries_grapher.layout import chart_card, condition_legend

ALL_IDS = [c.id for c in conditions.CONDITIONS]


def series(name="MCV", units="fL", band=(80.0, 100.0), value=70.0):
    return MetricSeries(
        name=name,
        dates=[pd.Timestamp("2024-01-01")],
        values=[value],
        display_values=[f"{value:g}"],
        band=band,
        units=units,
        panel="CBC",
        lab_band=band,
    )


class TestTable:
    def test_every_condition_has_a_source(self):
        for c in conditions.CONDITIONS:
            assert c.source.strip(), c.id

    def test_every_condition_has_a_unique_id(self):
        assert len({c.id for c in conditions.CONDITIONS}) == len(conditions.CONDITIONS)

    def test_every_condition_has_a_unique_colour(self):
        colours = [c.color for c in conditions.CONDITIONS]
        assert len(set(colours)) == len(colours)

    def test_no_condition_reuses_a_status_colour(self):
        """Condition hues must not read as the normal band or the flag."""
        reserved = {"#0ca30c", "#d03b3b", "#3987e5"}
        for c in conditions.CONDITIONS:
            assert c.color.lower() not in reserved, c.id

    def test_every_effect_has_a_note(self):
        for c in conditions.CONDITIONS:
            for e in c.effects:
                assert e.note.strip(), f"{c.id}/{e.pattern}"

    def test_a_band_always_carries_units(self):
        """An unqualified band cannot be reconciled with a metric's units."""
        for c in conditions.CONDITIONS:
            for e in c.effects:
                if e.band:
                    assert e.units, f"{c.id}/{e.pattern}"

    def test_bands_are_ordered_low_to_high(self):
        for c in conditions.CONDITIONS:
            for e in c.effects:
                if e.band:
                    assert e.band[0] < e.band[1], f"{c.id}/{e.pattern}"


class TestMatching:
    def test_thalassemia_matches_mcv(self):
        applied = conditions.effects_for("MCV", "fL", ["thalassemia-trait"])
        assert [a.condition.id for a in applied] == ["thalassemia-trait"]
        assert applied[0].band == (60.0, 79.0)

    def test_mchc_is_not_treated_as_mch(self):
        """Different measurement; a band for MCH must not land on MCHC."""
        assert conditions.effects_for("MCHC", "g/dL", ["thalassemia-trait"]) == []

    def test_unselected_conditions_do_nothing(self):
        assert conditions.effects_for("MCV", "fL", ["gilbert-syndrome"]) == []

    def test_no_selection_does_nothing(self):
        assert conditions.effects_for("MCV", "fL", []) == []
        assert conditions.effects_for("MCV", "fL", None) == []

    def test_an_unaffected_metric_gets_nothing(self):
        assert conditions.effects_for("Sodium", "mmol/L", ALL_IDS) == []

    def test_gilbert_matches_bilirubin(self):
        applied = conditions.effects_for("Bilirubin, Total", "mg/dL", ALL_IDS)
        assert [a.condition.id for a in applied] == ["gilbert-syndrome"]

    def test_duffy_matches_absolute_neutrophils(self):
        applied = conditions.effects_for("ANC (absolute Neutrophils)", "x10^3/uL", ALL_IDS)
        assert [a.condition.id for a in applied] == ["duffy-null-anc"]

    def test_one_condition_contributes_once_per_metric(self):
        """Overlapping patterns within a condition must not stack notes."""
        for name in ("Hemoglobin", "MCV", "Absolute Neutrophils"):
            applied = conditions.effects_for(name, "", ALL_IDS)
            ids = [a.condition.id for a in applied]
            assert len(ids) == len(set(ids)), name

    def test_note_only_conditions_have_no_band(self):
        applied = conditions.effects_for("TSH", "mIU/L", ["biotin-supplement"])
        assert applied and applied[0].band is None
        assert applied[0].note


class TestUnits:
    def test_a_band_converts_into_the_metric_units(self):
        applied = conditions.effects_for("Absolute Neutrophils", "cells/uL", ["duffy-null-anc"])
        assert applied[0].band == (1000.0, 1500.0)

    def test_an_unconvertible_band_is_dropped_not_guessed(self):
        """Rescaling a boundary wrongly is worse than omitting it."""
        applied = conditions.effects_for("Absolute Neutrophils", "mg/dL", ["duffy-null-anc"])
        assert applied and applied[0].band is None
        assert applied[0].note  # the explanation still stands

    def test_matching_units_pass_through(self):
        applied = conditions.effects_for("MCV", "fL", ["thalassemia-trait"])
        assert applied[0].band == (60.0, 79.0)


class TestBandsAreAdditive:
    """The design rule: a condition never replaces the normal band and never
    changes a verdict. A ticked box must not be able to hide an abnormality.
    """

    def test_the_normal_band_survives(self):
        s = series()
        fig = make_figure(s, None, conditions.effects_for("MCV", "fL", ["thalassemia-trait"]))
        fills = [sh.fillcolor for sh in fig.layout.shapes]
        assert "#0ca30c" in fills  # the normal band
        assert "#a06cd5" in fills  # the condition band
        assert len(fig.layout.shapes) == 2

    def test_the_out_of_range_verdict_is_unchanged(self):
        """70 fL is low against 80-100 whether or not a condition explains it."""
        s = series(value=70.0)
        assert s.latest_status == "low"
        plain = make_figure(s, None, None)
        with_cond = make_figure(s, None, conditions.effects_for("MCV", "fL", ["thalassemia-trait"]))
        flagged = lambda f: [t for t in f.data if t.mode == "markers"]  # noqa: E731
        assert len(flagged(plain)) == len(flagged(with_cond)) == 1

    def test_no_conditions_draws_only_the_normal_band(self):
        fig = make_figure(series(), None, [])
        assert len(fig.layout.shapes) == 1

    def test_a_note_only_condition_draws_no_band(self):
        s = series(name="TSH", units="mIU/L", band=(0.4, 4.0), value=2.0)
        fig = make_figure(s, None, conditions.effects_for("TSH", "mIU/L", ["biotin-supplement"]))
        assert len(fig.layout.shapes) == 1  # normal band only

    def test_condition_bands_sit_below_the_data(self):
        fig = make_figure(series(), None, conditions.effects_for("MCV", "fL", ALL_IDS))
        assert all(sh.layer == "below" for sh in fig.layout.shapes)


class TestCardText:
    def test_the_note_appears_alongside_the_band(self):
        card = chart_card(series(), None, conditions.effects_for("MCV", "fL", ["thalassemia-trait"]))
        text = str(card)
        assert "Thalassemia trait" in text
        assert "60–79 fL" in text

    def test_a_card_without_conditions_says_nothing_about_them(self):
        assert "Thalassemia" not in str(chart_card(series(), None, None))

    def test_note_only_conditions_still_annotate(self):
        s = series(name="Troponin", units="ng/mL", band=(0.0, 0.04), value=0.01)
        card = chart_card(s, None, conditions.effects_for("Troponin", "ng/mL", ["biotin-supplement"]))
        assert "falsely LOW" in str(card)


class TestLegend:
    def test_hidden_when_nothing_is_selected(self):
        assert condition_legend([]).style == {"display": "none"}
        assert condition_legend(None).style == {"display": "none"}

    def test_shown_with_a_style_a_callback_can_read(self):
        legend = condition_legend(["thalassemia-trait"])
        assert legend.style == {"display": "flex"}

    def test_lists_only_the_selected_conditions(self):
        text = str(condition_legend(["gilbert-syndrome"]))
        assert "Gilbert syndrome" in text
        assert "Thalassemia trait" not in text

    def test_order_follows_the_table_so_colours_stay_put(self):
        chosen = conditions.selected_conditions(["non-fasting-draw", "thalassemia-trait"])
        assert [c.id for c in chosen] == ["thalassemia-trait", "non-fasting-draw"]

    def test_note_only_conditions_are_marked_as_such(self):
        assert "note only" in str(condition_legend(["biotin-supplement"]))

    def test_band_conditions_are_not_marked_note_only(self):
        assert "note only" not in str(condition_legend(["thalassemia-trait"]))

    def test_the_caveat_is_always_present(self):
        assert "Not a diagnosis" in str(condition_legend(ALL_IDS))


class TestConditionOptions:
    """The checklist: ticked conditions first, alphabetical within each group."""

    def _labels(self, options):
        return [o["label"] for o in options]

    def test_unselected_is_alphabetical(self):
        labels = self._labels(conditions.condition_options())
        assert labels == sorted(labels, key=str.lower)

    def test_selected_float_to_the_top(self):
        options = conditions.condition_options(["non-fasting-draw"])
        assert options[0]["value"] == "non-fasting-draw"

    def test_each_group_is_alphabetical(self):
        options = conditions.condition_options(["thalassemia-trait", "gilbert-syndrome"])
        labels = self._labels(options)
        assert labels[:2] == ["Gilbert syndrome", "Thalassemia trait"]
        assert labels[2:] == sorted(labels[2:], key=str.lower)

    def test_every_condition_is_still_offered(self):
        for selected in ([], ["biotin-supplement"], ALL_IDS):
            values = [o["value"] for o in conditions.condition_options(selected)]
            assert sorted(values) == sorted(ALL_IDS)

    def test_the_module_default_matches_no_selection(self):
        assert conditions.CONDITION_OPTIONS == conditions.condition_options()


class TestMetricsAffectedBy:
    def test_reports_the_metrics_one_condition_touches(self):
        metrics = {
            "MCV": series("MCV"),
            "Hemoglobin": series("Hemoglobin", "g/dL", (13.7, 17.5), 13.3),
            "Sodium": series("Sodium", "mmol/L", (135.0, 145.0), 140.0),
        }
        assert conditions.metrics_affected_by(metrics, "thalassemia-trait") == {
            "MCV",
            "Hemoglobin",
        }

    def test_a_note_only_condition_still_names_its_metrics(self):
        """Nothing is shaded for biotin, but those results are still the ones
        it bears on."""
        metrics = {"TSH": series("TSH", "mIU/L", (0.4, 4.0), 2.0), "MCV": series("MCV")}
        assert conditions.metrics_affected_by(metrics, "biotin-supplement") == {"TSH"}

    def test_an_unknown_condition_touches_nothing(self):
        assert conditions.metrics_affected_by({"MCV": series()}, "not-a-condition") == set()


class TestConditionReading:
    """The card reports the latest value against the condition band as well as
    the population band — the screenshot case: low for the reference, normal
    for thalassemia trait."""

    def _hemoglobin(self, value=13.3):
        return series("Hemoglobin (hgb)", "g/dL", (13.7, 17.5), value)

    def _card_text(self, value=13.3, condition_ids=("thalassemia-trait",)):
        s = self._hemoglobin(value)
        return str(chart_card(s, None, conditions.effects_for(s.name, s.units, list(condition_ids))))

    def test_it_reports_normal_for_the_condition_while_low_overall(self):
        text = self._card_text()
        assert "▼ low" in text  # the population verdict is unchanged
        assert "normal for Thalassemia trait" in text

    def test_below_the_condition_band_too_reads_low_for_it(self):
        assert "▼ low for Thalassemia trait" in self._card_text(value=9.0)

    def test_above_the_condition_band_reads_high_for_it(self):
        assert "▲ high for Thalassemia trait" in self._card_text(value=16.0)

    def test_a_note_only_condition_adds_no_reading(self):
        s = series("Troponin I", "ng/mL", (0.0, 0.04), 0.01)
        text = str(chart_card(s, None, conditions.effects_for(s.name, s.units, ["biotin-supplement"])))
        assert "for Biotin supplement" not in text

    def test_no_conditions_selected_adds_no_reading(self):
        assert "normal for" not in str(chart_card(self._hemoglobin(), None, None))

    def test_the_sidebar_verdict_is_untouched(self):
        """A condition may add a reading; it may never edit the flag — the rule
        that keeps a ticked checkbox from hiding a real abnormality."""
        from lab_timeseries_grapher.layout import build_table_rows

        rows = build_table_rows({"Hemoglobin (hgb)": self._hemoglobin()})
        assert rows[0]["status"] == "low"
        assert rows[0]["status_glyph"] == "▼"


class TestConditionsAffecting:
    def test_reports_only_touched_metrics(self):
        metrics = {"MCV": series("MCV"), "Sodium": series("Sodium", "mmol/L", (135.0, 145.0), 140.0)}
        out = conditions.conditions_affecting(metrics, ["thalassemia-trait"])
        assert list(out) == ["MCV"]

    def test_empty_without_a_selection(self):
        assert conditions.conditions_affecting({"MCV": series()}, []) == {}

    @pytest.mark.parametrize("condition_id", ALL_IDS)
    def test_every_condition_matches_something_realistic(self, condition_id):
        """A condition nobody's metrics can match would be dead weight."""
        realistic = {
            n: series(n, "", None, 1.0)
            for n in (
                "MCV", "MCH", "Hemoglobin", "RBC", "Bilirubin, Total",
                "Absolute Neutrophils", "WBC", "Creatinine", "EGFR", "TSH",
                "T4, Free", "Troponin I", "Triglycerides", "Glucose",
            )
        }
        assert conditions.conditions_affecting(realistic, [condition_id])


class TestRdwIsNotWidened:
    """RDW is the discriminator between thalassemia trait and iron deficiency:
    the trait makes cells uniformly small, so it does not raise RDW. Giving RDW
    a widened band would explain away the one number saying the trait is not
    the whole story.
    """

    def test_rdw_gets_a_note_but_never_a_band(self):
        applied = conditions.effects_for("RDW", "%", ["thalassemia-trait"])
        assert len(applied) == 1
        assert applied[0].band is None
        assert applied[0].note

    def test_the_note_points_away_from_the_trait(self):
        note = conditions.effects_for("RDW", "%", ["thalassemia-trait"])[0].note
        assert "additional cause" in note
        assert "iron" in note.lower()

    def test_a_high_rdw_keeps_its_flag(self):
        """No band means nothing can soften the population verdict."""
        s = series(name="RDW", units="%", band=(12.0, 14.0), value=15.0)
        assert s.latest_status == "high"
        fig = make_figure(s, None, conditions.effects_for("RDW", "%", ["thalassemia-trait"]))
        assert len(fig.layout.shapes) == 1  # the normal band alone

    @pytest.mark.parametrize(
        "name", ["RDW", "RDW (rbc Distribution Width)", "Red Cell Distribution Width"]
    )
    def test_rdw_spellings_do_not_fall_through_to_the_rbc_rule(self, name):
        """'RDW (rbc Distribution Width)' contains 'rbc'; the count note would
        be wrong here and must not win."""
        applied = conditions.effects_for(name, "%", ["thalassemia-trait"])
        assert len(applied) == 1, name
        assert "RDW is typically normal" in applied[0].note, name

    def test_the_rbc_rule_still_matches_actual_counts(self):
        for name in ("RBC", "Red Cell Count", "Red Blood Cell Count"):
            applied = conditions.effects_for(name, "", ["thalassemia-trait"])
            assert applied and "red cell count" in applied[0].note.lower(), name
