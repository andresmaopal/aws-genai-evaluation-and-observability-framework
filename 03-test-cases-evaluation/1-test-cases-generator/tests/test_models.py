"""Unit tests for test_generator.models.

Covers:
- TestCase.from_dict raises ValueError when prompt is missing
- TestCase.from_dict raises ValueError when expected is missing
- FieldMapping.resolve correctly maps aliased keys to canonical names
- FieldMapping.resolve places unrecognized fields into metadata
- Diagnostics.to_dict() produces valid JSON-serializable output

Requirements: 6.2, 6.3, 7.4, 20.4, 20.5
"""

import json

import pytest

from test_generator.models import (
    DiagnosticRecord,
    Diagnostics,
    FieldMapping,
    TestCase,
)


# ---------------------------------------------------------------------------
# TestCase.from_dict — missing required fields
# ---------------------------------------------------------------------------


class TestCaseFromDictValidation:
    """Tests for ValueError on missing required fields (Reqs 20.4, 20.5)."""

    def test_missing_prompt_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="prompt"):
            TestCase.from_dict({"expected": "some answer"})

    def test_missing_expected_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="expected"):
            TestCase.from_dict({"prompt": "some question"})

    def test_missing_both_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            TestCase.from_dict({})

    def test_valid_minimal_dict_succeeds(self) -> None:
        tc = TestCase.from_dict({"prompt": "q", "expected": "a"})
        assert tc.prompt == "q"
        assert tc.expected == "a"
        assert tc.id is None
        assert tc.contexts == []
        assert tc.metadata == {}
        assert tc.agent_spec == {}


# ---------------------------------------------------------------------------
# FieldMapping.resolve — alias mapping (Reqs 6.2, 6.3)
# ---------------------------------------------------------------------------


class TestFieldMappingResolve:
    """Tests for FieldMapping.resolve alias resolution."""

    def test_prompt_alias_mapped(self) -> None:
        fm = FieldMapping()
        result = fm.resolve({"question": "hello", "expected": "world"})
        assert result["prompt"] == "hello"
        assert result["expected"] == "world"

    def test_expected_alias_mapped(self) -> None:
        fm = FieldMapping()
        result = fm.resolve({"prompt": "q", "answer": "a"})
        assert result["expected"] == "a"

    def test_id_alias_mapped(self) -> None:
        fm = FieldMapping()
        result = fm.resolve({"prompt": "q", "expected": "a", "test_id": "42"})
        assert result["id"] == "42"

    def test_contexts_alias_mapped(self) -> None:
        fm = FieldMapping()
        result = fm.resolve(
            {"prompt": "q", "expected": "a", "documents": ["doc1", "doc2"]}
        )
        assert result["contexts"] == ["doc1", "doc2"]

    def test_canonical_name_takes_precedence_over_alias(self) -> None:
        fm = FieldMapping()
        result = fm.resolve(
            {"prompt": "canonical", "question": "alias", "expected": "a"}
        )
        assert result["prompt"] == "canonical"

    def test_multiple_aliases_resolved(self) -> None:
        fm = FieldMapping()
        result = fm.resolve({"input": "q", "response": "a", "case_id": "7"})
        assert result["prompt"] == "q"
        assert result["expected"] == "a"
        assert result["id"] == "7"

    def test_unrecognized_fields_placed_in_metadata(self) -> None:
        fm = FieldMapping()
        result = fm.resolve(
            {
                "prompt": "q",
                "expected": "a",
                "custom_tag": "foo",
                "priority": 3,
            }
        )
        assert "metadata" in result
        assert result["metadata"]["custom_tag"] == "foo"
        assert result["metadata"]["priority"] == 3

    def test_unrecognized_fields_merged_with_existing_metadata(self) -> None:
        fm = FieldMapping()
        result = fm.resolve(
            {
                "prompt": "q",
                "expected": "a",
                "metadata": {"existing": True},
                "extra_field": "bar",
            }
        )
        assert result["metadata"]["existing"] is True
        assert result["metadata"]["extra_field"] == "bar"

    def test_empty_record_returns_empty_resolved(self) -> None:
        fm = FieldMapping()
        result = fm.resolve({})
        assert result == {}

    def test_custom_aliases(self) -> None:
        fm = FieldMapping(
            prompt_aliases=["user_query"],
            expected_aliases=["bot_reply"],
        )
        result = fm.resolve({"user_query": "hi", "bot_reply": "hello"})
        assert result["prompt"] == "hi"
        assert result["expected"] == "hello"


# ---------------------------------------------------------------------------
# Diagnostics.to_dict — JSON serialization (Req 7.4)
# ---------------------------------------------------------------------------


class TestDiagnosticsToDict:
    """Tests for Diagnostics.to_dict() JSON serializability."""

    def test_empty_diagnostics_serializable(self) -> None:
        diag = Diagnostics()
        d = diag.to_dict()
        # Must not raise
        serialized = json.dumps(d)
        assert isinstance(serialized, str)
        assert d["skipped_files"] == []
        assert d["malformed_records"] == []
        assert d["total_files_scanned"] == 0

    def test_populated_diagnostics_serializable(self) -> None:
        diag = Diagnostics(
            skipped_files=[
                DiagnosticRecord("s3://b/skip.txt", None, "unsupported ext", "warning"),
            ],
            malformed_records=[
                DiagnosticRecord("s3://b/data.jsonl", 5, "invalid JSON", "error"),
                DiagnosticRecord("s3://b/data.csv", 12, "missing prompt", "error"),
            ],
            total_files_scanned=10,
            files_successfully_parsed=8,
            total_test_cases=42,
        )
        d = diag.to_dict()
        serialized = json.dumps(d)
        assert isinstance(serialized, str)

        assert len(d["skipped_files"]) == 1
        assert d["skipped_files"][0]["file_key"] == "s3://b/skip.txt"

        assert len(d["malformed_records"]) == 2
        assert d["malformed_records"][0]["line_or_row"] == 5

        assert d["total_files_scanned"] == 10
        assert d["files_successfully_parsed"] == 8
        assert d["total_test_cases"] == 42

    def test_to_dict_roundtrips_through_json(self) -> None:
        diag = Diagnostics(
            skipped_files=[
                DiagnosticRecord("key.bin", None, "wrong ext", "warning"),
            ],
            malformed_records=[],
            total_files_scanned=3,
            files_successfully_parsed=2,
            total_test_cases=15,
        )
        d = diag.to_dict()
        reloaded = json.loads(json.dumps(d))
        assert reloaded == d
