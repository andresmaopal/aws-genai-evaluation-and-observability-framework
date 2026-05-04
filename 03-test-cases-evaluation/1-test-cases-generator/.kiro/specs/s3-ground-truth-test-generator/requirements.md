# Requirements Document

## Introduction

This feature transforms the existing Test Case Generator tool from a local-PDF-only, notebook-bound prototype into a production-ready, reusable test case generation platform for AWS customers building agentic AI applications. The three pillars of this transformation are:

1. **S3-Based Ground Truth Loading** — Replace local PDF ingestion with a robust S3 dataset loader that supports JSONL, JSON, and CSV ground truth files, with validation, field mapping, and diagnostics.
2. **Dual-Category Test Generation** — Optimize the generation prompt for frontier models to produce both functional (grounded, realistic) and boundary (adversarial but valid) test cases from ground truth data, with a configurable ratio.
3. **Usability and Reusability Improvements** — Parameterize hardcoded values, externalize configuration, simplify the notebook UI, and add an optional CLI entry point so any AWS customer can adopt the tool for their own agentic applications.

## Glossary

- **Ground_Truth_Loader**: The module responsible for connecting to S3, scanning for whitelisted file types, validating file structure, and normalizing samples into TestCase objects.
- **TestCase**: The common internal data object representing a single ground truth sample with fields: id, prompt, expected, contexts, metadata, agent_spec.
- **Field_Mapping**: A user-supplied dictionary that maps canonical TestCase field names to alternative column/key names found in the source files.
- **Diagnostics**: A structured report object that records skipped files, malformed lines/rows, parse errors, and summary counts produced during ground truth loading.
- **Test_Generator**: The core orchestration class (currently `TestCaseGenerator`) that accepts user inputs, loads ground truth, constructs prompts, invokes a Bedrock model, and returns generated test cases.
- **Generation_Prompt**: The system/user prompt template sent to the Bedrock model to produce test cases from ground truth data.
- **Functional_Test**: A generated test case that is realistic, grounded in ground truth data, and representative of typical end-user interactions.
- **Boundary_Test**: A generated test case that exercises edge conditions, unexpected phrasings, unusual-but-valid inputs, or atypical user behaviors — distinct from red-teaming or security attacks.
- **Category_Ratio**: The user-configurable percentage split between Functional_Tests and Boundary_Tests (e.g., 70/30).
- **Config_File**: An external YAML or JSON file that holds all parameterized settings (S3 URI, model ID, field mapping, category ratio, etc.) so users do not need to edit code.
- **CLI_Entry_Point**: An optional command-line interface that exposes the same generation workflow available in the notebook, suitable for scripting and CI/CD pipelines.
- **Notebook_UI**: The ipywidgets-based interactive interface rendered inside a Jupyter notebook.
- **Bedrock_Client**: The boto3 client used to invoke foundation models via Amazon Bedrock.
- **S3_URI**: A string in the format `s3://bucket-name/optional-prefix/` that identifies a location in Amazon S3.
- **Whitelist**: The set of allowed ground truth file extensions: `.jsonl`, `.json`, `.csv`.

## Requirements

### Requirement 1: S3 URI Parsing and Connection

**User Story:** As a developer, I want to provide an S3 URI so that the Ground_Truth_Loader can locate my ground truth dataset without requiring local file copies.

#### Acceptance Criteria

1. WHEN a valid S3_URI in the format `s3://bucket/prefix` is provided, THE Ground_Truth_Loader SHALL parse the URI into a bucket name and prefix.
2. WHEN the S3_URI omits a trailing slash on the prefix, THE Ground_Truth_Loader SHALL treat the value as a prefix for listing operations.
3. IF the S3_URI does not match the pattern `s3://<bucket>/<prefix>`, THEN THE Ground_Truth_Loader SHALL raise a ValueError with a message identifying the expected format.
4. IF the S3 bucket does not exist or the caller lacks s3:ListBucket permission, THEN THE Ground_Truth_Loader SHALL raise an S3AccessError that includes the bucket name and the underlying AWS error code.
5. IF S3 returns a throttling error during listing, THEN THE Ground_Truth_Loader SHALL retry with exponential backoff up to 3 attempts before raising an S3AccessError.

---

### Requirement 2: Recursive File Discovery and Whitelisting

**User Story:** As a developer, I want the loader to scan my S3 prefix recursively and only pick up supported file types so that unsupported formats are safely ignored.

#### Acceptance Criteria

