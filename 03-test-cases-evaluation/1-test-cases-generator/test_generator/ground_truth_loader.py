"""S3 ground truth loader.

Scans an S3 prefix for whitelisted file types (.jsonl, .json, .csv),
dispatches each file to the appropriate parser, and aggregates the results
into a list of TestCase objects and a Diagnostics report.

Key behaviours:
- Recursive or non-recursive listing controlled by ``recursive`` parameter.
- Exponential-backoff retry (up to 3 attempts) on S3 throttling errors.
- Raises ``S3AccessError`` on permission / missing-bucket errors.
- Raises ``FileNotFoundError`` when no whitelisted files are found.
- Defaults to lenient mode (skip malformed records, keep going).
"""

from __future__ import annotations

import io
import logging
import os
import time
from typing import Any

from test_generator.models import (
    DiagnosticRecord,
    Diagnostics,
    FieldMapping,
    TestCase,
)
from test_generator.parsers import PARSER_REGISTRY

logger = logging.getLogger(__name__)

# Extensions accepted by the loader.
WHITELISTED_EXTENSIONS: frozenset[str] = frozenset(PARSER_REGISTRY.keys())

# Retry configuration for S3 throttling errors.
_MAX_RETRIES = 3
_BACKOFF_BASE = 1.0  # seconds


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class S3AccessError(Exception):
    """Raised when an S3 operation fails due to permissions, missing bucket,
    or throttling that exceeds the retry budget."""

    def __init__(self, bucket: str, aws_error_code: str, message: str) -> None:
        self.bucket = bucket
        self.aws_error_code = aws_error_code
        self.message = message
        super().__init__(message)


# ---------------------------------------------------------------------------
# URI helpers
# ---------------------------------------------------------------------------

def parse_s3_uri(uri: str) -> tuple[str, str]:
    """Parse ``s3://bucket/prefix`` into *(bucket, prefix)*.

    A missing trailing slash on the prefix is acceptable — the caller should
    treat the value as a prefix for ``list_objects_v2``.

    Raises:
        ValueError: If *uri* does not match ``s3://<bucket>/<prefix>``.
    """
    if not uri.startswith("s3://"):
        raise ValueError(
            f"Invalid S3 URI '{uri}': expected format s3://<bucket>/<prefix>"
        )
    without_scheme = uri[len("s3://"):]
    if not without_scheme or "/" not in without_scheme:
        # Must have at least bucket/prefix (prefix can be empty after slash).
        # Accept "s3://bucket/" as bucket="" prefix="" edge — but bucket must
        # be non-empty.
        if without_scheme and without_scheme.endswith("/"):
            bucket = without_scheme.rstrip("/")
            if bucket:
                return bucket, ""
        raise ValueError(
            f"Invalid S3 URI '{uri}': expected format s3://<bucket>/<prefix>"
        )
    bucket, prefix = without_scheme.split("/", 1)
    if not bucket:
        raise ValueError(
            f"Invalid S3 URI '{uri}': bucket name must not be empty"
        )
    return bucket, prefix


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_throttling_error(error: Any) -> bool:
    """Return True if a botocore ClientError is a throttling / rate-limit error."""
    code = getattr(error, "response", {}).get("Error", {}).get("Code", "")
    return code in {"Throttling", "SlowDown", "RequestLimitExceeded"}


def _s3_call_with_retry(func, bucket: str, **kwargs):
    """Call *func* with retry + exponential backoff on throttling errors.

    Raises ``S3AccessError`` after exhausting retries or on non-throttling
    client errors.
    """
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            return func(**kwargs)
        except Exception as exc:
            # Check for botocore ClientError-like shape.
            error_code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
            if _is_throttling_error(exc):
                last_exc = exc
                wait = _BACKOFF_BASE * (2 ** (attempt - 1))
                logger.warning(
                    "S3 throttling on bucket '%s' (attempt %d/%d), retrying in %.1fs",
                    bucket, attempt, _MAX_RETRIES, wait,
                )
                time.sleep(wait)
                continue
            # Non-throttling AWS errors — raise immediately.
            if error_code:
                raise S3AccessError(
                    bucket=bucket,
                    aws_error_code=error_code,
                    message=str(exc),
                ) from exc
            # Unknown exception — re-raise as-is.
            raise
    # Exhausted retries on throttling.
    raise S3AccessError(
        bucket=bucket,
        aws_error_code="Throttling",
        message=f"S3 throttling persisted after {_MAX_RETRIES} retries: {last_exc}",
    ) from last_exc



def _list_objects(
    s3_client: Any,
    bucket: str,
    prefix: str,
    recursive: bool,
) -> list[dict[str, Any]]:
    """Return a list of S3 object metadata dicts under *prefix*.

    Each dict has at least ``Key`` and ``Size`` keys.
    """
    kwargs: dict[str, Any] = {"Bucket": bucket, "Prefix": prefix}
    if not recursive:
        kwargs["Delimiter"] = "/"

    objects: list[dict[str, Any]] = []
    while True:
        response = _s3_call_with_retry(
            s3_client.list_objects_v2, bucket, **kwargs
        )
        for obj in response.get("Contents", []):
            objects.append(obj)
        if response.get("IsTruncated"):
            kwargs["ContinuationToken"] = response["NextContinuationToken"]
        else:
            break
    return objects


