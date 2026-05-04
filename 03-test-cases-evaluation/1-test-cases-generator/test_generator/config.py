"""Configuration management for the S3 Ground Truth Test Generator.

Provides the ``Config`` dataclass and ``load_config`` helper that layers
YAML file values, built-in defaults, and runtime overrides.

Requirements: 13.1–13.5, 14.1–14.3, 14.5, 19.4
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from test_generator.models import FieldMapping

logger = logging.getLogger(__name__)

# Keys recognised in the YAML config file (must stay in sync with Config fields).
_KNOWN_KEYS = frozenset({
    "s3_uri",
    "field_mapping",
    "recursive",
    "lenient",
    "model_name",
    "aws_region",
    "functional_ratio",
    "num_cases",
    "num_questions_per_case",
    "output_format",
    "languages",
    "model_list_path",
    "prompt_template_path",
    "log_level",
})


# ---------------------------------------------------------------------------
# Config dataclass
# ---------------------------------------------------------------------------

@dataclass
class Config:
    """All tunable parameters for the test generator pipeline.

    Attributes:
        s3_uri:                S3 URI for ground truth data (``s3://bucket/prefix``).
        field_mapping:         Alias mapping from source keys to canonical TestCase fields.
        recursive:             Whether to scan S3 sub-prefixes recursively.
        lenient:               If True, skip malformed records; if False, fail fast.
        model_name:            Bedrock model identifier.
        aws_region:            AWS region for Bedrock and S3 calls.
        functional_ratio:      Percentage (0–100) of functional vs boundary test cases.
        num_cases:             Total number of test cases to generate.
        num_questions_per_case: Number of turns per test case.
        output_format:         Output serialisation format (default ``"yaml"``).
        languages:             Supported language list for the notebook dropdown.
        model_list_path:       Path to the model registry JSON file.
        prompt_template_path:  Optional path to an external prompt template file.
        log_level:             Python logging level name (default ``"INFO"``).
    """

    s3_uri: str | None = None
    field_mapping: FieldMapping = field(default_factory=FieldMapping)
    recursive: bool = True
    lenient: bool = True
    model_name: str = "claude-4-sonnet"
    aws_region: str = "us-east-1"
    functional_ratio: int = 70
    num_cases: int = 3
    num_questions_per_case: int = 2
    output_format: str = "yaml"
    languages: list[str] = field(default_factory=lambda: ["English", "Spanish"])
    model_list_path: str = "model_list.json"
    prompt_template_path: str | None = None
    log_level: str = "INFO"


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def _build_field_mapping(raw: Any) -> FieldMapping:
    """Construct a ``FieldMapping`` from a raw dict (or return default)."""
    if not isinstance(raw, dict):
        return FieldMapping()
    defaults = FieldMapping()
    return FieldMapping(
        prompt_aliases=raw.get("prompt_aliases", defaults.prompt_aliases),
        expected_aliases=raw.get("expected_aliases", defaults.expected_aliases),
        id_aliases=raw.get("id_aliases", defaults.id_aliases),
        contexts_aliases=raw.get("contexts_aliases", defaults.contexts_aliases),
    )


def load_config(
    config_path: str | None = None,
    overrides: dict[str, Any] | None = None,
) -> Config:
    """Load configuration with layering: defaults → YAML file → runtime overrides.

    Parameters:
        config_path: Path to a YAML config file.  Defaults to ``config.yaml``
                     in the current working directory.  If the file does not
                     exist the built-in defaults are used silently.
        overrides:   Runtime values (CLI flags, widget values) that take
                     precedence over both file and default values.

    Returns:
        A fully-resolved ``Config`` instance.
    """
    file_values: dict[str, Any] = {}
    path = Path(config_path) if config_path else Path("config.yaml")

    if path.is_file():
        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = yaml.safe_load(fh)
            if isinstance(raw, dict):
                # Warn on unrecognised keys (Req 13.5)
                for key in raw:
                    if key not in _KNOWN_KEYS:
                        logger.warning("Ignoring unrecognized config key: %s", key)
                file_values = {k: v for k, v in raw.items() if k in _KNOWN_KEYS}
            elif raw is not None:
                logger.error(
                    "Config file %s does not contain a YAML mapping; using defaults",
                    path,
                )
        except yaml.YAMLError as exc:
            logger.error("Failed to parse config file %s: %s", path, exc)
        except OSError as exc:
            logger.error("Failed to read config file %s: %s", path, exc)

    # Merge: defaults ← file ← overrides
    merged = {**file_values}
    if overrides:
        for key, value in overrides.items():
            if value is not None:
                merged[key] = value

    # Build FieldMapping from nested dict if present
    fm_raw = merged.pop("field_mapping", None)
    fm = _build_field_mapping(fm_raw) if fm_raw is not None else FieldMapping()

    return Config(
        s3_uri=merged.get("s3_uri"),
        field_mapping=fm,
        recursive=merged.get("recursive", True),
        lenient=merged.get("lenient", True),
        model_name=merged.get("model_name", "claude-4-sonnet"),
        aws_region=merged.get("aws_region", "us-east-1"),
        functional_ratio=merged.get("functional_ratio", 70),
        num_cases=merged.get("num_cases", 3),
        num_questions_per_case=merged.get("num_questions_per_case", 2),
        output_format=merged.get("output_format", "yaml"),
        languages=merged.get("languages", ["English", "Spanish"]),
        model_list_path=merged.get("model_list_path", "model_list.json"),
        prompt_template_path=merged.get("prompt_template_path"),
        log_level=merged.get("log_level", "INFO"),
    )
