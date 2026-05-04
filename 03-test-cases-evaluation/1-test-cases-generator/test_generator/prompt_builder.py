"""Prompt builder for the S3 Ground Truth Test Generator.

Constructs an XML-tagged generation prompt optimized for frontier Bedrock
models (Claude family).  Non-Claude models ignore the XML tags gracefully.

Requirements: 9.1–9.5, 10.1–10.5, 12.1–12.5, 14.3
"""

from __future__ import annotations

from typing import Any

import yaml

from test_generator.models import TestCase


def _serialize_ground_truth(test_cases: list[TestCase]) -> str:
    """Serialize TestCase objects as a YAML list for embedding in the prompt."""
    if not test_cases:
        return "No ground truth data provided."
    records = []
    for tc in test_cases:
        entry: dict[str, Any] = {"prompt": tc.prompt, "expected": tc.expected}
        if tc.contexts:
            entry["contexts"] = tc.contexts
        if tc.id:
            entry["id"] = tc.id
        records.append(entry)
    return yaml.dump(records, default_flow_style=False, allow_unicode=True)


def build_prompt(
    test_cases: list[TestCase],
    app_description: str,
    system_prompt: str,
    business_metrics: str,
    functional_count: int,
    boundary_count: int,
    num_questions_per_case: int,
    language: str = "English",
) -> str:
    """Construct the XML-tagged generation prompt for Bedrock models.

    Parameters
    ----------
    test_cases:
        Ground truth TestCase objects to embed in the prompt.
    app_description:
        Free-text description of the application under test.
    system_prompt:
        The agent's system prompt or key features description.
    business_metrics:
        Business metrics / goals for the application.
    functional_count:
        Number of functional test cases to request.
    boundary_count:
        Number of boundary test cases to request.
    num_questions_per_case:
        Number of turns (question/answer pairs) per test case.
    language:
        Target language for generated test cases.

    Returns
    -------
    str
        The complete prompt string with XML-tagged sections.
    """
    ground_truth_yaml = _serialize_ground_truth(test_cases)

    return f"""\
<instructions>
You are an expert Generative AI evaluation specialist. Generate exactly {functional_count} \
functional test cases and {boundary_count} boundary test cases for the application described below.

Each test case must have exactly {num_questions_per_case} question/response turns.
Generate all output in {language}.

Functional test cases must be realistic, grounded exclusively in the provided ground truth data, \
and representative of typical end-user interactions. Use domain-appropriate language and terminology \
drawn from the ground truth data. When ground truth includes context passages, treat them as the \
authoritative data source for expected responses. Multi-turn conversations should build naturally \
on previous context.

Boundary test cases must exercise edge conditions, unexpected phrasings, and unusual-but-valid \
user behaviors. They should remain realistic and grounded in the application domain — not \
red-teaming, jailbreak, or security attack scenarios. Examples of boundary scenarios include: \
misspellings, ambiguous references, out-of-range-but-close values, multi-intent queries, and \
context switches mid-conversation. When ground truth data is available, derive boundary scenarios \
from the actual data.

<chain_of_thought>
Before generating, reason about:
1. What distinct scenarios exist in the ground truth data?
2. What boundary conditions are realistic for this domain?
3. How can turns build naturally on each other?
</chain_of_thought>
</instructions>

<ground_truth>
{ground_truth_yaml}
</ground_truth>

<application_context>
  <description>{app_description}</description>
  <system_prompt>{system_prompt}</system_prompt>
  <business_metrics>{business_metrics}</business_metrics>
</application_context>

<output_format>
Output ONLY valid YAML with no surrounding prose. Use this exact schema:

```yaml
- scenario_name: "descriptive name"
  category: "functional"  # or "boundary"
  turns:
    - question: "user question"
      expected_result: "expected agent response"
    - question: "follow-up question"
      expected_result: "expected response"
```

Group all functional tests first, then boundary tests.
Separate each YAML document with ---.
</output_format>

<examples>
  <functional_example>
  - scenario_name: "Menu inquiry for Rice and Spice"
    category: "functional"
    turns:
      - question: "Can you show me the menu for Rice and Spice?"
        expected_result: "Restaurant Helper retrieves and displays the Rice and Spice menu with items, descriptions, and prices."
      - question: "What vegetarian options do they have?"
        expected_result: "Restaurant Helper filters and presents vegetarian items from the Rice and Spice menu."
  </functional_example>

  <boundary_example>
  - scenario_name: "Reservation with ambiguous date reference"
    category: "boundary"
    turns:
      - question: "Book me a table for next Friday-ish, maybe 6 people"
        expected_result: "Restaurant Helper asks for clarification on the exact date and confirms the party size of 6."
      - question: "Actually make it 11 people"
        expected_result: "Restaurant Helper informs the user that the maximum party size is 10 and asks them to adjust."
  </boundary_example>
</examples>"""
