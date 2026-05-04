"""Unit tests for the S3 ground truth loader.

Covers requirements 1.1-1.5, 2.1-2.6, 8.1-8.3.
All S3 interactions are mocked — no real AWS calls are made.
"""
from __future__ import annotations

import io
import json
from unittest.mock import MagicMock, patch

import pytest

from test_generator.ground_truth_loader import (
    S3AccessError,
    load_ground_truth,
    parse_s3_uri,
)
from test_generator.models import FieldMapping


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_s3_client(
    objects: list[dict] | None = None,
    file_contents: dict[str, bytes] | None = None,
    list_error: Exception | None = None,
    get_error: Exception | None = None,
) -> MagicMock:
    """Build a mock boto3 S3 client.

    Parameters
    ----------
    objects:
        List of dicts with at least ``Key`` and ``Size``.
    file_contents:
        Mapping from S3 key to raw bytes returned by ``get_object``.
    list_error:
        If set, ``list_objects_v2`` raises this on every call.
    get_error:
        If set, ``get_object`` raises this on every call.
    """
    client = MagicMock()

    if list_error:
        client.list_objects_v2.side_effect = list_error
    else:
        client.list_objects_v2.return_value = {
            "Contents": objects or [],
            "IsTruncated": False,
        }

    if get_error:
        client.get_object.side_effect = get_error
    elif file_contents:
        def _get_object(Bucket, Key):  # noqa: N803
            body = MagicMock()
            body.read.return_value = file_contents[Key]
            return {"Body": body}
        client.get_object.side_effect = _get_object

    return client


def _jsonl_bytes(*records: dict) -> bytes:
    return "\n".join(json.dumps(r) for r in records).encode()


def _client_error(code: str, message: str = "error") -> Exception:
    """Create a botocore-ClientError-like exception with a ``response`` dict."""
    exc = Exception(message)
    exc.response = {"Error": {"Code": code, "Message": message}}
    return exc


# ===================================================================
# parse_s3_uri
# ===================================================================

class TestParseS3Uri:
    def test_valid_uri_with_prefix(self):
        assert parse_s3_uri("s3://my-bucket/some/prefix/") == ("my-bucket", "some/prefix/")

    def test_valid_uri_without_trailing_slash(self):
        bucket, prefix = parse_s3_uri("s3://my-bucket/data")
        assert bucket == "my-bucket"
        assert prefix == "data"

    def test_valid_uri_empty_prefix(self):
        assert parse_s3_uri("s3://my-bucket/") == ("my-bucket", "")

    def test_invalid_scheme(self):
        with pytest.raises(ValueError, match="expected format"):
            parse_s3_uri("http://bucket/prefix")

    def test_missing_prefix_no_slash(self):
        with pytest.raises(ValueError, match="expected format"):
            parse_s3_uri("s3://bucket-only")

    def test_empty_after_scheme(self):
        with pytest.raises(ValueError, match="expected format"):
            parse_s3_uri("s3://")

    def test_empty_bucket(self):
        with pytest.raises(ValueError):
            parse_s3_uri("s3:///prefix")


# ===================================================================
# File discovery
# ===================================================================

class TestFileDiscovery:
    def test_recursive_lists_all(self):
        objects = [
            {"Key": "data/a.jsonl", "Size": 100},
            {"Key": "data/sub/b.json", "Size": 200},
        ]
        contents = {
            "data/a.jsonl": _jsonl_bytes({"prompt": "p", "expected": "e"}),
            "data/sub/b.json": json.dumps([{"prompt": "p2", "expected": "e2"}]).encode(),
        }
        client = _make_s3_client(objects=objects, file_contents=contents)
        cases, diag = load_ground_truth("s3://bkt/data/", recursive=True, s3_client=client)
        assert len(cases) == 2
        assert diag.total_files_scanned == 2
        assert diag.files_successfully_parsed == 2

    def test_non_recursive_uses_delimiter(self):
        objects = [{"Key": "data/a.jsonl", "Size": 50}]
        contents = {"data/a.jsonl": _jsonl_bytes({"prompt": "p", "expected": "e"})}
        client = _make_s3_client(objects=objects, file_contents=contents)
        load_ground_truth("s3://bkt/data/", recursive=False, s3_client=client)
        call_kwargs = client.list_objects_v2.call_args
        assert call_kwargs[1].get("Delimiter") == "/" or call_kwargs.kwargs.get("Delimiter") == "/"


# ===================================================================
# Whitelist filtering
# ===================================================================

