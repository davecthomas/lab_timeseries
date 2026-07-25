import pandas as pd
import pytest

from lab_timeseries_grapher import commentary
from lab_timeseries_grapher.commentary import (
    CommentaryError,
    build_prompt,
    format_metric,
    generate_commentary,
    is_configured,
    load_skill_prompt,
    skill_path,
    strip_frontmatter,
)
from lab_timeseries_grapher.data import MetricSeries


def make_metric(name="Ferritin", values=(82.0, 31.0), band=(30.0, 400.0), panel="Other"):
    dates = pd.date_range("2021-01-01", periods=len(values), freq="YS")
    return MetricSeries(
        name=name,
        dates=list(dates),
        values=list(values),
        display_values=[str(v) for v in values],
        band=band,
        units="ng/mL",
        panel=panel,
    )


class TestStripFrontmatter:
    def test_removes_yaml_block(self):
        assert strip_frontmatter("---\nname: x\n---\nBody here") == "Body here"

    def test_passes_through_without_frontmatter(self):
        assert strip_frontmatter("Just a body") == "Just a body"

    def test_unterminated_frontmatter_kept(self):
        assert strip_frontmatter("---\nname: x") == "---\nname: x"


class TestSkillPrompt:
    def test_skill_file_exists(self):
        assert skill_path().is_file()

    def test_edits_take_effect_without_restart(self, tmp_path, monkeypatch):
        edited = tmp_path / "SKILL.md"
        edited.write_text("---\nname: x\n---\nFirst wording")
        monkeypatch.setattr(commentary, "skill_path", lambda: edited)
        assert load_skill_prompt() == "First wording"
        edited.write_text("---\nname: x\n---\nSecond wording")
        assert load_skill_prompt() == "Second wording"

    def test_prompt_has_no_frontmatter_and_names_the_role(self):
        prompt = load_skill_prompt()
        assert not prompt.startswith("---")
        assert "Bloodwork Analysis Helper" in prompt
        assert "not a diagnosis" in prompt.lower()


class TestFormatMetric:
    def test_includes_range_units_and_points(self):
        text = format_metric(make_metric())
        assert "### Ferritin" in text
        assert "Units: ng/mL" in text
        assert "Reference range: 30 to 400" in text
        assert "2021-01-01: 82.0" in text

    def test_flags_out_of_range_points(self):
        text = format_metric(make_metric(values=(10.0, 500.0)))
        assert "[LOW]" in text
        assert "[HIGH]" in text

    def test_notes_missing_range(self):
        text = format_metric(make_metric(band=None))
        assert "not supplied by the lab" in text

    def test_cutoff_limits_points(self):
        text = format_metric(make_metric(), cutoff=pd.Timestamp("2021-06-01"))
        assert "2021-01-01" not in text
        assert "2022-01-01" in text

    def test_empty_window_is_stated(self):
        text = format_metric(make_metric(), cutoff=pd.Timestamp("2030-01-01"))
        assert "none in the selected date window" in text


class TestBuildPrompt:
    def test_includes_each_selected_metric(self):
        metrics = {"Ferritin": make_metric(), "Glucose": make_metric(name="Glucose")}
        prompt = build_prompt(metrics, ["Ferritin", "Glucose"])
        assert "### Ferritin" in prompt
        assert "### Glucose" in prompt
        assert "2 lab metric(s)" in prompt

    def test_unknown_names_are_skipped(self):
        prompt = build_prompt({"Ferritin": make_metric()}, ["Ferritin", "Nope"])
        assert "1 lab metric(s)" in prompt

    def test_empty_selection_raises(self):
        with pytest.raises(CommentaryError, match="at least one metric"):
            build_prompt({"Ferritin": make_metric()}, [])

    def test_cutoff_named_in_header(self):
        prompt = build_prompt(
            {"Ferritin": make_metric()}, ["Ferritin"], cutoff=pd.Timestamp("2022-01-01")
        )
        assert "results since 2022-01-01" in prompt

    def test_all_results_named_without_cutoff(self):
        prompt = build_prompt({"Ferritin": make_metric()}, ["Ferritin"])
        assert "all available results" in prompt


class FakeClient:
    def __init__(self, response="## Summary\nLooks stable.", error=None):
        self.response = response
        self.error = error
        self.calls = []

    def send_prompt(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        if self.error:
            raise self.error
        return self.response


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(commentary, "load_env", lambda: None)


class TestIsConfigured:
    def test_true_with_key(self, configured):
        assert is_configured() is True

    def test_false_without_key(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "")
        monkeypatch.setattr(commentary, "load_env", lambda: None)
        assert is_configured() is False


class TestGenerateCommentary:
    def test_returns_model_text(self, configured, monkeypatch):
        client = FakeClient()
        monkeypatch.setattr(commentary, "_completions_client", lambda: client)
        out = generate_commentary({"Ferritin": make_metric()}, ["Ferritin"])
        assert out == "## Summary\nLooks stable."

    def test_sends_skill_as_system_prompt(self, configured, monkeypatch):
        client = FakeClient()
        monkeypatch.setattr(commentary, "_completions_client", lambda: client)
        generate_commentary({"Ferritin": make_metric()}, ["Ferritin"])
        _, kwargs = client.calls[0]
        assert "Bloodwork Analysis Helper" in kwargs["system_prompt"]

    def test_missing_key_raises_user_safe_error(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "")
        monkeypatch.setattr(commentary, "load_env", lambda: None)
        with pytest.raises(CommentaryError, match="ANTHROPIC_API_KEY"):
            generate_commentary({"Ferritin": make_metric()}, ["Ferritin"])

    def test_provider_failure_is_wrapped(self, configured, monkeypatch):
        client = FakeClient(error=RuntimeError("upstream 500"))
        monkeypatch.setattr(commentary, "_completions_client", lambda: client)
        with pytest.raises(CommentaryError, match="upstream 500"):
            generate_commentary({"Ferritin": make_metric()}, ["Ferritin"])

    def test_empty_response_raises(self, configured, monkeypatch):
        client = FakeClient(response="   ")
        monkeypatch.setattr(commentary, "_completions_client", lambda: client)
        with pytest.raises(CommentaryError, match="empty response"):
            generate_commentary({"Ferritin": make_metric()}, ["Ferritin"])

    def test_empty_selection_raises_before_calling_provider(self, configured, monkeypatch):
        client = FakeClient()
        monkeypatch.setattr(commentary, "_completions_client", lambda: client)
        with pytest.raises(CommentaryError):
            generate_commentary({"Ferritin": make_metric()}, [])
        assert client.calls == []
