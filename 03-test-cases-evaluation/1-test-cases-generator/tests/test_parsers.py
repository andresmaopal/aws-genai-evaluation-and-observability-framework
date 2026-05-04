"""Unit tests for JSONL, JSON, and CSV parsers.

Covers requirements 3.1-3.7, 4.1-4.5, 5.1-5.6, 8.1, 8.2.
"""
from __future__ import annotations
import io
import json
import pytest
from test_generator.models import FieldMapping
from test_generator.parsers.jsonl_parser import JsonlParser, ValidationError
from test_generator.parsers.json_parser import JsonParser
from test_generator.parsers.csv_parser import CsvParser


def _stream(text: str) -> io.BytesIO:
    return io.BytesIO(text.encode("utf-8"))


def _mapping() -> FieldMapping:
    return FieldMapping()


class TestJsonlParser:
    parser = JsonlParser()

    def test_valid_lines(self):
        data = '{"prompt": "hello", "expected": "world"}\n{"prompt": "foo", "expected": "bar"}\n'
        cases, diags = self.parser.parse(_stream(data), "f.jsonl", _mapping(), True)
        assert len(cases) == 2
        assert cases[0].prompt == "hello"
        assert cases[1].expected == "bar"
        assert diags == []

    def test_empty_lines_skipped(self):
        data = '\n{"prompt": "a", "expected": "b"}\n\n'
        cases, diags = self.parser.parse(_stream(data), "f.jsonl", _mapping(), True)
        assert len(cases) == 1
        assert diags == []

    def test_alias_mapping(self):
        data = '{"question": "hi", "answer": "bye"}\n'
        cases, _ = self.parser.parse(_stream(data), "f.jsonl", _mapping(), True)
        assert cases[0].prompt == "hi"
        assert cases[0].expected == "bye"

    def test_extra_fields_to_metadata(self):
        data = '{"prompt": "q", "expected": "a", "custom": "v"}\n'
        cases, _ = self.parser.parse(_stream(data), "f.jsonl", _mapping(), True)
        assert cases[0].metadata == {"custom": "v"}

    def test_expected_as_list(self):
        data = '{"prompt": "q", "expected": ["a1", "a2"]}\n'
        cases, _ = self.parser.parse(_stream(data), "f.jsonl", _mapping(), True)
        assert cases[0].expected == ["a1", "a2"]

    def test_invalid_json_lenient(self):
        data = '{"prompt": "ok", "expected": "ok"}\nNOT JSON\n'
        cases, diags = self.parser.parse(_stream(data), "f.jsonl", _mapping(), True)
        assert len(cases) == 1
        assert len(diags) == 1
        assert diags[0].line_or_row == 2
        assert "Invalid JSON" in diags[0].reason

    def test_invalid_json_strict(self):
        with pytest.raises(ValidationError) as exc:
            self.parser.parse(_stream("NOT JSON\n"), "f.jsonl", _mapping(), False)
        assert exc.value.file_key == "f.jsonl"
        assert exc.value.line_number == 1

    def test_non_object_line(self):
        cases, diags = self.parser.parse(_stream('["a"]\n'), "f.jsonl", _mapping(), True)
        assert len(cases) == 0
        assert "not a JSON object" in diags[0].reason

    def test_missing_prompt_lenient(self):
        cases, diags = self.parser.parse(_stream('{"expected": "a"}\n'), "f.jsonl", _mapping(), True)
        assert len(cases) == 0
        assert "prompt" in diags[0].reason

    def test_missing_expected_lenient(self):
        cases, diags = self.parser.parse(_stream('{"prompt": "q"}\n'), "f.jsonl", _mapping(), True)
        assert len(cases) == 0
        assert "expected" in diags[0].reason

    def test_missing_prompt_strict(self):
        with pytest.raises(ValidationError):
            self.parser.parse(_stream('{"expected": "a"}\n'), "f.jsonl", _mapping(), False)

    def test_missing_expected_strict(self):
        with pytest.raises(ValidationError):
            self.parser.parse(_stream('{"prompt": "q"}\n'), "f.jsonl", _mapping(), False)

    def test_lenient_accumulates_errors(self):
        data = 'BAD\n{"expected":"x"}\n{"prompt":"ok","expected":"ok"}\n{"prompt":"y"}\n'
        cases, diags = self.parser.parse(_stream(data), "f.jsonl", _mapping(), True)
        assert len(cases) == 1
        assert len(diags) == 3

    def test_strict_stops_on_first(self):
        data = '{"prompt":"ok","expected":"ok"}\nBAD\n'
        with pytest.raises(ValidationError) as exc:
            self.parser.parse(_stream(data), "f.jsonl", _mapping(), False)
        assert exc.value.line_number == 2


