# AI Realistic Test Cases Generator

Generate evaluation test cases for agentic AI applications using Amazon Bedrock. Load ground truth data from S3 (JSONL, JSON, CSV), then produce both **functional** and **edge** test cases in structured YAML format.

Works from a Jupyter notebook, the command line, or as a Python library.

---

## What it does

1. **Loads ground truth** from an S3 bucket — your existing Q&A pairs, expected responses, and context documents.
2. **Builds an optimized prompt** with XML-tagged sections tuned for Claude and other Bedrock models.
3. **Generates test cases** in two categories:
   - **Functional** — realistic, grounded in your data, multi-turn conversations.
   - **Boundary** — edge cases, misspellings, ambiguous queries, unusual-but-valid inputs.
4. **Outputs structured YAML** ready to feed into evaluation frameworks.

---

## Prerequisites

- **Python 3.10+**
- **AWS credentials** configured (via `~/.aws/credentials`, environment variables, or IAM role) with access to:
  - Amazon Bedrock (model invocation)
  - Amazon S3 (reading ground truth files)

---

## Installation

```bash
# Clone the repo
git clone <your-repo-url>
cd <repo-directory>

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows

# Install dependencies
pip install boto3 pyyaml

# For notebook usage, also install:
pip install ipywidgets jupyterlab

# For running tests:
pip install pytest hypothesis
```

---

## Quick Start

### Option 1: Command Line

```bash
python -m test_generator \
  --app-description "A restaurant reservation assistant on WhatsApp" \
  --s3-uri s3://my-bucket/ground-truth/ \
  --model claude-4.5-sonnet \
  --num-cases 5 \
  --num-questions 3 \
  --functional-ratio 70 \
  --output test_cases.yaml
```

This generates 5 test cases (70% functional, 30% edge cases), each with 3 turns, and writes them to `test_cases.yaml`.

### Option 2: Jupyter Notebook

```python
from test_generator import NotebookUI

ui = NotebookUI()
ui.display()
```

This renders an interactive widget UI where you fill in your app description, paste an S3 URI, pick a model, adjust sliders, and click "Generate Test Cases".

### Option 3: Python Library

```python
from test_generator import TestGeneratorOrchestrator, Config, load_config

config = load_config()  # reads config.yaml if present
config.num_cases = 10
config.functional_ratio = 60

orchestrator = TestGeneratorOrchestrator(config)
result = orchestrator.generate(
    app_description="A restaurant reservation assistant",
    system_prompt="You are Restaurant Helper, a formal assistant.",
    business_metrics="Goal completion rate > 90%",
    s3_uri="s3://my-bucket/ground-truth/",
)

print(result.yaml_text)
print(f"Valid YAML: {result.is_valid_yaml}")
print(f"Cases generated: {result.test_cases_generated}")
```

---

## CLI Reference

```
python -m test_generator [OPTIONS]
```

| Flag | Description | Default |
|---|---|---|
| `--app-description` | Application description (required) | — |
| `--s3-uri` | S3 URI for ground truth data | from config |
| `--config` | Path to YAML config file | `config.yaml` |
| `--model` | Bedrock model name | `claude-4-sonnet` |
| `--num-cases` | Total test cases to generate | `3` |
| `--num-questions` | Turns per test case | `2` |
| `--functional-ratio` | % functional vs boundary (0–100) | `70` |
| `--output` | Output file path (omit for stdout) | stdout |
| `--lenient` | Skip malformed records | default |
| `--strict` | Fail on first malformed record | — |
| `--system-prompt` | Agent system prompt text | `""` |
| `--business-metrics` | Business metrics text | `""` |
| `--language` | Target language | `English` |

---

## Configuration File

Create a `config.yaml` in your working directory to avoid passing flags every time:

```yaml
# S3 ground truth location
s3_uri: s3://my-bucket/ground-truth/

# Model settings
model_name: claude-4-sonnet
aws_region: us-east-1

# Generation settings
num_cases: 5
num_questions_per_case: 3
functional_ratio: 70    # 70% functional, 30% boundary

# File parsing
recursive: true          # scan sub-prefixes
lenient: true            # skip bad records instead of failing

# Field mapping (if your data uses different column names)
field_mapping:
  prompt_aliases: [question, input, query, user_input]
  expected_aliases: [answer, output, response, expected_output]

# UI settings
languages: [English, Spanish, French]

# Paths
model_list_path: model_list.json

# Logging
log_level: INFO
```

All keys are optional. CLI flags and widget values override config file values, which override built-in defaults.

---

## Ground Truth Data Format

Place your ground truth files in S3. Supported formats:

### JSONL (one JSON object per line)

