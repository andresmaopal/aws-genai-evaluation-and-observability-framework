"""Data models for the S3 Ground Truth Test Generator.

Defines the core dataclasses used throughout the package:

- TestCase       — A single ground truth sample (prompt + expected answer).
- DiagnosticRecord — One warning or error produced during parsing.
- Diagnostics    — Aggregate parsing report (skipped files, malformed records, counts).
- FieldMapping   — Alias lists that map source-file keys to canonical TestCase fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# TestCase
# ---------------------------------------------------------------------------

@dataclass
class TestCase:
    """A single ground truth test case.

    Attributes:
        prompt:     The user question / input text (required).
        expected:   The expected agent response — a string or list of strings (required).
        id:         Optional unique identifier for the test case.
        contexts:   Supporting context passages (default empty list).
        metadata:   Arbitrary extra fields from the source record (default empty dict).
        agent_spec: Agent-specific configuration hints (default empty dict).
    """

    prompt: str
    expected: str | list[str]
    id: str | None = None
    contexts: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    agent_spec: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary of all fields."""
        return {
            "id": self.id,
            "prompt": self.prompt,
            "expected": self.expected,
            "contexts": self.contexts,
            "metadata": self.metadata,
            "agent_spec": self.agent_spec,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TestCase":
        """Construct a TestCase from a dictionary.

        Raises:
            ValueError: If the required ``prompt`` or ``expected`` key is missing.
        """
        if "prompt" not in d:
            raise ValueError("Missing required field: 'prompt'")
        if "expected" not in d:
            raise ValueError("Missing required field: 'expected'")
        return cls(
            prompt=d["prompt"],
            expected=d["expected"],
            id=d.get("id"),
            contexts=d.get("contexts", []),
            metadata=d.get("metadata", {}),
            agent_spec=d.get("agent_spec", {}),
        )


# ---------------------------------------------------------------------------
# DiagnosticRecord
# ---------------------------------------------------------------------------

@dataclass
class DiagnosticRecord:
    """A single diagnostic entry produced during file parsing.

    Attributes:
        file_key:   The S3 object key (or local path) of the source file.
        line_or_row: The 1-based line or row number where the issue occurred, or None.
        reason:     Human-readable description of the problem.
        severity:   ``"warning"`` or ``"error"``.
    """

    file_key: str
    line_or_row: int | None
    reason: str
    severity: str  # "warning" | "error"


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

@dataclass
class Diagnostics:
    """Aggregate diagnostics report for a ground truth loading run.

    Attributes:
        skipped_files:            Files that were skipped entirely (wrong extension, zero-byte, etc.).
        malformed_records:        Individual records/lines that failed validation.
        total_files_scanned:      Number of S3 objects examined.
        files_successfully_parsed: Number of files that produced at least one TestCase.
        total_test_cases:         Total TestCase objects produced across all files.
    """

    skipped_files: list[DiagnosticRecord] = field(default_factory=list)
    malformed_records: list[DiagnosticRecord] = field(default_factory=list)
    total_files_scanned: int = 0
    files_successfully_parsed: int = 0
    total_test_cases: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the diagnostics."""
        return {
            "skipped_files": [
                {"file_key": r.file_key, "reason": r.reason}
                for r in self.skipped_files
            ],
            "malformed_records": [
                {
                    "file_key": r.file_key,
                    "line_or_row": r.line_or_row,
                    "reason": r.reason,
                }
                for r in self.malformed_records
            ],
            "total_files_scanned": self.total_files_scanned,
            "files_successfully_parsed": self.files_successfully_parsed,
            "total_test_cases": self.total_test_cases,
        }


# ---------------------------------------------------------------------------
# FieldMapping
# ---------------------------------------------------------------------------

@dataclass
class FieldMapping:
    """Maps alternative source-file column/key names to canonical TestCase fields.

    Each alias list is checked in order; the first match wins.  Fields that do
    not match any alias (and are not canonical names) are placed into the
    TestCase ``metadata`` dict.

    Attributes:
        prompt_aliases:   Alternative names for the ``prompt`` field.
        expected_aliases: Alternative names for the ``expected`` field.
        id_aliases:       Alternative names for the ``id`` field.
        contexts_aliases: Alternative names for the ``contexts`` field.
    """

    prompt_aliases: list[str] = field(
        default_factory=lambda: ["question", "input", "query", "user_input"]
    )
    expected_aliases: list[str] = field(
        default_factory=lambda: [
            "answer", "output", "response", "expected_output", "expected_response"
        ]
    )
    id_aliases: list[str] = field(
        default_factory=lambda: ["test_id", "case_id", "identifier"]
    )
    contexts_aliases: list[str] = field(
        default_factory=lambda: ["context", "documents", "passages", "reference"]
    )

    def resolve(self, record: dict[str, Any]) -> dict[str, Any]:
        """Map source record keys to canonical TestCase field names using aliases.

        Keys that match a canonical name (``prompt``, ``expected``, ``id``,
        ``contexts``, ``metadata``, ``agent_spec``) are kept as-is.  Keys that
        match an alias are mapped to the corresponding canonical name.
        Unrecognized keys are collected into the ``metadata`` dict.

        Returns:
            A dictionary whose keys are canonical TestCase field names, ready
            to be passed to ``TestCase.from_dict()``.
        """
        # Canonical field names that are passed through directly.
        canonical_names = {"prompt", "expected", "id", "contexts", "metadata", "agent_spec"}

        # Build alias → canonical lookup.
        alias_map: dict[str, str] = {}
        for alias in self.prompt_aliases:
            alias_map[alias] = "prompt"
        for alias in self.expected_aliases:
            alias_map[alias] = "expected"
        for alias in self.id_aliases:
            alias_map[alias] = "id"
        for alias in self.contexts_aliases:
            alias_map[alias] = "contexts"

        resolved: dict[str, Any] = {}
        extra_metadata: dict[str, Any] = {}

        for key, value in record.items():
            if key in canonical_names:
                resolved[key] = value
            elif key in alias_map:
                canonical_key = alias_map[key]
                # Only set if not already present (canonical name takes precedence).
                if canonical_key not in resolved:
                    resolved[canonical_key] = value
            else:
                extra_metadata[key] = value

        # Merge extra metadata into any existing metadata dict.
        if extra_metadata:
            existing_meta = resolved.get("metadata", {})
            if isinstance(existing_meta, dict):
                existing_meta.update(extra_metadata)
            else:
                existing_meta = extra_metadata
            resolved["metadata"] = existing_meta

        return resolved
