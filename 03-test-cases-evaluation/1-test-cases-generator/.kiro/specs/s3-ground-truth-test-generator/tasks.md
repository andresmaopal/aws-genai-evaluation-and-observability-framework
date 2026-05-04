# Implementation Plan: S3 Ground Truth Test Generator

## Overview

Refactor the monolithic `utils.py` into a modular `test_generator/` Python package with S3-based ground truth loading, dual-category (functional + boundary) test generation, externalized YAML configuration, and both CLI and notebook entry points. Tasks are ordered for incremental development: data models → parsers → loader → config → prompt builder → generator orchestration → CLI → notebook UI → wiring and final validation.

## Tasks

- [-] 1. Create package structure and data models
  - [x] 1.1 Create `test_generator/` package skeleton with `__init__.py`
    - Create `test_generator/__init__.py` with package-level exports
    - Create `test_generator/parsers/__init__.py` with empty parser registry placeholder
    - _Requirements: Design package structure_

  - [x] 1.2 Implement `test_generator/models.py` with all dataclasses
    - Implement `TestCase` dataclass with fields: `id`, `prompt`, `expected`, `contexts`, `metadata`, `agent_spec`
    - Implement `TestCase.to_dict()` returning a JSON-serializable dictionary of all fields
    - Implement `TestCase.from_dict(d)` class method that raises `ValueError` when `prompt` or `expected` is missing
    - Implement `DiagnosticRecord` dataclass with fields: `file_key`, `line_or_row`, `reason`, `severity`
    - Implement `Diagnostics` dataclass with fields: `skipped_files`, `malformed_records`, `total_files_scanned`, `files_successfully_parsed`, `total_test_cases`, and a `to_dict()` method
    - Implement `FieldMapping` dataclass with alias lists for `prompt`, `expected`, `id`, `contexts` and a `resolve(record)` method that maps source keys to canonical TestCase field names
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 7.1, 7.2, 7.3, 7.4, 20.1, 20.2, 20.4, 20.5_

  - [x] 1.3 Write property test for TestCase round-trip serialization
    - **Property 1: Round-trip consistency** — For all valid TestCase objects, `TestCase.from_dict(tc.to_dict())` produces a TestCase equal to the original
    - **Validates: Requirements 6.5, 20.3**

  - [x] 1.4 Write unit tests for models
    - Test `TestCase.from_dict` raises `ValueError` when `prompt` is missing
    - Test `TestCase.from_dict` raises `ValueError` when `expected` is missing
    - Test `FieldMapping.resolve` correctly maps aliased keys to canonical names
    - Test `FieldMapping.resolve` places unrecognized fields into `metadata`
    - Test `Diagnostics.to_dict()` produces valid JSON-serializable output
    - _Requirements: 6.2, 6.3, 7.4, 20.4, 20.5_

- [x] 2. Implement file parsers
  - [x] 2.1 Implement parser protocol and registry in `test_generator/parsers/__init__.py`
    - Define `Parser` protocol with `parse(stream, file_key, field_mapping, lenient) -> tuple[list[TestCase], list[DiagnosticRecord]]`
    - Create `PARSER_REGISTRY` dict mapping `.jsonl`, `.json`, `.csv` to parser instances
    - _Requirements: 2.3 (whitelist extensions)_

  - [x] 2.2 Implement `test_generator/parsers/jsonl_parser.py`
    - Parse each non-empty line as independent JSON object
    - Record invalid JSON lines in diagnostics with file key, line number, and error message
    - Record lines missing `prompt` (and all Field_Mapping alternatives) as malformed
    - Record lines missing `expected` (and all Field_Mapping alternatives) as malformed
    - Normalize valid objects into TestCase using FieldMapping
    - In lenient mode, skip malformed lines and continue; in strict mode, raise `ValidationError` with file key and line number
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [x] 2.3 Implement `test_generator/parsers/json_parser.py`
    - Handle top-level JSON arrays: treat each element as a candidate TestCase record
    - Handle top-level JSON objects with recognized wrapper keys (`data`, `records`, `samples`, `test_cases`): extract the array value
    - Record invalid JSON files in diagnostics
    - Record files with neither a top-level array nor a recognized wrapper key as unsupported schema
    - Validate each extracted record for required fields using same rules as JSONL
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 2.4 Implement `test_generator/parsers/csv_parser.py`
    - Require a header row as the first non-empty line; record files without headers as malformed
    - Map CSV column names to TestCase fields using FieldMapping
    - Record rows missing `prompt` (and alternatives) with row number and file key
    - Record rows missing `expected` (and alternatives) with row number and file key
    - Handle quoted fields and embedded commas per RFC 4180
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [x] 2.5 Write unit tests for parsers
    - Test JSONL parser with valid lines, invalid JSON lines, and missing required fields
    - Test JSON parser with top-level array, wrapper-key objects, invalid JSON, and unsupported schema
    - Test CSV parser with valid headers, missing headers, missing required columns, and quoted fields
    - Test lenient vs strict mode behavior across all parsers
    - _Requirements: 3.1–3.7, 4.1–4.5, 5.1–5.6, 8.1, 8.2_

