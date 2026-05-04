"""Parser registry and base protocol for ground truth file parsers.

Each file format (JSONL, JSON, CSV) implements the Parser protocol and is
registered in PARSER_REGISTRY keyed by file extension.  New formats can be
added by implementing the protocol and inserting into the registry.
"""

from __future__ import annotations

from typing import IO, Protocol

from test_generator.models import DiagnosticRecord, FieldMapping, TestCase
from test_generator.parsers.csv_parser import CsvParser
from test_generator.parsers.json_parser import JsonParser
from test_generator.parsers.jsonl_parser import JsonlParser, ValidationError


class Parser(Protocol):
    """Common interface that every file-format parser must implement."""

    def parse(
        self,
        stream: IO[bytes],
        file_key: str,
        field_mapping: FieldMapping,
        lenient: bool,
    ) -> tuple[list[TestCase], list[DiagnosticRecord]]:
        """Parse a file stream into TestCase objects and diagnostic records."""
        ...


PARSER_REGISTRY: dict[str, Parser] = {
    ".jsonl": JsonlParser(),
    ".json": JsonParser(),
    ".csv": CsvParser(),
}

__all__ = [
    "Parser",
    "PARSER_REGISTRY",
    "JsonlParser",
    "JsonParser",
    "CsvParser",
    "ValidationError",
]
