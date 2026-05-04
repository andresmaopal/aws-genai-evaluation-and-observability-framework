"""Generator orchestrator for the S3 Ground Truth Test Generator.

Loads configuration, ground truth data, builds prompts, invokes Bedrock
models via the Converse API, validates YAML output, and returns results.

Requirements: 11.2–11.4, 11.6, 17.1–17.4, 18.1–18.3, 19.3–19.5
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

import yaml

from test_generator.config import Config
from test_generator.ground_truth_loader import load_ground_truth
from test_generator.models import Diagnostics, TestCase
from test_generator.prompt_builder import build_prompt

logger = logging.getLogger(__name__)

# Required fields every model entry must have.
_REQUIRED_MODEL_FIELDS = {"model_id", "region_name", "temperature", "inference_type"}

# Default max_tokens when not specified in the model registry.
_DEFAULT_MAX_TOKENS = 4096


# ---------------------------------------------------------------------------
# GenerationResult
# ---------------------------------------------------------------------------

@dataclass
class GenerationResult:
    """Result of a test case generation run.

    Attributes:
        yaml_text:            Raw text returned by the model (ideally valid YAML).
        is_valid_yaml:        Whether *yaml_text* parsed successfully as YAML.
        test_cases_generated: Number of top-level YAML documents / test cases detected.
        functional_count:     Requested number of functional test cases.
        boundary_count:       Requested number of boundary test cases.
        model_used:           Key name of the model that was invoked.
        diagnostics:          Ground truth loading diagnostics (if S3 was used).
        warnings:             Non-fatal warnings accumulated during generation.
    """

    yaml_text: str
    is_valid_yaml: bool
    test_cases_generated: int
    functional_count: int
    boundary_count: int
    model_used: str
    diagnostics: Diagnostics | None
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Model registry helpers
# ---------------------------------------------------------------------------

def _load_model_registry(path: str) -> dict[str, dict[str, Any]]:
    """Load, validate, and deduplicate the model registry from a JSON file.

    Deduplication: when two entries share the same ``(model_id, region_name)``
    pair, the entry with the shorter key name is kept.

    Validation: entries missing any of the required fields (``model_id``,
    ``region_name``, ``temperature``, ``inference_type``) are excluded with a
    warning.  Entries without ``max_tokens`` get a default of 4096.

    Returns
    -------
    dict[str, dict]
        Cleaned model registry keyed by model name.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw: dict[str, Any] = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Failed to load model registry from '%s': %s", path, exc)
        return {}

    # --- Validate required fields -------------------------------------------
    valid: dict[str, dict[str, Any]] = {}
    for key, entry in raw.items():
        if not isinstance(entry, dict):
            logger.warning("Model entry '%s' is not a dict — skipping", key)
            continue
        missing = _REQUIRED_MODEL_FIELDS - entry.keys()
        if missing:
            logger.warning(
                "Model '%s' missing required fields %s — excluding from registry",
                key,
                sorted(missing),
            )
            continue
        # Apply default max_tokens (Req 18.2).
        entry.setdefault("max_tokens", _DEFAULT_MAX_TOKENS)
        valid[key] = entry

    # --- Deduplicate by (model_id, region_name) -----------------------------
    seen: dict[tuple[str, str], str] = {}  # (model_id, region) → key name
    for key, entry in valid.items():
        dup_key = (entry["model_id"], entry["region_name"])
        if dup_key in seen:
            existing = seen[dup_key]
            # Keep the entry with the shorter key name (Req 18.1).
            if len(key) < len(existing):
                seen[dup_key] = key
        else:
            seen[dup_key] = key

    kept_keys = set(seen.values())
    deduped = {k: v for k, v in valid.items() if k in kept_keys}

    logger.info(
        "Model registry loaded: %d entries validated, %d after deduplication (from %d raw)",
        len(valid),
        len(deduped),
        len(raw),
    )
    return deduped


# ---------------------------------------------------------------------------
# YAML validation helper
# ---------------------------------------------------------------------------