- [x] 3. Implement S3 ground truth loader
  - [x] 3.1 Implement `test_generator/ground_truth_loader.py`
    - Implement `parse_s3_uri(uri)` that parses `s3://bucket/prefix` into `(bucket, prefix)` and raises `ValueError` on invalid format; treat missing trailing slash as prefix for listing
    - Implement `S3AccessError` exception with `bucket`, `aws_error_code`, and `message` attributes
    - Implement `load_ground_truth(s3_uri, field_mapping, recursive, lenient, s3_client)` that:
      - Lists objects under prefix (recursive or non-recursive based on parameter)
      - Filters by whitelist extensions (`.jsonl`, `.json`, `.csv`), skips non-whitelisted files with diagnostic warning
      - Skips zero-byte objects with diagnostic record
      - Raises `FileNotFoundError` when no whitelisted files found
      - Dispatches each file to the appropriate parser from `PARSER_REGISTRY`
      - Aggregates TestCase objects and DiagnosticRecord entries into a Diagnostics object
      - Retries with exponential backoff (up to 3 attempts) on S3 throttling errors, then raises `S3AccessError`
      - Raises `S3AccessError` on missing bucket or permission errors
    - Add INFO-level logging for S3 URI, file counts, whitelist matches, and total TestCase count
    - Add WARNING-level logging for skipped files, malformed records, and retry attempts
    - Default to lenient mode when mode parameter is not specified
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 6.1, 6.2, 6.3, 6.4, 7.1, 7.2, 7.3, 8.1, 8.2, 8.3, 19.1, 19.2_

  - [x] 3.2 Write unit tests for ground truth loader
    - Test `parse_s3_uri` with valid URIs, missing prefix, and invalid formats
    - Test file discovery with recursive and non-recursive modes (mock S3 client)
    - Test whitelist filtering and zero-byte file skipping
    - Test `FileNotFoundError` when no whitelisted files found
    - Test exponential backoff retry on throttling errors
    - Test `S3AccessError` on permission/bucket errors
    - Test lenient vs strict mode propagation to parsers
    - _Requirements: 1.1–1.5, 2.1–2.6, 8.1–8.3_

- [x] 4. Checkpoint — Ensure data layer tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement configuration management
  - [x] 5.1 Implement `test_generator/config.py`
    - Implement `Config` dataclass with all fields: `s3_uri`, `field_mapping`, `recursive`, `lenient`, `model_name`, `aws_region`, `functional_ratio`, `num_cases`, `num_questions_per_case`, `output_format`, `languages`, `model_list_path`, `prompt_template_path`, `log_level`
    - Implement `load_config(config_path, overrides)` that loads from YAML file (default `config.yaml`), applies runtime overrides, and falls back to built-in defaults when no file found
    - Log a warning and ignore unrecognized keys in the config file
    - Log an ERROR on config file parse errors
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 14.1, 14.2, 14.3, 14.5, 19.4_

  - [x] 5.2 Write unit tests for config loading
    - Test loading from valid YAML file
    - Test fallback to defaults when no file exists
    - Test runtime overrides take precedence over file values
    - Test warning on unrecognized keys
    - _Requirements: 13.1–13.5_

- [ ] 6. Implement prompt builder
  - [ ] 6.1 Implement `test_generator/prompt_builder.py`
    - Implement `build_prompt(test_cases, app_description, system_prompt, business_metrics, functional_count, boundary_count, num_questions_per_case, language)` that constructs an XML-tagged prompt with sections: `<instructions>`, `<chain_of_thought>`, `<ground_truth>`, `<application_context>`, `<output_format>`, `<examples>`
    - Include chain-of-thought instruction for scenario diversity reasoning
    - Include one few-shot functional example and one few-shot boundary example
    - Specify exact YAML output schema with `scenario_name`, `category`, and `turns` fields
    - Instruct model to output only valid YAML with no surrounding prose
    - Serialize ground truth TestCase objects as YAML list in `<ground_truth>` section
    - Support loading prompt template from external file when `prompt_template_path` is configured
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 10.1, 10.2, 10.3, 10.4, 10.5, 12.1, 12.2, 12.3, 12.4, 12.5, 14.3_

  - [x] 6.2 Write unit tests for prompt builder
    - Test that output contains all required XML sections
    - Test that functional and boundary counts are embedded correctly
    - Test that ground truth data is serialized into the prompt
    - Test that few-shot examples for both categories are present
    - _Requirements: 9.5, 10.3, 12.1–12.4_