class TestJsonParser:
    parser = JsonParser()

    def test_top_level_array(self):
        data = json.dumps([{"prompt": "p1", "expected": "e1"}, {"prompt": "p2", "expected": "e2"}])
        cases, diags = self.parser.parse(_stream(data), "f.json", _mapping(), True)
        assert len(cases) == 2
        assert diags == []

    def test_empty_array(self):
        cases, diags = self.parser.parse(_stream("[]"), "f.json", _mapping(), True)
        assert len(cases) == 0
        assert diags == []

    def test_wrapper_data(self):
        d = json.dumps({"data": [{"prompt": "p", "expected": "e"}]})
        cases, diags = self.parser.parse(_stream(d), "f.json", _mapping(), True)
        assert len(cases) == 1
        assert diags == []

    def test_wrapper_records(self):
        d = json.dumps({"records": [{"prompt": "p", "expected": "e"}]})
        cases, _ = self.parser.parse(_stream(d), "f.json", _mapping(), True)
        assert len(cases) == 1

    def test_wrapper_samples(self):
        d = json.dumps({"samples": [{"prompt": "p", "expected": "e"}]})
        cases, _ = self.parser.parse(_stream(d), "f.json", _mapping(), True)
        assert len(cases) == 1

    def test_wrapper_test_cases(self):
        d = json.dumps({"test_cases": [{"prompt": "p", "expected": "e"}]})
        cases, _ = self.parser.parse(_stream(d), "f.json", _mapping(), True)
        assert len(cases) == 1

    def test_invalid_json_lenient(self):
        cases, diags = self.parser.parse(_stream("NOT JSON"), "f.json", _mapping(), True)
        assert len(diags) == 1
        assert "Invalid JSON" in diags[0].reason

    def test_invalid_json_strict(self):
        with pytest.raises(ValidationError):
            self.parser.parse(_stream("NOT JSON"), "f.json", _mapping(), False)

    def test_unsupported_schema_lenient(self):
        d = json.dumps({"unknown": [1]})
        cases, diags = self.parser.parse(_stream(d), "f.json", _mapping(), True)
        assert "Unsupported JSON schema" in diags[0].reason

    def test_unsupported_schema_strict(self):
        with pytest.raises(ValidationError):
            self.parser.parse(_stream(json.dumps({"unknown": [1]})), "f.json", _mapping(), False)

    def test_scalar_unsupported(self):
        cases, diags = self.parser.parse(_stream(json.dumps("str")), "f.json", _mapping(), True)
        assert "Unsupported JSON schema" in diags[0].reason

    def test_missing_fields_in_records(self):
        d = json.dumps([{"prompt": "p"}, {"expected": "e"}])
        cases, diags = self.parser.parse(_stream(d), "f.json", _mapping(), True)
        assert len(cases) == 0
        assert len(diags) == 2

    def test_non_dict_record_lenient(self):
        d = json.dumps(["str", {"prompt": "p", "expected": "e"}])
        cases, diags = self.parser.parse(_stream(d), "f.json", _mapping(), True)
        assert len(cases) == 1
        assert "not a JSON object" in diags[0].reason

    def test_non_dict_record_strict(self):
        with pytest.raises(ValidationError):
            self.parser.parse(_stream(json.dumps(["str"])), "f.json", _mapping(), False)

    def test_alias_mapping(self):
        d = json.dumps([{"question": "q", "answer": "a"}])
        cases, _ = self.parser.parse(_stream(d), "f.json", _mapping(), True)
        assert cases[0].prompt == "q"
        assert cases[0].expected == "a"

    def test_lenient_accumulates(self):
        d = json.dumps(["x", {"prompt": "p"}, {"expected": "e"}, {"prompt": "ok", "expected": "ok"}])
        cases, diags = self.parser.parse(_stream(d), "f.json", _mapping(), True)
        assert len(cases) == 1
        assert len(diags) == 3

    def test_strict_stops_first(self):
        d = json.dumps([{"prompt": "ok", "expected": "ok"}, {"prompt": "no exp"}])
        with pytest.raises(ValidationError) as exc:
            self.parser.parse(_stream(d), "f.json", _mapping(), False)
        assert exc.value.line_number == 2


