"""Unit tests for test_generator.prompt_builder.

Covers:
- Output contains all required XML sections
- Functional and boundary counts are embedded correctly
- Ground truth data is serialized into the prompt
- Few-shot examples for both categories are present

Requirements: 9.5, 10.3, 12.1–12.4
"""

from __future__ import annotations

import pytest

from test_generator.models import TestCase
from test_generator.prompt_builder import build_prompt


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_test_cases() -> list[TestCase]:
    """A small set of TestCase objects for prompt construction."""
    return [
        TestCase(
            prompt="What are the opening hours?",
            expected="We are open from 9 AM to 9 PM every day.",
            id="tc-1",
            contexts=["Hours: 9 AM – 9 PM daily"],
        ),
        TestCase(
            prompt="Do you have vegan options?",
            expected="Yes, we offer several vegan dishes.",
            id="tc-2",
        ),
    ]


@pytest.fixture()
def minimal_prompt(sample_test_cases: list[TestCase]) -> str:
    """Build a prompt with typical parameters for reuse across tests."""
    return build_prompt(
        test_cases=sample_test_cases,
        app_description="A restaurant assistant chatbot",
        system_prompt="You are a helpful restaurant assistant.",
        business_metrics="Customer satisfaction, order accuracy",
        functional_count=5,
        boundary_count=3,
        num_questions_per_case=2,
        language="English",
    )


# ---------------------------------------------------------------------------
# XML section presence (Req 12.1)
# ---------------------------------------------------------------------------


class TestXMLSections:
    """The prompt must contain all required XML-tagged sections."""

    def test_instructions_section_present(self, minimal_prompt: str) -> None:
        assert "<instructions>" in minimal_prompt
        assert "</instructions>" in minimal_prompt

    def test_ground_truth_section_present(self, minimal_prompt: str) -> None:
        assert "<ground_truth>" in minimal_prompt
        assert "</ground_truth>" in minimal_prompt

    def test_application_context_section_present(self, minimal_prompt: str) -> None:
        assert "<application_context>" in minimal_prompt
        assert "</application_context>" in minimal_prompt

    def test_output_format_section_present(self, minimal_prompt: str) -> None:
        assert "<output_format>" in minimal_prompt
        assert "</output_format>" in minimal_prompt

    def test_examples_section_present(self, minimal_prompt: str) -> None:
        assert "<examples>" in minimal_prompt
        assert "</examples>" in minimal_prompt

    def test_chain_of_thought_present(self, minimal_prompt: str) -> None:
        """Req 12.2 — chain-of-thought instruction for scenario diversity."""
        assert "<chain_of_thought>" in minimal_prompt
        assert "</chain_of_thought>" in minimal_prompt


# ---------------------------------------------------------------------------
# Functional / boundary counts embedded (Req 11.2, 11.3, 11.4)
# ---------------------------------------------------------------------------


class TestCountEmbedding:
    """Functional and boundary counts must appear in the prompt text."""

    def test_functional_count_embedded(self, minimal_prompt: str) -> None:
        # The prompt should mention generating 5 functional test cases
        assert "5" in minimal_prompt
        # Verify it's associated with "functional"
        assert "functional" in minimal_prompt.lower()

    def test_boundary_count_embedded(self, minimal_prompt: str) -> None:
        # The prompt should mention generating 3 boundary test cases
        assert "3" in minimal_prompt
        assert "boundary" in minimal_prompt.lower()

    def test_zero_functional_count(self, sample_test_cases: list[TestCase]) -> None:
        prompt = build_prompt(
            test_cases=sample_test_cases,
            app_description="App",
            system_prompt="Sys",
            business_metrics="Metrics",
            functional_count=0,
            boundary_count=10,
            num_questions_per_case=2,
        )
        assert "0" in prompt or "only" in prompt.lower()
        assert "10" in prompt

    def test_zero_boundary_count(self, sample_test_cases: list[TestCase]) -> None:
        prompt = build_prompt(
            test_cases=sample_test_cases,
            app_description="App",
            system_prompt="Sys",
            business_metrics="Metrics",
            functional_count=10,
            boundary_count=0,
            num_questions_per_case=2,
        )
        assert "10" in prompt


# ---------------------------------------------------------------------------
# Ground truth serialized into prompt (Req 9.1, 9.4)
# ---------------------------------------------------------------------------