class TestWhitelistFiltering:
    def test_non_whitelisted_extension_skipped(self):
        objects = [
            {"Key": "data/readme.txt", "Size": 10},
            {"Key": "data/a.jsonl", "Size": 50},
        ]
        contents = {"data/a.jsonl": _jsonl_bytes({"prompt": "p", "expected": "e"})}
        client = _make_s3_client(objects=objects, file_contents=contents)
        cases, diag = load_ground_truth("s3://bkt/data/", s3_client=client)
        assert len(cases) == 1
        assert len(diag.skipped_files) == 1
        assert "txt" in diag.skipped_files[0].reason

    def test_zero_byte_file_skipped(self):
        objects = [
            {"Key": "data/empty.jsonl", "Size": 0},
            {"Key": "data/ok.jsonl", "Size": 50},
        ]
        contents = {"data/ok.jsonl": _jsonl_bytes({"prompt": "p", "expected": "e"})}
        client = _make_s3_client(objects=objects, file_contents=contents)
        cases, diag = load_ground_truth("s3://bkt/data/", s3_client=client)
        assert len(cases) == 1
        skip_reasons = [r.reason for r in diag.skipped_files]
        assert any("Zero-byte" in r for r in skip_reasons)

    def test_no_whitelisted_files_raises(self):
        objects = [{"Key": "data/readme.md", "Size": 100}]
        client = _make_s3_client(objects=objects)
        with pytest.raises(FileNotFoundError, match="No supported ground truth files"):
            load_ground_truth("s3://bkt/data/", s3_client=client)

    def test_empty_prefix_raises(self):
        client = _make_s3_client(objects=[])
        with pytest.raises(FileNotFoundError):
            load_ground_truth("s3://bkt/data/", s3_client=client)



# ===================================================================
# S3 error handling
# ===================================================================

class TestS3ErrorHandling:
    @patch("test_generator.ground_truth_loader.time.sleep")
    def test_throttling_retries_then_raises(self, mock_sleep):
        exc = _client_error("Throttling")
        client = _make_s3_client(list_error=exc)
        with pytest.raises(S3AccessError) as exc_info:
            load_ground_truth("s3://bkt/data/", s3_client=client)
        assert exc_info.value.aws_error_code == "Throttling"
        assert exc_info.value.bucket == "bkt"
        # Should have retried 3 times.
        assert client.list_objects_v2.call_count == 3

    @patch("test_generator.ground_truth_loader.time.sleep")
    def test_slowdown_retries(self, mock_sleep):
        exc = _client_error("SlowDown")
        client = _make_s3_client(list_error=exc)
        with pytest.raises(S3AccessError):
            load_ground_truth("s3://bkt/data/", s3_client=client)
        assert client.list_objects_v2.call_count == 3

    def test_access_denied_raises_immediately(self):
        exc = _client_error("AccessDenied", "Access Denied")
        client = _make_s3_client(list_error=exc)
        with pytest.raises(S3AccessError) as exc_info:
            load_ground_truth("s3://bkt/data/", s3_client=client)
        assert exc_info.value.aws_error_code == "AccessDenied"
        # No retries for non-throttling errors.
        assert client.list_objects_v2.call_count == 1

    def test_no_such_bucket_raises(self):
        exc = _client_error("NoSuchBucket")
        client = _make_s3_client(list_error=exc)
        with pytest.raises(S3AccessError) as exc_info:
            load_ground_truth("s3://bkt/data/", s3_client=client)
        assert exc_info.value.aws_error_code == "NoSuchBucket"


# ===================================================================
# Lenient vs strict mode
# ===================================================================

class TestLenientStrictMode:
    def test_lenient_skips_malformed_records(self):
        bad_jsonl = b'not json\n{"prompt": "p", "expected": "e"}\n'
        objects = [{"Key": "data/f.jsonl", "Size": 100}]
        contents = {"data/f.jsonl": bad_jsonl}
        client = _make_s3_client(objects=objects, file_contents=contents)
        cases, diag = load_ground_truth("s3://bkt/data/", lenient=True, s3_client=client)
        assert len(cases) == 1
        assert len(diag.malformed_records) == 1

    def test_strict_raises_on_malformed(self):
        bad_jsonl = b'not json\n{"prompt": "p", "expected": "e"}\n'
        objects = [{"Key": "data/f.jsonl", "Size": 100}]
        contents = {"data/f.jsonl": bad_jsonl}
        client = _make_s3_client(objects=objects, file_contents=contents)
        # The JSONL parser raises ValidationError in strict mode.
        with pytest.raises(Exception):
            load_ground_truth("s3://bkt/data/", lenient=False, s3_client=client)

    def test_default_is_lenient(self):
        """load_ground_truth defaults to lenient=True."""
        bad_jsonl = b'not json\n{"prompt": "p", "expected": "e"}\n'
        objects = [{"Key": "data/f.jsonl", "Size": 100}]
        contents = {"data/f.jsonl": bad_jsonl}
        client = _make_s3_client(objects=objects, file_contents=contents)
        # Should not raise — lenient is the default.
        cases, diag = load_ground_truth("s3://bkt/data/", s3_client=client)
        assert len(cases) == 1


