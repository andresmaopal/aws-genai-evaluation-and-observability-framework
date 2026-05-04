"""JSONL file parser for ground truth data.

Parses each non-empty line as an independent JSON object, normalizes via
FieldMapping, and produces TestCase objects with diagnostic records for
malformed lines.
"""

from __future__ import annotations

import json
from typing import IO

from test_generator.models import DiagnosticRecord, FieldMapping, TestCase


class ValidationError(Exception):
    """Raised in strict mode when a malformed record is encountered."""

    def __init__(self, file_key: str, line_number: int, reason: str) -> None:
        self.file_key = file_key
        self.line_number = line_number
        self.reason = reason
        super().__init__(f"{file_key}:{line_number}: {reason}")


class JsonlParser:
    """Line-by-line JSONL parser implementing the Parser protocol."""

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

        for line_number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue

            # Attempt JSON parse
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError as exc:
                diag = DiagnosticRecord(
                    file_key=file_key,
                    line_or_row=line_number,
                    reason=f"Invalid JSON: {exc}",
                    severity="error",
                )
                if not lenient:
                    raise ValidationError(file_key, line_number, diag.reason)
                diagnostics.append(diag)
                continue

            if not isinstance(obj, dict):
                diag = DiagnosticRecord(
                    file_key=file_key,
                    line_or_row=line_number,
                    reason="Line is not a JSON object",
                    severity="error",
                )
                if not lenient:
                    raise ValidationError(file_key, line_number, diag.reason)
                diagnostics.append(diag)
                continue

            # Resolve aliases
            resolved = field_mapping.resolve(obj)

            # Check required fields
            if "prompt" not in resolved:
                diag = DiagnosticRecord(
                    file_key=file_key,
                    line_or_row=line_number,
                    reason="Missing required field: 'prompt' (and no matching aliases)",
                    severity="error",
                )
                if not lenient:
                    raise ValidationError(file_key, line_number, diag.reason)
                diagnostics.append(diag)
                continue

            if "expected" not in resolved:
                diag = DiagnosticRecord(
                    file_key=file_key,
                    line_or_row=line_number,
                    reason="Missing required field: 'expected' (and no matching aliases)",
                    severity="error",
                )
                if not lenient:
                    raise ValidationError(file_key, line_number, diag.reason)
                diagnostics.append(diag)
                continue

            test_cases.append(TestCase.from_dict(resolved))

        return test_cases, diagnostics
