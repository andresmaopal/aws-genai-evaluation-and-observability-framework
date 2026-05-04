"""CLI entry point for the S3 Ground Truth Test Generator.

Usage::

    python -m test_generator --app-description "My app" --s3-uri s3://bucket/prefix

Requirements: 15.1–15.6, 11.5, 17.2, 17.3
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

import yaml

from test_generator.config import load_config
from test_generator.generator import TestGeneratorOrchestrator

logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="test_generator",
        description="Generate functional and boundary test cases from S3 ground truth data.",
    )
    parser.add_argument("--s3-uri", help="S3 URI for ground truth data (s3://bucket/prefix)")
    parser.add_argument("--config", help="Path to YAML config file (default: config.yaml)")
    parser.add_argument("--model", help="Bedrock model name to use for generation")
    parser.add_argument("--num-cases", type=int, help="Total number of test cases to generate")
    parser.add_argument("--num-questions", type=int, help="Number of turns per test case")
    parser.add_argument(
        "--functional-ratio",
        type=int,
        metavar="0-100",
        help="Percentage of functional vs boundary test cases (0–100)",
    )
    parser.add_argument("--output", help="Output file path (default: stdout)")

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--lenient", action="store_true", default=None, help="Skip malformed records (default)")
    mode_group.add_argument("--strict", action="store_true", default=None, help="Fail on first malformed record")

    parser.add_argument("--app-description", help="Application description (required)")
    parser.add_argument("--system-prompt", default="", help="Agent system prompt")
    parser.add_argument("--business-metrics", default="", help="Business metrics text")
    parser.add_argument("--language", default=None, help="Target language for generated tests")
    return parser


def _build_overrides(args: argparse.Namespace) -> dict[str, object]:
    """Map parsed CLI args to config override keys."""
    overrides: dict[str, object] = {}
    if args.s3_uri is not None:
        overrides["s3_uri"] = args.s3_uri
    if args.model is not None:
        overrides["model_name"] = args.model
    if args.num_cases is not None:
        overrides["num_cases"] = args.num_cases
    if args.num_questions is not None:
        overrides["num_questions_per_case"] = args.num_questions
    if args.functional_ratio is not None:
        overrides["functional_ratio"] = args.functional_ratio
    if args.lenient:
        overrides["lenient"] = True
    elif args.strict:
        overrides["lenient"] = False
    return overrides


def _reorder_yaml_output(raw_text: str) -> str:
    """Reorder YAML documents so functional cases come before boundary cases.

    Parses the raw YAML text into documents, groups them by category
    (functional first, then boundary, then any uncategorized), and
    re-serializes with ``---`` separators between documents.

    If parsing fails, returns the original text unchanged.

    Requirements: 17.2, 17.3
    """
    try:
        docs = list(yaml.safe_load_all(raw_text))
    except yaml.YAMLError:
        return raw_text

    # Flatten: each doc may be a list of test cases or a single test case dict.
    all_cases: list[dict[str, Any]] = []
    for doc in docs:
        if doc is None:
            continue
        if isinstance(doc, list):
            all_cases.extend(d for d in doc if isinstance(d, dict))
        elif isinstance(doc, dict):
            all_cases.append(doc)

    if not all_cases:
        return raw_text

    functional = [c for c in all_cases if c.get("category") == "functional"]
    boundary = [c for c in all_cases if c.get("category") == "boundary"]
    other = [c for c in all_cases if c.get("category") not in ("functional", "boundary")]

    ordered = functional + boundary + other

    # Serialize each case as a separate YAML document separated by ---
    parts: list[str] = []
    for case in ordered:
        parts.append(yaml.dump(case, default_flow_style=False, sort_keys=False).rstrip())

    return "---\n".join(parts) + "\n"


def _validate_functional_ratio(value: int | None) -> str | None:
    """Return an error message if functional-ratio is out of range, else None."""
    if value is not None and not (0 <= value <= 100):
        return "--functional-ratio must be between 0 and 100"
    return None


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns 0 on success, non-zero on failure."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Validate functional-ratio range early (Req 11.5)
    ratio_err = _validate_functional_ratio(args.functional_ratio)
    if ratio_err:
        print(f"Error: {ratio_err}", file=sys.stderr)
        return 1

    # Load config with CLI overrides (Req 13.4)
    config = load_config(config_path=args.config, overrides=_build_overrides(args))

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    # Validate app_description (Req 15.5)
    app_description = args.app_description
    if not app_description:
        print("Error: --app-description is required", file=sys.stderr)
        return 1

    try:
        orchestrator = TestGeneratorOrchestrator(config)
        result = orchestrator.generate(
            app_description=app_description,
            system_prompt=args.system_prompt,
            business_metrics=args.business_metrics,
            s3_uri=config.s3_uri,
            model_name=args.model,
            language=args.language or "English",
        )
    except Exception as exc:
        logger.error("Generation failed: %s", exc)
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    # Reorder output: functional first, then boundary, separated by --- (Req 17.2, 17.3)
    output_text = result.yaml_text
    if result.is_valid_yaml and output_text.strip():
        output_text = _reorder_yaml_output(output_text)

    # Write output (Req 15.3, 15.4)
    if args.output:
        Path(args.output).write_text(output_text, encoding="utf-8")
        logger.info("Output written to %s", args.output)
    else:
        print(output_text)

    # Print warnings to stderr
    for warning in result.warnings:
        print(f"Warning: {warning}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