def _file_extension(key: str) -> str:
    """Return the lowercased file extension including the dot, e.g. '.jsonl'."""
    _, ext = os.path.splitext(key)
    return ext.lower()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_ground_truth(
    s3_uri: str,
    field_mapping: FieldMapping | None = None,
    recursive: bool = True,
    lenient: bool = True,
    s3_client: Any | None = None,
) -> tuple[list[TestCase], Diagnostics]:
    """Load ground truth data from an S3 prefix.

    Parameters
    ----------
    s3_uri:
        S3 URI in the form ``s3://bucket/prefix``.
    field_mapping:
        Optional alias mapping.  Defaults to ``FieldMapping()`` with
        standard aliases.
    recursive:
        If True, list objects in nested sub-prefixes.
    lenient:
        If True (default), skip malformed records and continue.
    s3_client:
        An injectable boto3 S3 client.  When ``None`` a default client is
        created via ``boto3.client("s3")``.

    Returns
    -------
    tuple[list[TestCase], Diagnostics]

    Raises
    ------
    ValueError
        If *s3_uri* is not a valid S3 URI.
    FileNotFoundError
        If no whitelisted files are found under the prefix.
    S3AccessError
        On permission errors, missing bucket, or throttling after retries.
    """
    if field_mapping is None:
        field_mapping = FieldMapping()

    if s3_client is None:
        import boto3
        s3_client = boto3.client("s3")

    bucket, prefix = parse_s3_uri(s3_uri)
    logger.info("Scanning S3 URI: %s (bucket=%s, prefix=%s)", s3_uri, bucket, prefix)

    # --- Discover objects ---------------------------------------------------
    all_objects = _list_objects(s3_client, bucket, prefix, recursive)
    logger.info("Discovered %d objects under prefix '%s'", len(all_objects), prefix)

    diagnostics = Diagnostics()
    diagnostics.total_files_scanned = len(all_objects)

    # --- Filter by whitelist and zero-byte ----------------------------------
    whitelisted: list[dict[str, Any]] = []
    for obj in all_objects:
        key = obj["Key"]
        size = obj.get("Size", 0)
        ext = _file_extension(key)

        if ext not in WHITELISTED_EXTENSIONS:
            reason = f"Extension '{ext}' not in whitelist {sorted(WHITELISTED_EXTENSIONS)}"
            logger.warning("Skipping file '%s': %s", key, reason)
            diagnostics.skipped_files.append(
                DiagnosticRecord(file_key=key, line_or_row=None, reason=reason, severity="warning")
            )
            continue

        if size == 0:
            reason = "Zero-byte file"
            logger.warning("Skipping file '%s': %s", key, reason)
            diagnostics.skipped_files.append(
                DiagnosticRecord(file_key=key, line_or_row=None, reason=reason, severity="warning")
            )
            continue

        whitelisted.append(obj)

    logger.info("%d files match whitelist out of %d scanned", len(whitelisted), len(all_objects))

    if not whitelisted:
        raise FileNotFoundError(
            f"No supported ground truth files ({', '.join(sorted(WHITELISTED_EXTENSIONS))}) "
            f"found under {s3_uri}"
        )

    # --- Parse each file ----------------------------------------------------
    all_test_cases: list[TestCase] = []

    for obj in whitelisted:
        key = obj["Key"]
        ext = _file_extension(key)
        parser = PARSER_REGISTRY[ext]

        # Download file content.
        response = _s3_call_with_retry(
            s3_client.get_object, bucket, Bucket=bucket, Key=key
        )
        body_bytes: bytes = response["Body"].read()
        stream = io.BytesIO(body_bytes)

        try:
            test_cases, diag_records = parser.parse(
                stream=stream,
                file_key=key,
                field_mapping=field_mapping,
                lenient=lenient,
            )
        except Exception as exc:
            # In lenient mode, record the error and continue.
            if lenient:
                reason = f"Parser error: {exc}"
                logger.warning("Error parsing '%s': %s", key, reason)
                diagnostics.malformed_records.append(
                    DiagnosticRecord(file_key=key, line_or_row=None, reason=reason, severity="error")
                )
                continue
            raise

        # Accumulate results.
        all_test_cases.extend(test_cases)
        diagnostics.malformed_records.extend(diag_records)

        if test_cases:
            diagnostics.files_successfully_parsed += 1

        for rec in diag_records:
            logger.warning(
                "Malformed record in '%s' (line/row %s): %s",
                rec.file_key, rec.line_or_row, rec.reason,
            )

    diagnostics.total_test_cases = len(all_test_cases)
    logger.info(
        "Ground truth loading complete: %d test cases from %d files (%d files skipped, %d malformed records)",
        diagnostics.total_test_cases,
        diagnostics.files_successfully_parsed,
        len(diagnostics.skipped_files),
        len(diagnostics.malformed_records),
    )

    return all_test_cases, diagnostics
