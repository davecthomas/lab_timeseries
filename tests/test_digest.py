import pandas as pd

from lab_timeseries_grapher.data import MetricSeries
from lab_timeseries_grapher.digest import build_digest, match_metrics
from lab_timeseries_grapher.reference_ranges import Profile


def make_metric(name, values, band=(30.0, 400.0), panel="Iron", start="2021-01-01"):
    dates = pd.date_range(start, periods=len(values), freq="YS")
    return MetricSeries(
        name=name,
        dates=list(dates),
        values=list(values),
        display_values=[f"{v:g}" for v in values],
        band=band,
        units="ng/mL",
        panel=panel,
        lab_band=band,
    )


def sample():
    return {
        "Ferritin": make_metric("Ferritin", [82.0, 31.0, 22.0]),
        "HDL Cholesterol": make_metric("HDL Cholesterol", [55.0], (40.0, 100.0), "Lipids",
                                       start="2023-01-01"),
        "Non-HDL Cholesterol": make_metric("Non-HDL Cholesterol", [120.0], (0.0, 130.0),
                                           "Lipids", start="2023-01-01"),
        # Last drawn years before the others: out of range, but not *now*.
        "Old MCV": make_metric("Old MCV", [70.0], (80.0, 100.0), "CBC", start="2015-01-01"),
    }


def digest(**kwargs):
    return build_digest(sample(), Profile(), "labs.csv", **kwargs)


class TestMatch:
    def test_exact_name_does_not_pull_in_supersets(self):
        assert match_metrics(sample(), "hdl cholesterol") == ["HDL Cholesterol"]

    def test_substring_matches_several(self):
        assert match_metrics(sample(), "cholesterol") == ["HDL Cholesterol",
                                                          "Non-HDL Cholesterol"]


class TestOverview:
    def test_flags_only_current_out_of_range(self):
        text = digest()
        flagged = text.split("## Out of range now")[1].split("## All metrics")[0]
        assert "Ferritin" in flagged and "▼ LOW" in flagged
        assert "Old MCV" not in flagged

    def test_lists_every_metric_with_currency(self):
        text = digest()
        assert "- Old MCV | 70 ng/mL (2015-01-01) | — | 80–100 (lab) | ▼ LOW | 1 | no" in text
        assert "- Ferritin | 22 ng/mL (2023-01-01) | 31 | 30–400 (lab) | ▼ LOW | 3 | yes" in text


class TestHistory:
    def test_metric_history_is_oldest_first_with_flags(self):
        text = digest(queries=["ferritin"])
        rows = [ln for ln in text.splitlines() if ln.startswith("| 20")]
        assert rows == [
            "| 2021-01-01 | 82 |  |",
            "| 2022-01-01 | 31 |  |",
            "| 2023-01-01 | 22 | ▼ LOW |",
        ]

    def test_since_trims_the_window(self):
        text = digest(queries=["ferritin"], since=pd.Timestamp("2022-06-01"))
        assert "2021-01-01" not in text and "2023-01-01" in text

    def test_since_names_metrics_with_nothing_in_the_window(self):
        text = digest(panel="cbc", since=pd.Timestamp("2020-01-01"))
        assert "## Old MCV" not in text
        assert "Not measured since 2020-01-01: Old MCV." in text

    def test_out_of_range_selects_current_flags(self):
        text = digest(out_of_range=True)
        assert "## Ferritin" in text and "Old MCV" not in text

    def test_panel_selects_its_metrics(self):
        text = digest(panel="lipids")
        assert "## HDL Cholesterol" in text and "## Non-HDL Cholesterol" in text

    def test_unmatched_query_is_reported(self):
        assert "No metric matched: zinc" in digest(queries=["zinc"])