- [x] 7. Implement generator orchestrator
  - [x] 7.1 Implement `test_generator/generator.py`
    - Implement `GenerationResult` dataclass with fields: `yaml_text`, `is_valid_yaml`, `test_cases_generated`, `functional_count`, `boundary_count`, `model_used`, `diagnostics`, `warnings`
    - Implement `TestGeneratorOrchestrator` class with `__init__(config)` and `generate(app_description, system_prompt, business_metrics, s3_uri, ground_truth)` method
    - Compute `functional_count = round(total_cases * ratio / 100)` and `boundary_count = total_cases - functional_count`
    - Handle ratio edge cases: 100 → only functional, 0 → only boundary
    - Load model registry from `model_list.json` (configurable path), deduplicate by `(model_id, region_name)` keeping shorter key name, validate required fields (`model_id`, `region_name`, `temperature`, `inference_type`), apply default `max_tokens=4096` when missing, log warning and exclude models with missing required fields
    - Invoke Bedrock model using the Converse API; handle Claude vs non-Claude request formats
    - Validate model output is parseable as YAML; if invalid, retry once; if still invalid, return raw text with warning
    - Add INFO-level logging for model name, case count, functional/boundary split, prompt token estimate
    - Add ERROR-level logging for model invocation failures and YAML parse failures
    - Configure Python `logging` module with configurable log level (default INFO)
    - _Requirements: 11.2, 11.3, 11.4, 11.6, 17.1, 17.2, 17.3, 17.4, 18.1, 18.2, 18.3, 19.3, 19.4, 19.5_

  - [x] 7.2 Write unit tests for generator orchestrator
    - Test functional/boundary count calculation for various ratios (0, 50, 70, 100)
    - Test model registry deduplication and validation logic
    - Test YAML validation and retry behavior (mock Bedrock client)
    - Test `GenerationResult` fields are populated correctly
    - _Requirements: 11.2–11.4, 17.4, 18.1–18.3_

- [x] 8. Checkpoint — Ensure core pipeline tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement CLI entry point
  - [x] 9.1 Implement `test_generator/__main__.py`
    - Use `argparse` to accept: `--s3-uri`, `--config`, `--model`, `--num-cases`, `--num-questions`, `--functional-ratio` (0–100), `--output`, `--lenient`/`--strict`, `--app-description`
    - Load config from `--config` path (or default), apply CLI args as overrides
    - Validate that `app_description` is provided (from CLI or config); exit with non-zero code and message if missing
    - Call `TestGeneratorOrchestrator.generate()` with resolved parameters
    - Write YAML output to `--output` file path when provided, or print to stdout
    - Group functional test cases before boundary test cases; separate YAML documents with `---`
    - Return exit code 0 on success, non-zero on failure
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 11.5, 17.2, 17.3_

  - [x] 9.2 Write unit tests for CLI entry point
    - Test argument parsing for all supported flags
    - Test missing `app_description` exits with non-zero code
    - Test output to file vs stdout
    - _Requirements: 15.1–15.6_

- [x] 10. Implement modernized notebook UI
  - [x] 10.1 Implement `test_generator/notebook_ui.py`
    - Implement `NotebookUI` class with `__init__(config)` and `display()` method
    - Replace PDF load button with a text input widget for S3 URI
    - Add Category Ratio integer slider (0–100, default 70) labeled "Functional / Boundary ratio" between questions slider and Generate button
    - Retain existing widgets: app description, system prompt, business metrics, language dropdown (populated from config `languages`), model dropdown, num cases slider, num questions slider
    - Display diagnostics summary (files scanned, files parsed, records loaded, warnings) in output area after ground truth loading
    - Show progress indicator with model name, case count, functional/boundary split, and ground truth record count before generation begins
    - Read language list from config instead of hardcoded list
    - _Requirements: 11.1, 14.1, 16.1, 16.2, 16.3, 16.4, 16.5_

- [x] 11. Wire everything together and update package exports
  - [x] 11.1 Update `test_generator/__init__.py` with public API exports
    - Export `TestCase`, `Diagnostics`, `FieldMapping`, `Config`, `TestGeneratorOrchestrator`, `NotebookUI`, `load_config`, `load_ground_truth`
    - _Requirements: Design package structure_

  - [x] 11.2 Update `test_case_generator.ipynb` to use new package
    - Replace `from utils import TestCaseGenerator` with `from test_generator import NotebookUI`
    - Instantiate `NotebookUI` with optional config and call `display()`
    - _Requirements: 16.4_

  - [x] 11.3 Create a default `config.yaml` example file
    - Include all supported keys with commented defaults as a reference for users
    - _Requirements: 13.1, 13.2_

- [x] 12. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation after the data layer and core pipeline
- Property tests validate the TestCase round-trip serialization invariant
- The S3 client is injectable in `load_ground_truth` to enable unit testing with mocks
- The implementation language is Python, matching the existing codebase and design document
