"""JSON file parser for ground truth data.

Handles top-level arrays and objects with recognized wrapper keys
(``data``, ``records``, ``samples``, ``test_cases``).  Each element is
validated and normalized into a TestCase via FieldMapping.
"""

from __future__ import annotations

import json
from typing import IO

from test_generator.models import DiagnosticRecord, FieldMapping, TestCase
from test_generator.parsers.jsonl_parser import ValidationError

RECOGNIZED_WRAPPER_KEYS = {"data", "records", "samples", "test_cases"}


class JsonParser:
    """Top-level JSON array / wrapper-key parser implementing the Parser protocol."""

    def parse(
        self,
        stream: IO[bytes],
        file_key: str,
        field_mapping: FieldMapping,
        lenient: bool,
    ) -> tuple[list[TestCase], list[DiagnosticRecord]]:
        test_cases: list[TestCase] = []
        diagnostics: list[DiagnosticRecord] = []

        raw = stream.read()
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw

        # Parse the entire file as JSON
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            diag = DiagnosticRecord(
                file_key=file_key,
                line_or_row=None,
                reason=f"Invalid JSON file: {exc}",
                severity="error",
            )
            if not lenient:
                raise ValidationError(file_key, 0, diag.reason)
            diagnostics.append(diag)
            return test_cases, diagnostics

        # Extract the records array
        records: list | None = None

        if isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            for key in RECOGNIZED_WRAPPER_KEYS:
                if key in data and isinstance(data[key], list):
                    records = data[key]
                    break

        if records is None:
            diag = DiagnosticRecord(
                file_key=file_key,
                line_or_row=None,
                reason="Unsupported JSON schema: expected a top-level array or an object with a recognized wrapper key "
                       f"({', '.join(sorted(RECOGNIZED_WRAPPER_KEYS))})",
                severity="error",
            )
            if not lenient:
                raise ValidationError(file_key, 0, diag.reason)
            diagnostics.append(diag)
            return test_cases, diagnostics

        # Validate each record (1-indexed for user-facing diagnostics)
        for idx, record in enumerate(records, start=1):
            if not isinstance(record, dict):
                diag = DiagnosticRecord(
                    file_key=file_key,
                    line_or_row=idx,
                    reason=f"Record {idx} is not a JSON object",
                    severity="error",
                )
                if not lenient:
                    raise ValidationError(file_key, idx, diag.reason)
                diagnostics.append(diag)
                continue

            resolved = field_mapping.resolve(record)

            if "prompt" not in resolved:
                diag = DiagnosticRecord(
                    file_key=file_key,
                    line_or_row=idx,
                    reason="Missing required field: 'prompt' (and no matching aliases)",
                    severity="error",
                )
                if not lenient:
                    raise ValidationError(file_key, idx, diag.reason)
                diagnostics.append(diag)
                continue

            if "expected" not in resolved:
                diag = DiagnosticRecord(
                    file_key=file_key,
                    line_or_row=idx,
                    reason="Missing required field: 'expected' (and no matching aliases)",
                    severity="error",
                )
                if not lenient:
                    raise ValidationError(file_key, idx, diag.reason)
                diagnostics.append(diag)
                continue

            test_cases.append(TestCase.from_dict(resolved))

        return test_cases, diagnostics
