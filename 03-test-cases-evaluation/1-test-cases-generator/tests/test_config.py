"""Unit tests for test_generator.config.

Covers:
- Loading from a valid YAML file
- Fallback to defaults when no file exists
- Runtime overrides take precedence over file values
- Warning on unrecognized keys

Requirements: 13.1–13.5
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
import yaml

from test_generator.config import Config, load_config
from test_generator.models import FieldMapping


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_yaml(path: Path, data: dict) -> None:
    """Write a dict as YAML to *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh)


# ---------------------------------------------------------------------------
# Loading from a valid YAML file (Req 13.1, 13.2)
# ---------------------------------------------------------------------------


class TestLoadFromValidYAML:
    """load_config should read recognised keys from a YAML file."""

    def test_scalar_keys_loaded(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.yaml"
        _write_yaml(cfg_file, {
            "s3_uri": "s3://my-bucket/prefix/",
            "model_name": "claude-4-haiku",
            "aws_region": "eu-west-1",
            "functional_ratio": 50,
            "num_cases": 10,
            "num_questions_per_case": 5,
            "output_format": "json",
            "log_level": "DEBUG",
        })

        cfg = load_config(config_path=str(cfg_file))

        assert cfg.s3_uri == "s3://my-bucket/prefix/"
        assert cfg.model_name == "claude-4-haiku"
        assert cfg.aws_region == "eu-west-1"
        assert cfg.functional_ratio == 50
        assert cfg.num_cases == 10
        assert cfg.num_questions_per_case == 5
        assert cfg.output_format == "json"
        assert cfg.log_level == "DEBUG"

    def test_languages_list_loaded(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.yaml"
        _write_yaml(cfg_file, {"languages": ["English", "French", "German"]})

        cfg = load_config(config_path=str(cfg_file))

        assert cfg.languages == ["English", "French", "German"]

    def test_field_mapping_loaded(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.yaml"
        _write_yaml(cfg_file, {
            "field_mapping": {
                "prompt_aliases": ["user_query"],
                "expected_aliases": ["bot_reply"],
            },
        })

        cfg = load_config(config_path=str(cfg_file))

        assert cfg.field_mapping.prompt_aliases == ["user_query"]
        assert cfg.field_mapping.expected_aliases == ["bot_reply"]
        # Unspecified alias lists keep defaults
        assert cfg.field_mapping.id_aliases == FieldMapping().id_aliases

    def test_boolean_keys_loaded(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.yaml"
        _write_yaml(cfg_file, {"recursive": False, "lenient": False})

        cfg = load_config(config_path=str(cfg_file))

        assert cfg.recursive is False
        assert cfg.lenient is False

    def test_model_list_path_and_prompt_template_path(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.yaml"
        _write_yaml(cfg_file, {
            "model_list_path": "custom_models.json",
            "prompt_template_path": "prompts/my_template.txt",
        })

        cfg = load_config(config_path=str(cfg_file))

        assert cfg.model_list_path == "custom_models.json"
        assert cfg.prompt_template_path == "prompts/my_template.txt"


# ---------------------------------------------------------------------------
# Fallback to defaults when no file exists (Req 13.3)
# ---------------------------------------------------------------------------


class TestFallbackToDefaults:
    """load_config should return built-in defaults when no config file is found."""

    def test_nonexistent_path_returns_defaults(self, tmp_path: Path) -> None:
        cfg = load_config(config_path=str(tmp_path / "does_not_exist.yaml"))

        expected = Config()
        assert cfg.s3_uri == expected.s3_uri
        assert cfg.model_name == expected.model_name
        assert cfg.aws_region == expected.aws_region
        assert cfg.functional_ratio == expected.functional_ratio
        assert cfg.num_cases == expected.num_cases
        assert cfg.num_questions_per_case == expected.num_questions_per_case
        assert cfg.output_format == expected.output_format
        assert cfg.languages == expected.languages
        assert cfg.recursive == expected.recursive
        assert cfg.lenient == expected.lenient
        assert cfg.log_level == expected.log_level

    def test_none_path_with_no_cwd_file_returns_defaults(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        cfg = load_config()

        assert cfg.model_name == "claude-4-sonnet"
        assert cfg.functional_ratio == 70

    def test_empty_yaml_file_returns_defaults(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("", encoding="utf-8")

        cfg = load_config(config_path=str(cfg_file))

        assert cfg.model_name == "claude-4-sonnet"
        assert cfg.num_cases == 3


# ---------------------------------------------------------------------------
# Runtime overrides take precedence (Req 13.4)
# ---------------------------------------------------------------------------


class TestRuntimeOverrides:
    """Runtime overrides must win over file values and defaults."""

    def test_override_beats_file_value(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.yaml"
        _write_yaml(cfg_file, {"model_name": "from-file", "num_cases": 5})

        cfg = load_config(
            config_path=str(cfg_file),
            overrides={"model_name": "from-override", "num_cases": 20},
        )

        assert cfg.model_name == "from-override"
        assert cfg.num_cases == 20

    def test_override_beats_default(self) -> None:
        cfg = load_config(
            config_path="/nonexistent.yaml",
            overrides={"aws_region": "ap-southeast-1", "functional_ratio": 100},
        )

        assert cfg.aws_region == "ap-southeast-1"
        assert cfg.functional_ratio == 100

    def test_none_override_values_are_ignored(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.yaml"
        _write_yaml(cfg_file, {"model_name": "from-file"})

        cfg = load_config(
            config_path=str(cfg_file),
            overrides={"model_name": None},
        )

        # None override should not clobber the file value
        assert cfg.model_name == "from-file"

    def test_override_field_mapping(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.yaml"
        _write_yaml(cfg_file, {
            "field_mapping": {"prompt_aliases": ["from_file"]},
        })

        cfg = load_config(
            config_path=str(cfg_file),
            overrides={"field_mapping": {"prompt_aliases": ["from_override"]}},
        )

        assert cfg.field_mapping.prompt_aliases == ["from_override"]


# ---------------------------------------------------------------------------
# Warning on unrecognized keys (Req 13.5)
# ---------------------------------------------------------------------------


class TestUnrecognizedKeys:
    """Unrecognized config keys should be logged as warnings and ignored."""

    def test_unrecognized_key_logged_as_warning(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        cfg_file = tmp_path / "config.yaml"
        _write_yaml(cfg_file, {
            "model_name": "valid-model",
            "bogus_key": "should warn",
            "another_unknown": 42,
        })

        with caplog.at_level(logging.WARNING, logger="test_generator.config"):
            cfg = load_config(config_path=str(cfg_file))

        # Valid key still loaded
        assert cfg.model_name == "valid-model"

        # Warnings emitted for each unrecognized key
        warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("bogus_key" in m for m in warning_messages)
        assert any("another_unknown" in m for m in warning_messages)

    def test_unrecognized_keys_do_not_affect_config(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.yaml"
        _write_yaml(cfg_file, {
            "num_cases": 7,
            "unknown_setting": True,
        })

        cfg = load_config(config_path=str(cfg_file))

        assert cfg.num_cases == 7
        # No attribute for the unknown key
        assert not hasattr(cfg, "unknown_setting")


# ---------------------------------------------------------------------------
# Edge cases: malformed YAML / non-mapping content
# ---------------------------------------------------------------------------


class TestConfigEdgeCases:
    """Error handling for broken or unexpected YAML content."""

    def test_invalid_yaml_logs_error_and_returns_defaults(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("{{invalid yaml::", encoding="utf-8")

        with caplog.at_level(logging.ERROR, logger="test_generator.config"):
            cfg = load_config(config_path=str(cfg_file))

        assert cfg.model_name == "claude-4-sonnet"  # defaults
        error_messages = [r.message for r in caplog.records if r.levelno == logging.ERROR]
        assert any("parse" in m.lower() or "failed" in m.lower() for m in error_messages)

    def test_non_mapping_yaml_logs_error_and_returns_defaults(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("- just\n- a\n- list\n", encoding="utf-8")

        with caplog.at_level(logging.ERROR, logger="test_generator.config"):
            cfg = load_config(config_path=str(cfg_file))

        assert cfg.model_name == "claude-4-sonnet"
        error_messages = [r.message for r in caplog.records if r.levelno == logging.ERROR]
        assert any("mapping" in m.lower() for m in error_messages)