1. WHEN the `recursive` parameter is True, THE Ground_Truth_Loader SHALL list all objects under the given prefix, including objects in nested sub-prefixes.
2. WHEN the `recursive` parameter is False, THE Ground_Truth_Loader SHALL list only objects directly under the given prefix (no sub-prefix traversal).
3. THE Ground_Truth_Loader SHALL accept only files with extensions in the Whitelist (`.jsonl`, `.json`, `.csv`).
4. WHEN a file with an extension outside the Whitelist is encountered, THE Ground_Truth_Loader SHALL skip the file and record a warning in the Diagnostics object that includes the file key and its extension.
5. WHEN no whitelisted files are found under the given prefix, THE Ground_Truth_Loader SHALL raise a FileNotFoundError with a message stating no supported ground truth files were found.
6. THE Ground_Truth_Loader SHALL ignore S3 objects with a size of zero bytes and record each in the Diagnostics object.

---

### Requirement 3: JSONL File Validation and Parsing

**User Story:** As a developer, I want JSONL ground truth files parsed line-by-line so that each valid line becomes a TestCase and malformed lines are reported.

#### Acceptance Criteria

1. WHEN a `.jsonl` file is loaded, THE Ground_Truth_Loader SHALL parse each non-empty line as an independent JSON object.
2. WHEN a line is not valid JSON, THE Ground_Truth_Loader SHALL record the file key, line number, and error message in the Diagnostics object.
3. WHEN a JSON object lacks both a `prompt` field and all Field_Mapping alternatives for `prompt`, THE Ground_Truth_Loader SHALL record the line as malformed in the Diagnostics object.
4. WHEN a JSON object lacks both an `expected` field and all Field_Mapping alternatives for `expected`, THE Ground_Truth_Loader SHALL record the line as malformed in the Diagnostics object.
5. WHEN a valid JSON object contains recognized fields, THE Ground_Truth_Loader SHALL normalize the object into a TestCase using the Field_Mapping.
6. IF the `lenient` mode is enabled and a line is malformed, THEN THE Ground_Truth_Loader SHALL skip the line and continue processing subsequent lines.
7. IF the `lenient` mode is disabled and a line is malformed, THEN THE Ground_Truth_Loader SHALL raise a ValidationError that includes the file key and line number.

---

### Requirement 4: JSON File Validation and Parsing

**User Story:** As a developer, I want JSON files containing arrays of objects or recognized wrapper schemas parsed into TestCase objects so that I can use common dataset export formats.

#### Acceptance Criteria

1. WHEN a `.json` file contains a top-level JSON array, THE Ground_Truth_Loader SHALL treat each element as a candidate TestCase record.
2. WHEN a `.json` file contains a top-level JSON object with a recognized key (e.g., `"data"`, `"records"`, `"samples"`, `"test_cases"`), THE Ground_Truth_Loader SHALL extract the array value from that key.
3. IF a `.json` file is not valid JSON, THEN THE Ground_Truth_Loader SHALL record the file key and parse error in the Diagnostics object.
4. IF a `.json` file contains neither a top-level array nor a recognized wrapper key, THEN THE Ground_Truth_Loader SHALL record the file as unsupported schema in the Diagnostics object.
5. THE Ground_Truth_Loader SHALL validate each extracted record for required fields (`prompt` and `expected` or their Field_Mapping alternatives) using the same rules as JSONL parsing.

---

### Requirement 5: CSV File Validation and Parsing

**User Story:** As a developer, I want CSV ground truth files parsed using header-based column mapping so that I can use spreadsheet exports as ground truth.

#### Acceptance Criteria

1. WHEN a `.csv` file is loaded, THE Ground_Truth_Loader SHALL require a header row as the first non-empty line.
2. IF a `.csv` file has no header row or is empty, THEN THE Ground_Truth_Loader SHALL record the file as malformed in the Diagnostics object.
3. THE Ground_Truth_Loader SHALL map CSV column names to TestCase fields using the Field_Mapping dictionary.
4. WHEN a CSV row lacks values for both the `prompt` column and all Field_Mapping alternatives for `prompt`, THE Ground_Truth_Loader SHALL record the row number and file key in the Diagnostics object.
5. WHEN a CSV row lacks values for both the `expected` column and all Field_Mapping alternatives for `expected`, THE Ground_Truth_Loader SHALL record the row number and file key in the Diagnostics object.
6. THE Ground_Truth_Loader SHALL handle quoted fields and embedded commas according to RFC 4180.

---

### Requirement 6: TestCase Normalization

**User Story:** As a developer, I want all parsed records normalized into a uniform TestCase schema so that downstream prompt construction does not depend on the source file format.

#### Acceptance Criteria