def _validate_yaml(text: str) -> tuple[bool, int]:
    """Try to parse *text* as YAML and return (is_valid, document_count)."""
    try:
        docs = list(yaml.safe_load_all(text))
        count = sum(1 for d in docs if d is not None)
        return True, count
    except yaml.YAMLError:
        return False, 0


# ---------------------------------------------------------------------------
# Bedrock invocation
# ---------------------------------------------------------------------------

def _extract_response_text(response: dict[str, Any]) -> str:
    """Extract the text content from a Bedrock Converse API response."""
    output = response.get("output", {})
    message = output.get("message", {})
    content_blocks = message.get("content", [])
    parts: list[str] = []
    for block in content_blocks:
        if "text" in block:
            parts.append(block["text"])
    return "\n".join(parts)


def _invoke_bedrock(
    bedrock_client: Any,
    model_id: str,
    prompt_text: str,
    temperature: float,
    max_tokens: int,
) -> str:
    """Invoke a Bedrock model via the Converse API and return the response text.

    Uses the Converse API which provides a unified interface across model
    families.  Claude and non-Claude models are handled identically by the
    Converse API.
    """
    messages = [{"role": "user", "content": [{"text": prompt_text}]}]

    inference_config: dict[str, Any] = {
        "maxTokens": max_tokens,
        "temperature": temperature,
    }

    response = bedrock_client.converse(
        modelId=model_id,
        messages=messages,
        inferenceConfig=inference_config,
    )

    return _extract_response_text(response)


# ---------------------------------------------------------------------------
# TestGeneratorOrchestrator
# ---------------------------------------------------------------------------

