"""CSV file parser for ground truth data.

Parses CSV files with a required header row, maps column names to TestCase
fields via FieldMapping, and handles quoted fields / embedded commas per
RFC 4180.
"""

from __future__ import annotations

import csv
import io
from typing import IO

from test_generator.models import DiagnosticRecord, FieldMapping, TestCase
from test_generator.parsers.jsonl_parser import ValidationError


class CsvParser:
    """Header-based CSV parser implementing the Parser protocol."""

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

        # Check for empty / header-less files
        stripped = text.strip()
        if not stripped:
            diag = DiagnosticRecord(
                file_key=file_key,
                line_or_row=None,
                reason="CSV file is empty (no header row)",
                severity="error",
            )
            if not lenient:
                raise ValidationError(file_key, 0, diag.reason)
            diagnostics.append(diag)
            return test_cases, diagnostics

        reader = csv.DictReader(io.StringIO(text))

        if reader.fieldnames is None or len(reader.fieldnames) == 0:
            diag = DiagnosticRecord(
                file_key=file_key,
                line_or_row=None,
                reason="CSV file has no header row",
                severity="error",
            )
            if not lenient:
                raise ValidationError(file_key, 0, diag.reason)
            diagnostics.append(diag)
            return test_cases, diagnostics

        for row_number, row in enumerate(reader, start=2):  # row 1 is header
            # Convert DictReader row (which may have None values) to a clean dict
            record = {k: v for k, v in row.items() if k is not None and v is not None and v != ""}

            if not record:
                continue

            resolved = field_mapping.resolve(record)

            if "prompt" not in resolved:
                diag = DiagnosticRecord(
                    file_key=file_key,
                    line_or_row=row_number,
                    reason="Missing required field: 'prompt' (and no matching aliases)",
                    severity="error",
                )
                if not lenient:
                    raise ValidationError(file_key, row_number, diag.reason)
                diagnostics.append(diag)
                continue

            if "expected" not in resolved:
                diag = DiagnosticRecord(
                    file_key=file_key,
                    line_or_row=row_number,
                    reason="Missing required field: 'expected' (and no matching aliases)",
                    severity="error",
                )
                if not lenient:
                    raise ValidationError(file_key, row_number, diag.reason)
                diagnostics.append(diag)
                continue

            test_cases.append(TestCase.from_dict(resolved))

        return test_cases, diagnostics