class TestGroundTruthSerialization:
    """Ground truth TestCase data must appear inside the prompt."""

    def test_prompt_field_values_present(self, minimal_prompt: str) -> None:
        assert "What are the opening hours?" in minimal_prompt
        assert "Do you have vegan options?" in minimal_prompt

    def test_expected_field_values_present(self, minimal_prompt: str) -> None:
        assert "We are open from 9 AM to 9 PM every day." in minimal_prompt
        assert "Yes, we offer several vegan dishes." in minimal_prompt

    def test_context_data_included_when_present(self, minimal_prompt: str) -> None:
        """Req 9.4 — contexts should be incorporated when available."""
        assert "Hours: 9 AM" in minimal_prompt

    def test_ground_truth_inside_ground_truth_section(
        self, minimal_prompt: str
    ) -> None:
        gt_start = minimal_prompt.index("<ground_truth>")
        gt_end = minimal_prompt.index("</ground_truth>")
        gt_section = minimal_prompt[gt_start:gt_end]
        assert "What are the opening hours?" in gt_section

    def test_empty_test_cases_produces_valid_prompt(self) -> None:
        """Prompt should still be valid with no ground truth data."""
        prompt = build_prompt(
            test_cases=[],
            app_description="App",
            system_prompt="Sys",
            business_metrics="Metrics",
            functional_count=3,
            boundary_count=2,
            num_questions_per_case=2,
        )
        assert "<ground_truth>" in prompt
        assert "<instructions>" in prompt


# ---------------------------------------------------------------------------
# Application context embedded
# ---------------------------------------------------------------------------


class TestApplicationContext:
    """App description, system prompt, and business metrics must appear."""

    def test_app_description_present(self, minimal_prompt: str) -> None:
        assert "A restaurant assistant chatbot" in minimal_prompt

    def test_system_prompt_present(self, minimal_prompt: str) -> None:
        assert "You are a helpful restaurant assistant." in minimal_prompt

    def test_business_metrics_present(self, minimal_prompt: str) -> None:
        assert "Customer satisfaction, order accuracy" in minimal_prompt

    def test_description_inside_application_context(self, minimal_prompt: str) -> None:
        ctx_start = minimal_prompt.index("<application_context>")
        ctx_end = minimal_prompt.index("</application_context>")
        ctx_section = minimal_prompt[ctx_start:ctx_end]
        assert "A restaurant assistant chatbot" in ctx_section


# ---------------------------------------------------------------------------
# Few-shot examples (Req 12.3)
# ---------------------------------------------------------------------------


class TestFewShotExamples:
    """At least one functional and one boundary few-shot example must be present."""

    def test_functional_example_present(self, minimal_prompt: str) -> None:
        assert "<functional_example>" in minimal_prompt
        assert "</functional_example>" in minimal_prompt

    def test_boundary_example_present(self, minimal_prompt: str) -> None:
        assert "<boundary_example>" in minimal_prompt
        assert "</boundary_example>" in minimal_prompt

    def test_functional_example_has_category_label(self, minimal_prompt: str) -> None:
        """Req 9.5 — functional examples labelled with category 'functional'."""
        fe_start = minimal_prompt.index("<functional_example>")
        fe_end = minimal_prompt.index("</functional_example>")
        fe_section = minimal_prompt[fe_start:fe_end]
        assert "functional" in fe_section.lower()

    def test_boundary_example_has_category_label(self, minimal_prompt: str) -> None:
        """Req 10.3 — boundary examples labelled with category 'boundary'."""
        be_start = minimal_prompt.index("<boundary_example>")
        be_end = minimal_prompt.index("</boundary_example>")
        be_section = minimal_prompt[be_start:be_end]
        assert "boundary" in be_section.lower()


# ---------------------------------------------------------------------------
# YAML output schema specification (Req 12.4)
# ---------------------------------------------------------------------------


class TestOutputSchemaSpec:
    """The prompt must specify the exact YAML output schema."""

    def test_scenario_name_field_mentioned(self, minimal_prompt: str) -> None:
        assert "scenario_name" in minimal_prompt

    def test_category_field_mentioned(self, minimal_prompt: str) -> None:
        of_start = minimal_prompt.index("<output_format>")
        of_end = minimal_prompt.index("</output_format>")
        of_section = minimal_prompt[of_start:of_end]
        assert "category" in of_section

    def test_turns_field_mentioned(self, minimal_prompt: str) -> None:
        assert "turns" in minimal_prompt

    def test_yaml_only_instruction(self, minimal_prompt: str) -> None:
        """Req 12.4 — instruct model to output only valid YAML, no prose."""
        lower = minimal_prompt.lower()
        assert "yaml" in lower
        # Should instruct no surrounding prose
        assert "no" in lower and "prose" in lower or "only" in lower


# ---------------------------------------------------------------------------
# Language parameter
# ---------------------------------------------------------------------------


class TestLanguageParameter:
    """The language parameter should be reflected in the prompt."""

    def test_default_language_english(self, minimal_prompt: str) -> None:
        assert "English" in minimal_prompt

    def test_custom_language(self, sample_test_cases: list[TestCase]) -> None:
        prompt = build_prompt(
            test_cases=sample_test_cases,
            app_description="App",
            system_prompt="Sys",
            business_metrics="Metrics",
            functional_count=3,
            boundary_count=2,
            num_questions_per_case=2,
            language="Spanish",
        )
        assert "Spanish" in prompt