# ===================================================================
# Diagnostics aggregation
# ===================================================================

class TestDiagnosticsAggregation:
    def test_diagnostics_counts(self):
        objects = [
            {"Key": "data/a.jsonl", "Size": 50},
            {"Key": "data/b.csv", "Size": 60},
            {"Key": "data/c.txt", "Size": 70},
        ]
        jsonl_data = _jsonl_bytes(
            {"prompt": "p1", "expected": "e1"},
            {"prompt": "p2", "expected": "e2"},
        )
        csv_data = b"prompt,expected\nhello,world\n"
        contents = {
            "data/a.jsonl": jsonl_data,
            "data/b.csv": csv_data,
        }
        client = _make_s3_client(objects=objects, file_contents=contents)
        cases, diag = load_ground_truth("s3://bkt/data/", s3_client=client)
        assert diag.total_files_scanned == 3
        assert diag.files_successfully_parsed == 2
        assert diag.total_test_cases == 3
        assert len(diag.skipped_files) == 1  # c.txt

    def test_diagnostics_serializable(self):
        objects = [{"Key": "data/a.jsonl", "Size": 50}]
        contents = {"data/a.jsonl": _jsonl_bytes({"prompt": "p", "expected": "e"})}
        client = _make_s3_client(objects=objects, file_contents=contents)
        _, diag = load_ground_truth("s3://bkt/data/", s3_client=client)
        d = diag.to_dict()
        assert isinstance(d, dict)
        assert "total_test_cases" in d


# ===================================================================
# Multi-format dispatch
# ===================================================================

class TestMultiFormatDispatch:
    def test_dispatches_to_correct_parser(self):
        jsonl_data = _jsonl_bytes({"prompt": "j", "expected": "j"})
        json_data = json.dumps([{"prompt": "js", "expected": "js"}]).encode()
        csv_data = b"prompt,expected\nc,c\n"
        objects = [
            {"Key": "data/a.jsonl", "Size": 50},
            {"Key": "data/b.json", "Size": 60},
            {"Key": "data/c.csv", "Size": 40},
        ]
        contents = {
            "data/a.jsonl": jsonl_data,
            "data/b.json": json_data,
            "data/c.csv": csv_data,
        }
        client = _make_s3_client(objects=objects, file_contents=contents)
        cases, diag = load_ground_truth("s3://bkt/data/", s3_client=client)
        assert len(cases) == 3
        assert diag.files_successfully_parsed == 3


# ===================================================================
# Exponential backoff details (Req 1.5)
# ===================================================================

class TestExponentialBackoff:
    @patch("test_generator.ground_truth_loader.time.sleep")
    def test_backoff_delays_increase_exponentially(self, mock_sleep):
        exc = _client_error("Throttling")
        client = _make_s3_client(list_error=exc)
        with pytest.raises(S3AccessError):
            load_ground_truth("s3://bkt/data/", s3_client=client)
        # Backoff base is 1.0s: delays should be 1.0, 2.0, 4.0
        delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert delays == [1.0, 2.0, 4.0]

    @patch("test_generator.ground_truth_loader.time.sleep")
    def test_request_limit_exceeded_retries(self, mock_sleep):
        """RequestLimitExceeded is also a throttling error (Req 1.5)."""
        exc = _client_error("RequestLimitExceeded")
        client = _make_s3_client(list_error=exc)
        with pytest.raises(S3AccessError) as exc_info:
            load_ground_truth("s3://bkt/data/", s3_client=client)
        assert exc_info.value.aws_error_code == "Throttling"
        assert client.list_objects_v2.call_count == 3

    @patch("test_generator.ground_truth_loader.time.sleep")
    def test_throttling_succeeds_on_retry(self, mock_sleep):
        """If S3 stops throttling on a retry, loading succeeds."""
        exc = _client_error("Throttling")
        objects = [{"Key": "data/a.jsonl", "Size": 50}]
        contents = {"data/a.jsonl": _jsonl_bytes({"prompt": "p", "expected": "e"})}

        client = MagicMock()
        # First call throttles, second succeeds.
        client.list_objects_v2.side_effect = [
            exc,
            {"Contents": objects, "IsTruncated": False},
        ]

        def _get_object(Bucket, Key):
            body = MagicMock()
            body.read.return_value = contents[Key]
            return {"Body": body}
        client.get_object.side_effect = _get_object

        cases, diag = load_ground_truth("s3://bkt/data/", s3_client=client)
        assert len(cases) == 1
        assert client.list_objects_v2.call_count == 2