class TestGeneratorOrchestrator:
    """Core orchestration class for the test case generation pipeline.

    Workflow:
    1. Load ground truth from S3 (if ``s3_uri`` provided).
    2. Build the XML-tagged generation prompt.
    3. Invoke the selected Bedrock model via the Converse API.
    4. Validate the model output as YAML; retry once on failure.
    5. Return a ``GenerationResult``.

    Parameters
    ----------
    config:
        Resolved ``Config`` instance with all tunable parameters.
    bedrock_client:
        Optional injectable boto3 Bedrock Runtime client (for testing).
    """

    def __init__(
        self,
        config: Config,
        bedrock_client: Any | None = None,
    ) -> None:
        self.config = config
        self._bedrock_client = bedrock_client
        self._models: dict[str, dict[str, Any]] = _load_model_registry(
            config.model_list_path
        )

        # Configure root logging level from config (Req 19.5).
        logging.basicConfig(
            level=getattr(logging, config.log_level.upper(), logging.INFO),
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )

    # -- Properties ----------------------------------------------------------

    @property
    def available_models(self) -> list[str]:
        """Return sorted list of available model key names."""
        return sorted(self._models.keys())

    # -- Internal helpers ----------------------------------------------------

    def _get_bedrock_client(self, region: str) -> Any:
        """Return the Bedrock Runtime client, creating one lazily if needed."""
        if self._bedrock_client is not None:
            return self._bedrock_client
        import boto3

        self._bedrock_client = boto3.client(
            "bedrock-runtime", region_name=region
        )
        return self._bedrock_client

    def _resolve_model(self, model_name: str | None) -> tuple[str, dict[str, Any]]:
        """Look up a model by name, falling back to config default.

        Returns (key_name, model_entry).  Raises ``ValueError`` if not found.
        """
        name = model_name or self.config.model_name
        if name not in self._models:
            raise ValueError(
                f"Model '{name}' not found in registry. "
                f"Available: {', '.join(self.available_models[:10])}…"
            )
        return name, self._models[name]

    # -- Public API ----------------------------------------------------------

    def generate(
        self,
        app_description: str,
        system_prompt: str = "",
        business_metrics: str = "",
        s3_uri: str | None = None,
        ground_truth: list[TestCase] | None = None,
        model_name: str | None = None,
        language: str = "English",
    ) -> GenerationResult:
        """Run the full generation pipeline.

        Parameters
        ----------
        app_description:
            Free-text description of the application under test.
        system_prompt:
            The agent's system prompt or key features.
        business_metrics:
            Business goals / metrics.
        s3_uri:
            Optional S3 URI to load ground truth from.  Ignored when
            *ground_truth* is provided directly.
        ground_truth:
            Pre-loaded TestCase objects.  Takes precedence over *s3_uri*.
        model_name:
            Override the model to use (defaults to ``config.model_name``).
        language:
            Target language for generated test cases.

        Returns
        -------
        GenerationResult
        """
        warnings: list[str] = []
        diagnostics: Diagnostics | None = None

        # -- Resolve model ---------------------------------------------------
        key_name, model_entry = self._resolve_model(model_name)
        model_id = model_entry["model_id"]
        temperature = model_entry["temperature"]
        max_tokens = model_entry.get("max_tokens", _DEFAULT_MAX_TOKENS)
        region = model_entry.get("region_name", self.config.aws_region)

        # -- Compute functional / boundary split (Req 11.2–11.4) -------------
        total_cases = self.config.num_cases
        ratio = self.config.functional_ratio
        functional_count = round(total_cases * ratio / 100)
        boundary_count = total_cases - functional_count

        logger.info(
            "Generation config — model: %s, total cases: %d, "
            "functional: %d, boundary: %d (ratio=%d%%)",
            key_name,
            total_cases,
            functional_count,
            boundary_count,
            ratio,
        )

        # -- Load ground truth -----------------------------------------------
        test_cases: list[TestCase] = []
        if ground_truth is not None:
            test_cases = ground_truth
        elif s3_uri or self.config.s3_uri:
            uri = s3_uri or self.config.s3_uri
            assert uri is not None  # for type checker
            test_cases, diagnostics = load_ground_truth(
                s3_uri=uri,
                field_mapping=self.config.field_mapping,
                recursive=self.config.recursive,
                lenient=self.config.lenient,
            )
            logger.info("Loaded %d ground truth records from %s", len(test_cases), uri)

        # -- Build prompt ----------------------------------------------------
        prompt_text = build_prompt(
            test_cases=test_cases,
            app_description=app_description,
            system_prompt=system_prompt,
            business_metrics=business_metrics,
            functional_count=functional_count,
            boundary_count=boundary_count,
            num_questions_per_case=self.config.num_questions_per_case,
            language=language,
        )

        # Rough token estimate (Req 19.3).
        token_estimate = len(prompt_text) // 4
        logger.info("Prompt token estimate: ~%d tokens", token_estimate)

        # -- Invoke model ----------------------------------------------------
        client = self._get_bedrock_client(region)
        raw_text = ""
        try:
            raw_text = _invoke_bedrock(
                bedrock_client=client,
                model_id=model_id,
                prompt_text=prompt_text,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            logger.error("Model invocation failed for '%s': %s", key_name, exc)
            return GenerationResult(
                yaml_text="",
                is_valid_yaml=False,
                test_cases_generated=0,
                functional_count=functional_count,
                boundary_count=boundary_count,
                model_used=key_name,
                diagnostics=diagnostics,
                warnings=[f"Model invocation failed: {exc}"],
            )

        # -- Validate YAML (Req 17.4) — retry once on failure ---------------
        is_valid, doc_count = _validate_yaml(raw_text)
        if not is_valid:
            logger.warning(
                "Model output is not valid YAML — retrying once (model=%s)", key_name
            )
            try:
                raw_text = _invoke_bedrock(
                    bedrock_client=client,
                    model_id=model_id,
                    prompt_text=prompt_text,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                is_valid, doc_count = _validate_yaml(raw_text)
            except Exception as exc:
                logger.error("Retry invocation failed for '%s': %s", key_name, exc)
                warnings.append(f"Retry invocation failed: {exc}")

        if not is_valid:
            logger.error("YAML parse failure after retry (model=%s)", key_name)
            warnings.append(
                "Model output is not valid YAML after retry; returning raw text."
            )

        return GenerationResult(
            yaml_text=raw_text,
            is_valid_yaml=is_valid,
            test_cases_generated=doc_count,
            functional_count=functional_count,
            boundary_count=boundary_count,
            model_used=key_name,
            diagnostics=diagnostics,
            warnings=warnings,
        )
