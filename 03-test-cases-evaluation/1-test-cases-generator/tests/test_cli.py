"""Unit tests for test_generator.__main__ (CLI entry point).

Covers:
- Argument parsing for all supported flags
- Missing app_description exits with non-zero code
- Output to file vs stdout
- Functional-ratio validation

Requirements: 15.1–15.6
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from test_generator.__main__ import _build_overrides, _build_parser, main
from test_generator.generator import GenerationResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(**overrides) -> GenerationResult:
    defaults = dict(
        yaml_text="- scenario_name: test\n  category: functional\n  turns: []\n",
        is_valid_yaml=True,
        test_cases_generated=1,
        functional_count=1,
        boundary_count=0,
        model_used="test-model",
        diagnostics=None,
        warnings=[],
    )
    defaults.update(overrides)
    return GenerationResult(**defaults)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

class TestArgumentParsing:
    def test_all_flags_parsed(self):
        parser = _build_parser()
        args = parser.parse_args([
            "--s3-uri", "s3://bucket/prefix",
            "--config", "my_config.yaml",
            "--model", "claude-4-sonnet",
            "--num-cases", "10",
            "--num-questions", "3",
            "--functional-ratio", "80",
            "--output", "out.yaml",
            "--lenient",
            "--app-description", "My app",
        ])
        assert args.s3_uri == "s3://bucket/prefix"
        assert args.config == "my_config.yaml"
        assert args.model == "claude-4-sonnet"
        assert args.num_cases == 10
        assert args.num_questions == 3
        assert args.functional_ratio == 80
        assert args.output == "out.yaml"
        assert args.lenient is True
        assert args.app_description == "My app"

    def test_strict_flag(self):
        parser = _build_parser()
        args = parser.parse_args(["--strict", "--app-description", "x"])
        assert args.strict is True
        assert args.lenient is None

    def test_defaults(self):
        parser = _build_parser()
        args = parser.parse_args(["--app-description", "x"])
        assert args.s3_uri is None
        assert args.config is None
        assert args.model is None
        assert args.num_cases is None
        assert args.output is None


# ---------------------------------------------------------------------------
# Override building
# ---------------------------------------------------------------------------

class TestBuildOverrides:
    def test_maps_cli_args_to_config_keys(self):
        parser = _build_parser()
        args = parser.parse_args([
            "--s3-uri", "s3://b/p",
            "--model", "m",
            "--num-cases", "5",
            "--num-questions", "2",
            "--functional-ratio", "60",
            "--lenient",
            "--app-description", "x",
        ])
        overrides = _build_overrides(args)
        assert overrides["s3_uri"] == "s3://b/p"
        assert overrides["model_name"] == "m"
        assert overrides["num_cases"] == 5
        assert overrides["num_questions_per_case"] == 2
        assert overrides["functional_ratio"] == 60
        assert overrides["lenient"] is True

    def test_strict_sets_lenient_false(self):
        parser = _build_parser()
        args = parser.parse_args(["--strict", "--app-description", "x"])
        overrides = _build_overrides(args)
        assert overrides["lenient"] is False

    def test_no_flags_produces_empty_overrides(self):
        parser = _build_parser()
        args = parser.parse_args(["--app-description", "x"])
        overrides = _build_overrides(args)
        assert overrides == {}


# ---------------------------------------------------------------------------
# main() integration
# ---------------------------------------------------------------------------

class TestMain:
    @patch("test_generator.__main__.TestGeneratorOrchestrator")
    @patch("test_generator.__main__.load_config")
    def test_missing_app_description_returns_1(self, mock_config, mock_orch):
        """Req 15.5: missing app_description → non-zero exit."""
        from test_generator.config import Config
        mock_config.return_value = Config()
        code = main([])
        assert code == 1

    @patch("test_generator.__main__.TestGeneratorOrchestrator")
    @patch("test_generator.__main__.load_config")
    def test_success_returns_0(self, mock_config, mock_orch, capsys):
        from test_generator.config import Config
        mock_config.return_value = Config()
        mock_instance = MagicMock()
        mock_instance.generate.return_value = _make_result()
        mock_orch.return_value = mock_instance

        code = main(["--app-description", "My app"])
        assert code == 0
        captured = capsys.readouterr()
        assert "scenario_name" in captured.out

    @patch("test_generator.__main__.TestGeneratorOrchestrator")
    @patch("test_generator.__main__.load_config")
    def test_output_to_file(self, mock_config, mock_orch, tmp_path):
        from test_generator.config import Config
        mock_config.return_value = Config()
        mock_instance = MagicMock()
        mock_instance.generate.return_value = _make_result()
        mock_orch.return_value = mock_instance

        out_file = tmp_path / "result.yaml"
        code = main(["--app-description", "My app", "--output", str(out_file)])
        assert code == 0
        assert out_file.exists()
        assert "scenario_name" in out_file.read_text()

    @patch("test_generator.__main__.TestGeneratorOrchestrator")
    @patch("test_generator.__main__.load_config")
    def test_generation_exception_returns_1(self, mock_config, mock_orch):
        from test_generator.config import Config
        mock_config.return_value = Config()
        mock_instance = MagicMock()
        mock_instance.generate.side_effect = RuntimeError("boom")
        mock_orch.return_value = mock_instance

        code = main(["--app-description", "My app"])
        assert code == 1

    @patch("test_generator.__main__.TestGeneratorOrchestrator")
    @patch("test_generator.__main__.load_config")
    def test_warnings_printed_to_stderr(self, mock_config, mock_orch, capsys):
        from test_generator.config import Config
        mock_config.return_value = Config()
        mock_instance = MagicMock()
        mock_instance.generate.return_value = _make_result(warnings=["watch out"])
        mock_orch.return_value = mock_instance

        code = main(["--app-description", "My app"])
        assert code == 0
        captured = capsys.readouterr()
        assert "watch out" in captured.err


# ---------------------------------------------------------------------------
# YAML reordering (Req 17.2, 17.3)
# ---------------------------------------------------------------------------

class TestReorderYamlOutput:
    def test_functional_before_boundary(self):
        from test_generator.__main__ import _reorder_yaml_output

        raw = (
            "- scenario_name: edge\n  category: boundary\n  turns: []\n"
            "---\n"
            "- scenario_name: happy\n  category: functional\n  turns: []\n"
        )
        result = _reorder_yaml_output(raw)
        func_pos = result.index("functional")
        bound_pos = result.index("boundary")
        assert func_pos < bound_pos

    def test_all_functional_unchanged(self):
        from test_generator.__main__ import _reorder_yaml_output

        raw = "scenario_name: a\ncategory: functional\nturns: []\n"
        result = _reorder_yaml_output(raw)
        assert "functional" in result
        assert "boundary" not in result

    def test_invalid_yaml_returns_original(self):
        from test_generator.__main__ import _reorder_yaml_output

        raw = "not: valid: yaml: {{{"
        result = _reorder_yaml_output(raw)
        assert result == raw

    def test_separator_between_documents(self):
        from test_generator.__main__ import _reorder_yaml_output

        raw = (
            "scenario_name: a\ncategory: functional\nturns: []\n"
            "---\n"
            "scenario_name: b\ncategory: boundary\nturns: []\n"
        )
        result = _reorder_yaml_output(raw)
        assert "---" in result


# ---------------------------------------------------------------------------
# Functional ratio validation
# ---------------------------------------------------------------------------

class TestFunctionalRatioValidation:
    def test_ratio_out_of_range_returns_1(self, capsys):
        code = main(["--app-description", "x", "--functional-ratio", "150"])
        assert code == 1
        captured = capsys.readouterr()
        assert "functional-ratio" in captured.err

    def test_negative_ratio_returns_1(self, capsys):
        code = main(["--app-description", "x", "--functional-ratio", "-5"])
        assert code == 1
        captured = capsys.readouterr()
        assert "functional-ratio" in captured.err


# ---------------------------------------------------------------------------
# Reordered output integration (Req 17.2, 17.3)
# ---------------------------------------------------------------------------

class TestMainReorderedOutput:
    @patch("test_generator.__main__.TestGeneratorOrchestrator")
    @patch("test_generator.__main__.load_config")
    def test_output_groups_functional_before_boundary(self, mock_config, mock_orch, capsys):
        from test_generator.config import Config

        mock_config.return_value = Config()
        # Simulate model returning boundary before functional
        yaml_text = (
            "scenario_name: edge\ncategory: boundary\nturns: []\n"
            "---\n"
            "scenario_name: happy\ncategory: functional\nturns: []\n"
        )
        mock_instance = MagicMock()
        mock_instance.generate.return_value = _make_result(
            yaml_text=yaml_text, is_valid_yaml=True, test_cases_generated=2
        )
        mock_orch.return_value = mock_instance

        code = main(["--app-description", "My app"])
        assert code == 0
        captured = capsys.readouterr()
        func_pos = captured.out.index("functional")
        bound_pos = captured.out.index("boundary")
        assert func_pos < bound_pos