# ===================================================================
# S3AccessError attributes (Req 1.4)
# ===================================================================

class TestS3AccessErrorAttributes:
    def test_error_has_bucket_and_code(self):
        err = S3AccessError(bucket="my-bkt", aws_error_code="AccessDenied", message="nope")
        assert err.bucket == "my-bkt"
        assert err.aws_error_code == "AccessDenied"
        assert err.message == "nope"
        assert str(err) == "nope"


# ===================================================================
# Field mapping propagation (Req 2.3, 6.2)
# ===================================================================

class TestFieldMappingPropagation:
    def test_custom_field_mapping_resolves_aliases(self):
        """Custom FieldMapping aliases are used by parsers during loading."""
        mapping = FieldMapping(
            prompt_aliases=["question"],
            expected_aliases=["answer"],
        )
        jsonl_data = _jsonl_bytes({"question": "q1", "answer": "a1"})
        objects = [{"Key": "data/a.jsonl", "Size": 50}]
        contents = {"data/a.jsonl": jsonl_data}
        client = _make_s3_client(objects=objects, file_contents=contents)
        cases, diag = load_ground_truth(
            "s3://bkt/data/", field_mapping=mapping, s3_client=client
        )
        assert len(cases) == 1
        assert cases[0].prompt == "q1"
        assert cases[0].expected == "a1"

    def test_default_field_mapping_used_when_none(self):
        """When field_mapping is None, default FieldMapping is used."""
        jsonl_data = _jsonl_bytes({"input": "q", "output": "a"})
        objects = [{"Key": "data/a.jsonl", "Size": 50}]
        contents = {"data/a.jsonl": jsonl_data}
        client = _make_s3_client(objects=objects, file_contents=contents)
        cases, _ = load_ground_truth("s3://bkt/data/", field_mapping=None, s3_client=client)
        assert len(cases) == 1
        assert cases[0].prompt == "q"
        assert cases[0].expected == "a"


# ===================================================================
# Paginated S3 listing (Req 2.1)
# ===================================================================

class TestPaginatedListing:
    def test_handles_paginated_responses(self):
        """Loader follows ContinuationToken across multiple pages."""
        page1_objects = [{"Key": "data/a.jsonl", "Size": 50}]
        page2_objects = [{"Key": "data/b.jsonl", "Size": 60}]
        contents = {
            "data/a.jsonl": _jsonl_bytes({"prompt": "p1", "expected": "e1"}),
            "data/b.jsonl": _jsonl_bytes({"prompt": "p2", "expected": "e2"}),
        }

        client = MagicMock()
        client.list_objects_v2.side_effect = [
            {"Contents": page1_objects, "IsTruncated": True, "NextContinuationToken": "tok1"},
            {"Contents": page2_objects, "IsTruncated": False},
        ]

        def _get_object(Bucket, Key):
            body = MagicMock()
            body.read.return_value = contents[Key]
            return {"Body": body}
        client.get_object.side_effect = _get_object

        cases, diag = load_ground_truth("s3://bkt/data/", s3_client=client)
        assert len(cases) == 2
        assert diag.total_files_scanned == 2
        assert client.list_objects_v2.call_count == 2


# ===================================================================
# All-valid diagnostics (Req 7.3)
# ===================================================================

class TestAllValidDiagnostics:
    def test_clean_dataset_has_empty_diagnostic_lists(self):
        """When all files are valid, skipped_files and malformed_records are empty (Req 7.3)."""
        objects = [{"Key": "data/a.jsonl", "Size": 50}]
        contents = {"data/a.jsonl": _jsonl_bytes({"prompt": "p", "expected": "e"})}
        client = _make_s3_client(objects=objects, file_contents=contents)
        _, diag = load_ground_truth("s3://bkt/data/", s3_client=client)
        assert diag.skipped_files == []
        assert diag.malformed_records == []