1. THE Ground_Truth_Loader SHALL produce TestCase objects with the following fields: `id` (string or None), `prompt` (string), `expected` (string or list of strings), `contexts` (list of strings, default empty list), `metadata` (dict, default empty dict), `agent_spec` (dict, default empty dict).
2. WHEN a source record contains a field matching a Field_Mapping alias, THE Ground_Truth_Loader SHALL map the value to the corresponding canonical TestCase field.
3. WHEN a source record contains fields not recognized by the Field_Mapping or canonical names, THE Ground_Truth_Loader SHALL place those fields in the `metadata` dictionary of the TestCase.
4. WHEN the `expected` field value is a single string, THE Ground_Truth_Loader SHALL store the value as-is (string). WHEN the value is a list, THE Ground_Truth_Loader SHALL store the value as a list of strings.
5. FOR ALL valid source records, parsing into a TestCase and then serializing the TestCase back to a dictionary SHALL preserve the `prompt` and `expected` values without loss (round-trip property).

---

### Requirement 7: Diagnostics Reporting

**User Story:** As a developer, I want a structured diagnostics report after loading so that I can identify and fix problems in my ground truth dataset.

#### Acceptance Criteria

1. THE Ground_Truth_Loader SHALL return a Diagnostics object alongside the list of TestCase objects.
2. THE Diagnostics object SHALL contain: a list of skipped files (with file key and reason), a list of malformed records (with file key, line/row number, and error description), a count of total files scanned, a count of files successfully parsed, and a count of total TestCase objects produced.
3. WHEN all files are valid and all records parse successfully, THE Diagnostics object SHALL have empty skipped-files and malformed-records lists.
4. THE Diagnostics object SHALL be serializable to JSON for logging and inspection.

---

### Requirement 8: Fail-Fast vs Lenient Mode

**User Story:** As a developer, I want to choose between strict validation that stops on the first error and lenient validation that collects all errors so that I can use the appropriate mode for development vs production.

#### Acceptance Criteria

1. WHEN lenient mode is enabled, THE Ground_Truth_Loader SHALL continue processing after encountering a malformed record and accumulate all errors in the Diagnostics object.
2. WHEN lenient mode is disabled, THE Ground_Truth_Loader SHALL raise a ValidationError on the first malformed record encountered, including the file key and line/row number.
3. THE Ground_Truth_Loader SHALL default to lenient mode when the mode parameter is not specified.

---

### Requirement 9: Functional Test Case Generation Prompt

**User Story:** As a developer, I want the Generation_Prompt to produce realistic, ground-truth-grounded functional test cases so that generated tests reflect actual user interactions.

#### Acceptance Criteria

1. THE Generation_Prompt SHALL instruct the model to generate Functional_Tests that are grounded exclusively in the provided TestCase data.
2. THE Generation_Prompt SHALL instruct the model to produce multi-turn conversation flows where each turn builds naturally on the previous context.
3. THE Generation_Prompt SHALL instruct the model to use domain-appropriate language and terminology drawn from the ground truth data.
4. WHEN ground truth TestCase objects include `contexts` fields, THE Generation_Prompt SHALL instruct the model to incorporate those context passages as the authoritative data source for expected responses.
5. THE Generation_Prompt SHALL instruct the model to output test cases in a structured YAML format with fields: scenario name, turns (each with question and expected_result), and category label "functional".

---

### Requirement 10: Boundary Test Case Generation Prompt

**User Story:** As a developer, I want the Generation_Prompt to also produce boundary test cases that exercise edge conditions and atypical-but-valid user behaviors so that my agent is tested beyond the happy path.

#### Acceptance Criteria

1. THE Generation_Prompt SHALL instruct the model to generate Boundary_Tests that exercise unexpected phrasings, boundary conditions, and unusual-but-valid user behaviors.
2. THE Generation_Prompt SHALL instruct the model to keep Boundary_Tests realistic and grounded in the application domain — not red-teaming, jailbreak, or security attack scenarios.
3. THE Generation_Prompt SHALL instruct the model to label each Boundary_Test with the category label "boundary".
4. THE Generation_Prompt SHALL provide the model with examples of boundary scenarios: misspellings, ambiguous references, out-of-range-but-close values, multi-intent queries, and context switches mid-conversation.
5. WHEN ground truth data is available, THE Generation_Prompt SHALL instruct the model to derive boundary scenarios from the actual data (e.g., querying for items just outside the menu, requesting reservations at closing time).

---

### Requirement 11: Category Ratio Control

