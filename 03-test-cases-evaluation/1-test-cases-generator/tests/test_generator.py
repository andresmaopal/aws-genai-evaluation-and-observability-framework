"""Unit tests for test_generator.generator.

Covers:
- Functional/boundary count calculation for various ratios (0, 50, 70, 100)
- Model registry deduplication and validation logic
- YAML validation and retry behavior (mock Bedrock client)
- GenerationResult fields are populated correctly

Requirements: 11.2–11.4, 17.4, 18.1–18.3
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from test_generator.config import Config
from test_generator.generator import (
    GenerationResult,
    TestGeneratorOrchestrator,
    _load_model_registry,
    _validate_yaml,
)
from test_generator.models import Diagnostics, TestCase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_model_registry(path: Path, data: dict[str, Any]) -> str:
    """Write a model registry JSON file and return its path as a string."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    return str(path)


def _minimal_model_entry(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid model entry with optional overrides."""
    base = {
        "model_id": "test.model-v1:0",
        "region_name": "us-east-1",
        "temperature": 0.2,
        "inference_type": "ON_DEMAND",
    }
    base.update(overrides)
    return base


def _make_converse_response(text: str) -> dict[str, Any]:
    """Build a mock Bedrock Converse API response containing *text*."""
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"text": text}],
            }
        }
    }


VALID_YAML_OUTPUT = """\
- scenario_name: "Test scenario"
  category: "functional"
  turns:
    - question: "Hello"
      expected_result: "Hi there"
"""

INVALID_YAML_OUTPUT = "{{not: valid: yaml::"


# ---------------------------------------------------------------------------
# Functional / boundary count calculation (Req 11.2–11.4, 11.6)
# ---------------------------------------------------------------------------


class TestCountCalculation:
    """Verify functional_count and boundary_count for various ratios."""

    @pytest.fixture()
    def orchestrator(self, tmp_path: Path) -> TestGeneratorOrchestrator:
        reg_path = _write_model_registry(
            tmp_path / "models.json",
            {"test-model": _minimal_model_entry()},
        )
        mock_client = MagicMock()
        mock_client.converse.return_value = _make_converse_response(VALID_YAML_OUTPUT)
        cfg = Config(model_name="test-model", model_list_path=reg_path)
        return TestGeneratorOrchestrator(config=cfg, bedrock_client=mock_client)

    def _generate(self, orch: TestGeneratorOrchestrator, ratio: int, total: int) -> GenerationResult:
        orch.config.functional_ratio = ratio
        orch.config.num_cases = total
        return orch.generate(app_description="App", ground_truth=[])

    def test_ratio_70_of_10(self, orchestrator: TestGeneratorOrchestrator) -> None:
        result = self._generate(orchestrator, ratio=70, total=10)
        assert result.functional_count == 7
        assert result.boundary_count == 3

    def test_ratio_50_of_10(self, orchestrator: TestGeneratorOrchestrator) -> None:
        result = self._generate(orchestrator, ratio=50, total=10)
        assert result.functional_count == 5
        assert result.boundary_count == 5

    def test_ratio_100_only_functional(self, orchestrator: TestGeneratorOrchestrator) -> None:
        result = self._generate(orchestrator, ratio=100, total=10)
        assert result.functional_count == 10
        assert result.boundary_count == 0

    def test_ratio_0_only_boundary(self, orchestrator: TestGeneratorOrchestrator) -> None:
        result = self._generate(orchestrator, ratio=0, total=10)
        assert result.functional_count == 0
        assert result.boundary_count == 10

    def test_rounding_ratio_33_of_10(self, orchestrator: TestGeneratorOrchestrator) -> None:
        result = self._generate(orchestrator, ratio=33, total=10)
        # round(10 * 33 / 100) = round(3.3) = 3
        assert result.functional_count == 3
        assert result.boundary_count == 7

    def test_counts_sum_to_total(self, orchestrator: TestGeneratorOrchestrator) -> None:
        for ratio in (0, 25, 33, 50, 67, 70, 100):
            result = self._generate(orchestrator, ratio=ratio, total=10)
            assert result.functional_count + result.boundary_count == 10


# ---------------------------------------------------------------------------
# Model registry loading, validation, deduplication (Req 18.1–18.3)
# ---------------------------------------------------------------------------


class TestModelRegistry:
    """Model registry loading, validation, and deduplication."""

    def test_valid_entries_loaded(self, tmp_path: Path) -> None:
        path = _write_model_registry(
            tmp_path / "models.json",
            {"m1": _minimal_model_entry(), "m2": _minimal_model_entry(model_id="other.model-v1:0")},
        )
        registry = _load_model_registry(path)
        assert "m1" in registry
        assert "m2" in registry

    def test_missing_required_field_excluded(self, tmp_path: Path) -> None:
        path = _write_model_registry(
            tmp_path / "models.json",
            {
                "good": _minimal_model_entry(),
                "bad": {"model_id": "x", "region_name": "us-east-1"},  # missing temperature, inference_type
            },
        )
        registry = _load_model_registry(path)
        assert "good" in registry
        assert "bad" not in registry

    def test_default_max_tokens_applied(self, tmp_path: Path) -> None:
        entry = _minimal_model_entry()
        assert "max_tokens" not in entry
        path = _write_model_registry(tmp_path / "models.json", {"m": entry})
        registry = _load_model_registry(path)
        assert registry["m"]["max_tokens"] == 4096

    def test_explicit_max_tokens_preserved(self, tmp_path: Path) -> None:
        path = _write_model_registry(
            tmp_path / "models.json",
            {"m": _minimal_model_entry(max_tokens=8192)},
        )
        registry = _load_model_registry(path)
        assert registry["m"]["max_tokens"] == 8192

    def test_deduplication_keeps_shorter_key(self, tmp_path: Path) -> None:
        """When two entries share (model_id, region_name), keep the shorter key."""
        shared = {"model_id": "same.model:0", "region_name": "us-east-1"}
        path = _write_model_registry(
            tmp_path / "models.json",
            {
                "short": _minimal_model_entry(**shared),
                "very-long-name": _minimal_model_entry(**shared),
            },
        )
        registry = _load_model_registry(path)
        assert "short" in registry
        assert "very-long-name" not in registry

    def test_different_regions_not_deduplicated(self, tmp_path: Path) -> None:
        path = _write_model_registry(
            tmp_path / "models.json",
            {
                "east": _minimal_model_entry(model_id="m:0", region_name="us-east-1"),
                "west": _minimal_model_entry(model_id="m:0", region_name="us-west-2"),
            },
        )
        registry = _load_model_registry(path)
        assert "east" in registry
        assert "west" in registry

    def test_nonexistent_file_returns_empty(self, tmp_path: Path) -> None:
        registry = _load_model_registry(str(tmp_path / "nope.json"))
        assert registry == {}

    def test_invalid_json_returns_empty(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{{not json", encoding="utf-8")
        registry = _load_model_registry(str(bad_file))
        assert registry == {}

    def test_non_dict_entry_skipped(self, tmp_path: Path) -> None:
        path = _write_model_registry(
            tmp_path / "models.json",
            {"good": _minimal_model_entry(), "bad": "not a dict"},
        )
        registry = _load_model_registry(path)
        assert "good" in registry
        assert "bad" not in registry


# ---------------------------------------------------------------------------
# YAML validation helper
# ---------------------------------------------------------------------------


class TestYAMLValidation:
    """_validate_yaml should detect valid/invalid YAML and count documents."""

    def test_valid_single_document(self) -> None:
        is_valid, count = _validate_yaml("key: value\n")
        assert is_valid is True
        assert count == 1

    def test_valid_multi_document(self) -> None:
        text = "a: 1\n---\nb: 2\n---\nc: 3\n"
        is_valid, count = _validate_yaml(text)
        assert is_valid is True
        assert count == 3

    def test_invalid_yaml(self) -> None:
        is_valid, count = _validate_yaml("{{bad: yaml::")
        assert is_valid is False
        assert count == 0

    def test_empty_string(self) -> None:
        is_valid, count = _validate_yaml("")
        assert is_valid is True
        assert count == 0


# ---------------------------------------------------------------------------
# YAML validation and retry behavior (Req 17.4)
# ---------------------------------------------------------------------------


class TestYAMLRetryBehavior:
    """Model output YAML validation with retry-once logic."""

    def _make_orchestrator(
        self, tmp_path: Path, mock_client: MagicMock
    ) -> TestGeneratorOrchestrator:
        reg_path = _write_model_registry(
            tmp_path / "models.json",
            {"test-model": _minimal_model_entry()},
        )
        cfg = Config(model_name="test-model", model_list_path=reg_path)
        return TestGeneratorOrchestrator(config=cfg, bedrock_client=mock_client)

    def test_valid_yaml_on_first_try(self, tmp_path: Path) -> None:
        mock_client = MagicMock()
        mock_client.converse.return_value = _make_converse_response(VALID_YAML_OUTPUT)
        orch = self._make_orchestrator(tmp_path, mock_client)

        result = orch.generate(app_description="App", ground_truth=[])

        assert result.is_valid_yaml is True
        assert result.test_cases_generated >= 1
        assert mock_client.converse.call_count == 1

    def test_invalid_yaml_retries_once_then_succeeds(self, tmp_path: Path) -> None:
        mock_client = MagicMock()
        mock_client.converse.side_effect = [
            _make_converse_response(INVALID_YAML_OUTPUT),
            _make_converse_response(VALID_YAML_OUTPUT),
        ]
        orch = self._make_orchestrator(tmp_path, mock_client)

        result = orch.generate(app_description="App", ground_truth=[])

        assert result.is_valid_yaml is True
        assert mock_client.converse.call_count == 2

    def test_invalid_yaml_both_attempts_returns_raw(self, tmp_path: Path) -> None:
        mock_client = MagicMock()
        mock_client.converse.side_effect = [
            _make_converse_response(INVALID_YAML_OUTPUT),
            _make_converse_response(INVALID_YAML_OUTPUT),
        ]
        orch = self._make_orchestrator(tmp_path, mock_client)

        result = orch.generate(app_description="App", ground_truth=[])

        assert result.is_valid_yaml is False
        assert result.yaml_text == INVALID_YAML_OUTPUT
        assert any("not valid YAML" in w for w in result.warnings)

    def test_invocation_failure_returns_error_result(self, tmp_path: Path) -> None:
        mock_client = MagicMock()
        mock_client.converse.side_effect = RuntimeError("Bedrock down")
        orch = self._make_orchestrator(tmp_path, mock_client)

        result = orch.generate(app_description="App", ground_truth=[])

        assert result.is_valid_yaml is False
        assert result.yaml_text == ""
        assert result.test_cases_generated == 0
        assert any("invocation failed" in w.lower() for w in result.warnings)

    def test_retry_invocation_failure_returns_raw_with_warning(self, tmp_path: Path) -> None:
        mock_client = MagicMock()
        mock_client.converse.side_effect = [
            _make_converse_response(INVALID_YAML_OUTPUT),
            RuntimeError("Retry failed"),
        ]
        orch = self._make_orchestrator(tmp_path, mock_client)

        result = orch.generate(app_description="App", ground_truth=[])

        assert result.is_valid_yaml is False
        assert any("retry" in w.lower() for w in result.warnings)


# ---------------------------------------------------------------------------
# GenerationResult fields populated correctly
# ---------------------------------------------------------------------------


class TestGenerationResultFields:
    """Verify all GenerationResult fields are set correctly."""

    def test_model_used_field(self, tmp_path: Path) -> None:
        mock_client = MagicMock()
        mock_client.converse.return_value = _make_converse_response(VALID_YAML_OUTPUT)
        reg_path = _write_model_registry(
            tmp_path / "models.json",
            {"my-model": _minimal_model_entry()},
        )
        cfg = Config(model_name="my-model", model_list_path=reg_path)
        orch = TestGeneratorOrchestrator(config=cfg, bedrock_client=mock_client)

        result = orch.generate(app_description="App", ground_truth=[])

        assert result.model_used == "my-model"

    def test_diagnostics_none_when_no_s3(self, tmp_path: Path) -> None:
        mock_client = MagicMock()
        mock_client.converse.return_value = _make_converse_response(VALID_YAML_OUTPUT)
        reg_path = _write_model_registry(
            tmp_path / "models.json",
            {"m": _minimal_model_entry()},
        )
        cfg = Config(model_name="m", model_list_path=reg_path)
        orch = TestGeneratorOrchestrator(config=cfg, bedrock_client=mock_client)

        result = orch.generate(app_description="App", ground_truth=[])

        assert result.diagnostics is None

    def test_ground_truth_passed_directly(self, tmp_path: Path) -> None:
        mock_client = MagicMock()
        mock_client.converse.return_value = _make_converse_response(VALID_YAML_OUTPUT)
        reg_path = _write_model_registry(
            tmp_path / "models.json",
            {"m": _minimal_model_entry()},
        )
        cfg = Config(model_name="m", model_list_path=reg_path)
        orch = TestGeneratorOrchestrator(config=cfg, bedrock_client=mock_client)

        gt = [TestCase(prompt="Q?", expected="A.")]
        result = orch.generate(app_description="App", ground_truth=gt)

        # The prompt should contain the ground truth data
        call_args = mock_client.converse.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
        prompt_text = messages[0]["content"][0]["text"]
        assert "Q?" in prompt_text

    def test_unknown_model_raises_value_error(self, tmp_path: Path) -> None:
        mock_client = MagicMock()
        reg_path = _write_model_registry(
            tmp_path / "models.json",
            {"m": _minimal_model_entry()},
        )
        cfg = Config(model_name="nonexistent", model_list_path=reg_path)
        orch = TestGeneratorOrchestrator(config=cfg, bedrock_client=mock_client)

        with pytest.raises(ValueError, match="not found in registry"):
            orch.generate(app_description="App", ground_truth=[])

    def test_warnings_list_empty_on_success(self, tmp_path: Path) -> None:
        mock_client = MagicMock()
        mock_client.converse.return_value = _make_converse_response(VALID_YAML_OUTPUT)
        reg_path = _write_model_registry(
            tmp_path / "models.json",
            {"m": _minimal_model_entry()},
        )
        cfg = Config(model_name="m", model_list_path=reg_path)
        orch = TestGeneratorOrchestrator(config=cfg, bedrock_client=mock_client)

        result = orch.generate(app_description="App", ground_truth=[])

        assert result.warnings == []