class TestCsvParser:
    parser = CsvParser()

    def test_valid_csv(self):
        cases, diags = self.parser.parse(_stream("prompt,expected\nhello,world\nfoo,bar\n"), "f.csv", _mapping(), True)
        assert len(cases) == 2
        assert cases[0].prompt == "hello"
        assert diags == []

    def test_alias_columns(self):
        cases, _ = self.parser.parse(_stream("question,answer\nhello,world\n"), "f.csv", _mapping(), True)
        assert cases[0].prompt == "hello"
        assert cases[0].expected == "world"

    def test_quoted_fields_rfc4180(self):
        data = 'prompt,expected\n"hello, world","with ""quotes"""\n'
        cases, _ = self.parser.parse(_stream(data), "f.csv", _mapping(), True)
        assert cases[0].prompt == "hello, world"
        assert cases[0].expected == 'with "quotes"'

    def test_extra_columns_metadata(self):
        cases, _ = self.parser.parse(_stream("prompt,expected,x\na,b,c\n"), "f.csv", _mapping(), True)
        assert cases[0].metadata == {"x": "c"}

    def test_empty_file_lenient(self):
        cases, diags = self.parser.parse(_stream(""), "f.csv", _mapping(), True)
        assert len(diags) == 1
        assert "empty" in diags[0].reason.lower()

    def test_empty_file_strict(self):
        with pytest.raises(ValidationError):
            self.parser.parse(_stream(""), "f.csv", _mapping(), False)

    def test_whitespace_only(self):
        cases, diags = self.parser.parse(_stream("  \n \n"), "f.csv", _mapping(), True)
        assert len(cases) == 0
        assert len(diags) == 1

    def test_missing_prompt_col(self):
        cases, diags = self.parser.parse(_stream("expected\nworld\n"), "f.csv", _mapping(), True)
        assert len(cases) == 0
        assert "prompt" in diags[0].reason

    def test_missing_expected_col(self):
        cases, diags = self.parser.parse(_stream("prompt\nhello\n"), "f.csv", _mapping(), True)
        assert len(cases) == 0
        assert "expected" in diags[0].reason

    def test_empty_prompt_value(self):
        cases, diags = self.parser.parse(_stream("prompt,expected\n,world\n"), "f.csv", _mapping(), True)
        assert len(cases) == 0
        assert "prompt" in diags[0].reason

    def test_empty_expected_value(self):
        cases, diags = self.parser.parse(_stream("prompt,expected\nhello,\n"), "f.csv", _mapping(), True)
        assert len(cases) == 0
        assert "expected" in diags[0].reason

    def test_missing_prompt_strict(self):
        with pytest.raises(ValidationError):
            self.parser.parse(_stream("expected\nworld\n"), "f.csv", _mapping(), False)

    def test_missing_expected_strict(self):
        with pytest.raises(ValidationError):
            self.parser.parse(_stream("prompt\nhello\n"), "f.csv", _mapping(), False)

    def test_lenient_accumulates(self):
        cases, diags = self.parser.parse(_stream("prompt,expected\n,w\nh,\ngood,ok\n"), "f.csv", _mapping(), True)
        assert len(cases) == 1
        assert len(diags) == 2

    def test_strict_stops_first(self):
        with pytest.raises(ValidationError) as exc:
            self.parser.parse(_stream("prompt,expected\ngood,ok\n,bad\n"), "f.csv", _mapping(), False)
        assert exc.value.line_number == 3

    def test_diagnostic_row_number(self):
        _, diags = self.parser.parse(_stream("prompt,expected\ngood,ok\n,bad\n"), "f.csv", _mapping(), True)
        assert diags[0].line_or_row == 3
        assert diags[0].file_key == "f.csv"


class TestParserRegistry:
    def test_has_all_extensions(self):
        from test_generator.parsers import PARSER_REGISTRY
        assert set(PARSER_REGISTRY.keys()) == {".jsonl", ".json", ".csv"}

    def test_correct_types(self):
        from test_generator.parsers import PARSER_REGISTRY
        assert isinstance(PARSER_REGISTRY[".jsonl"], JsonlParser)
        assert isinstance(PARSER_REGISTRY[".json"], JsonParser)
        assert isinstance(PARSER_REGISTRY[".csv"], CsvParser)