**User Story:** As a developer, I want to control the ratio of functional to boundary test cases via a slider so that I can tune the test mix for my evaluation needs.

#### Acceptance Criteria

1. THE Notebook_UI SHALL provide an integer slider widget labeled "Functional / Boundary ratio" with a range of 0 to 100, representing the percentage of Functional_Tests.
2. THE Test_Generator SHALL calculate the number of Functional_Tests as `round(total_cases * ratio / 100)` and the number of Boundary_Tests as `total_cases - functional_count`.
3. WHEN the ratio is set to 100, THE Test_Generator SHALL generate only Functional_Tests.
4. WHEN the ratio is set to 0, THE Test_Generator SHALL generate only Boundary_Tests.
5. THE CLI_Entry_Point SHALL accept a `--functional-ratio` integer argument (0–100) that controls the same split.
6. THE Test_Generator SHALL default the Category_Ratio to 70 (70% functional, 30% boundary) when no value is specified.

---

### Requirement 12: Generation Prompt Optimization for Frontier Models

**User Story:** As a developer, I want the prompt engineered for frontier Bedrock models so that output quality and structure are maximized.

#### Acceptance Criteria

1. THE Generation_Prompt SHALL use structured XML-tagged sections to separate instructions, ground truth data, output format, and examples — matching the prompting best practices for Anthropic Claude models.
2. THE Generation_Prompt SHALL include a concise chain-of-thought instruction asking the model to reason about scenario diversity before generating output.
3. THE Generation_Prompt SHALL include at least one few-shot example of a well-formed functional test case and one few-shot example of a well-formed boundary test case.
4. THE Generation_Prompt SHALL specify the exact YAML output schema and instruct the model to produce only valid YAML with no surrounding prose.
5. WHEN the selected model is not a Claude model, THE Test_Generator SHALL still send the same prompt structure (non-Claude models will ignore XML tags gracefully).

---

### Requirement 13: Externalized Configuration

**User Story:** As a developer, I want all tunable parameters in an external config file so that I can customize the tool without editing Python source code.

#### Acceptance Criteria

1. THE Test_Generator SHALL load configuration from a YAML file (default path: `config.yaml` in the working directory).
2. THE Config_File SHALL support the following keys: `s3_uri`, `field_mapping`, `recursive`, `lenient`, `model_name`, `aws_region`, `functional_ratio`, `num_cases`, `num_questions_per_case`, `output_format`, and `languages`.
3. WHEN a Config_File is not found at the default path, THE Test_Generator SHALL use built-in default values for all configuration keys.
4. WHEN a configuration key is provided both in the Config_File and as a runtime argument (CLI flag or widget value), THE Test_Generator SHALL use the runtime argument, overriding the Config_File value.
5. IF the Config_File contains an unrecognized key, THEN THE Test_Generator SHALL log a warning and ignore the unrecognized key.

---

### Requirement 14: Parameterization of Hardcoded Values

**User Story:** As a developer, I want previously hardcoded values (language list, model list path, PDF folder path, prompt template) extracted into configuration so that the tool is adaptable without code changes.

#### Acceptance Criteria

1. THE Test_Generator SHALL read the list of supported languages from the Config_File `languages` key instead of a hardcoded list.
2. THE Test_Generator SHALL read the model registry file path from the Config_File `model_list_path` key, defaulting to `model_list.json`.
3. THE Test_Generator SHALL read the generation prompt template from an external file referenced by the Config_File `prompt_template_path` key, defaulting to a bundled template.
4. THE Test_Generator SHALL accept the S3_URI for ground truth data from the Config_File, replacing the hardcoded local `context_pdf_files/` folder path.
5. THE Test_Generator SHALL accept the AWS region from the Config_File `aws_region` key, defaulting to `us-east-1`.

---

### Requirement 15: CLI Entry Point

**User Story:** As a developer, I want a command-line interface so that I can run test case generation from scripts and CI/CD pipelines without opening a notebook.

#### Acceptance Criteria

1. THE CLI_Entry_Point SHALL be invocable as `python -m test_generator` or via a named console script entry point.
2. THE CLI_Entry_Point SHALL accept the following arguments: `--s3-uri`, `--config` (path to Config_File), `--model`, `--num-cases`, `--num-questions`, `--functional-ratio`, `--output` (output file path), `--lenient` / `--strict`, and `--app-description`.
3. WHEN the `--output` argument is provided, THE CLI_Entry_Point SHALL write generated test cases to the specified file path in YAML format.
4. WHEN the `--output` argument is omitted, THE CLI_Entry_Point SHALL print generated test cases to stdout.
5. IF a required input (app description) is missing from both CLI arguments and Config_File, THEN THE CLI_Entry_Point SHALL exit with a non-zero exit code and a message identifying the missing input.
6. THE CLI_Entry_Point SHALL return exit code 0 on success and a non-zero exit code on failure.