```jsonl
{"prompt": "What are your hours?", "expected": "We are open 9 AM to 9 PM daily."}
{"prompt": "Do you have vegan options?", "expected": "Yes, we offer several vegan dishes."}
```

### JSON (array or wrapper object)

```json
[
  {"prompt": "Show me the menu", "expected": "Here is our full menu..."},
  {"prompt": "Book a table for 4", "expected": "I'd be happy to help with that reservation."}
]
```

Wrapper keys `data`, `records`, `samples`, and `test_cases` are also recognized:

```json
{"data": [{"prompt": "...", "expected": "..."}]}
```

### CSV

```csv
prompt,expected
"What are your hours?","We are open 9 AM to 9 PM daily."
"Do you have vegan options?","Yes, we offer several vegan dishes."
```

### Field Aliases

Your data doesn't need to use `prompt` and `expected` exactly. The tool recognizes common alternatives:

| Canonical field | Recognized aliases |
|---|---|
| `prompt` | `question`, `input`, `query`, `user_input` |
| `expected` | `answer`, `output`, `response`, `expected_output`, `expected_response` |
| `id` | `test_id`, `case_id`, `identifier` |
| `contexts` | `context`, `documents`, `passages`, `reference` |

You can also define custom aliases in the config file under `field_mapping`.

---

## Output Format

Generated test cases are YAML documents with this structure:

```yaml
- scenario_name: "Menu inquiry for Rice and Spice"
  category: "functional"
  turns:
    - question: "Can you show me the menu for Rice and Spice?"
      expected_result: "Restaurant Helper retrieves and displays the menu."
    - question: "What vegetarian options do they have?"
      expected_result: "Restaurant Helper filters and presents vegetarian items."
---
- scenario_name: "Reservation with ambiguous date"
  category: "boundary"
  turns:
    - question: "Book me a table for next Friday-ish, maybe 6 people"
      expected_result: "Restaurant Helper asks for clarification on the exact date."
    - question: "Actually make it 11 people"
      expected_result: "Restaurant Helper informs the user the max party size is 10."
```

Functional cases are grouped first, then boundary cases, separated by `---`.

---

## Available Models

The tool ships with `model_list.json` containing 60+ Bedrock models including:

- **Claude** — claude-4-sonnet, claude-4-opus, claude-3.7-sonnet, claude-3.5-sonnet-v2, and more
- **Amazon Nova** — nova-premier, nova-pro, nova-lite, nova-micro
- **Meta Llama** — llama-4-scout, llama-4-maverick, llama-3.3-70b, and more
- **Mistral** — pixtral-large, mistral-large, mixtral-8x7b
- **Others** — DeepSeek, Cohere Command R, AI21 Jamba, Qwen, Writer Palmyra

Use `--model <name>` to select one, or pick from the dropdown in the notebook UI.

---

## Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run a specific test file
python -m pytest tests/test_generator.py -v

# Run with coverage (if pytest-cov installed)
python -m pytest tests/ --cov=test_generator
```

---

## Project Structure

```
test_generator/
  __init__.py              # Package exports
  __main__.py              # CLI entry point (python -m test_generator)
  models.py                # TestCase, Diagnostics, FieldMapping dataclasses
  config.py                # Config loading from YAML with layered overrides
  ground_truth_loader.py   # S3 scanning, file discovery, parser dispatch
  prompt_builder.py        # XML-tagged prompt construction
  generator.py             # Orchestrator: load → prompt → invoke → validate
  notebook_ui.py           # ipywidgets UI for Jupyter
  parsers/
    __init__.py            # Parser registry
    jsonl_parser.py        # Line-by-line JSONL parsing
    json_parser.py         # Array / wrapper-key JSON parsing
    csv_parser.py          # Header-based CSV parsing
tests/
  test_models.py
  test_parsers.py
  test_ground_truth_loader.py
  test_config.py
  test_prompt_builder.py
  test_generator.py
  test_testcase_roundtrip.py
model_list.json            # Bedrock model registry
config.yaml                # Your config (create this)
```

---

## Troubleshooting

**"No supported ground truth files found"** — Check that your S3 URI points to a prefix containing `.jsonl`, `.json`, or `.csv` files. Make sure the prefix is correct (trailing slash is optional).

**"Model not found in registry"** — The `--model` name must match a key in `model_list.json`. Run with `--help` or check the file for available names.

**"Access Denied" on S3** — Your AWS credentials need `s3:ListBucket` and `s3:GetObject` permissions on the target bucket and prefix.

**"Model invocation failed"** — Verify your AWS credentials have `bedrock:InvokeModel` permission and that the selected model is enabled in your Bedrock console for the target region.

**Invalid YAML output** — The tool retries once automatically. If the model still produces invalid YAML, the raw text is returned with a warning. Try a different model or reduce `--num-cases`.