---

### Requirement 16: Notebook UI Modernization

**User Story:** As a developer, I want the notebook UI updated to support S3 ground truth loading, category ratio control, and externalized configuration so that the interactive experience matches the new capabilities.

#### Acceptance Criteria

1. THE Notebook_UI SHALL replace the "Load context PDF files" button with a text input widget for the S3_URI.
2. THE Notebook_UI SHALL add the Category_Ratio slider widget between the existing "# of questions per case" slider and the "Generate" button.
3. THE Notebook_UI SHALL display a summary of Diagnostics (files scanned, files parsed, records loaded, warnings) in the output area after ground truth loading completes.
4. THE Notebook_UI SHALL retain existing widgets for application description, system prompt, business metrics, language selection, model selection, number of cases, and number of questions per case.
5. WHEN the user clicks "Generate Test Cases", THE Notebook_UI SHALL show a progress indicator and the model name, case count, functional/boundary split, and ground truth record count before generation begins.

---

### Requirement 17: Output Format and Structure

**User Story:** As a developer, I want generated test cases output in a clean, structured YAML format with category labels so that I can directly feed them into evaluation frameworks.

#### Acceptance Criteria

1. THE Test_Generator SHALL output each generated test case as a YAML document with fields: `scenario_name` (string), `category` (string: "functional" or "boundary"), and `turns` (list of objects each with `question` and `expected_result`).
2. THE Test_Generator SHALL group functional test cases before boundary test cases in the output.
3. WHEN the output contains multiple test cases, THE Test_Generator SHALL separate each YAML document with the standard `---` document separator.
4. THE Test_Generator SHALL validate that the model's raw output is parseable as YAML before returning the result. IF the output is not valid YAML, THEN THE Test_Generator SHALL retry the model invocation once and, if still invalid, return the raw text with a warning.

---

### Requirement 18: Model Registry Cleanup

**User Story:** As a developer, I want the model registry streamlined so that duplicate entries are removed and each model entry includes all fields needed for invocation.

#### Acceptance Criteria

1. THE Test_Generator SHALL load models from `model_list.json` and deduplicate entries that share the same `model_id` and `region_name`, keeping the entry with the shorter key name.
2. WHEN a model entry lacks a `max_tokens` field, THE Test_Generator SHALL apply a default value of 4096.
3. THE Test_Generator SHALL validate that every model entry contains the required fields: `model_id`, `region_name`, `temperature`, and `inference_type` at load time. IF a required field is missing, THEN THE Test_Generator SHALL log a warning and exclude the model from the available models list.

---

### Requirement 19: Logging and Observability

**User Story:** As a developer, I want structured logging throughout the loading and generation pipeline so that I can diagnose issues in production.

#### Acceptance Criteria

1. THE Ground_Truth_Loader SHALL log at INFO level: the S3_URI being scanned, the count of files discovered, the count of files matching the Whitelist, and the total TestCase count after parsing.
2. THE Ground_Truth_Loader SHALL log at WARNING level: each skipped file (with reason), each malformed record (with file key and line/row number), and each S3 retry attempt.
3. THE Test_Generator SHALL log at INFO level: the selected model name, the number of cases requested, the functional/boundary split, and the prompt token estimate.
4. THE Test_Generator SHALL log at ERROR level: model invocation failures, YAML parse failures on model output, and configuration file parse errors.
5. THE Test_Generator SHALL use the Python standard `logging` module with a configurable log level (default: INFO).

---

### Requirement 20: TestCase Serialization Round-Trip

**User Story:** As a developer, I want to serialize TestCase objects to JSON and deserialize them back so that I can cache, inspect, and share ground truth datasets.

#### Acceptance Criteria

1. THE TestCase object SHALL provide a `to_dict()` method that returns a JSON-serializable dictionary containing all fields.
2. THE TestCase class SHALL provide a `from_dict(d)` class method that constructs a TestCase from a dictionary.
3. FOR ALL valid TestCase objects, `TestCase.from_dict(tc.to_dict())` SHALL produce a TestCase equal to the original (round-trip property).
4. WHEN a dictionary passed to `from_dict` lacks the required `prompt` field, THE TestCase class SHALL raise a ValueError.
5. WHEN a dictionary passed to `from_dict` lacks the required `expected` field, THE TestCase class SHALL raise a ValueError.
