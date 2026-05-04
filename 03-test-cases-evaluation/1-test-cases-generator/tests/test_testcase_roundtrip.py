"""Property-based tests for TestCase round-trip serialization.

Property 1 (Round-trip consistency):
    For all valid TestCase objects, TestCase.from_dict(tc.to_dict()) produces
    a TestCase equal to the original.

Validates: Requirements 6.5, 20.3
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from test_generator.models import TestCase


# ---------------------------------------------------------------------------
# Hypothesis strategies for generating arbitrary TestCase instances
# ---------------------------------------------------------------------------

# Strategy for the `expected` field: either a single string or a list of strings.
_expected_strategy = st.one_of(
    st.text(min_size=1),
    st.lists(st.text(min_size=1), min_size=1, max_size=5),
)

# Strategy for JSON-safe metadata / agent_spec dicts (string keys, simple values).
_simple_values = st.one_of(
    st.text(),
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.booleans(),
    st.none(),
)

_json_dict = st.dictionaries(
    keys=st.text(min_size=1, max_size=20),
    values=_simple_values,
    max_size=5,
)

_testcase_strategy = st.builds(
    TestCase,
    prompt=st.text(min_size=1),
    expected=_expected_strategy,
    id=st.one_of(st.none(), st.text(min_size=1)),
    contexts=st.lists(st.text(), max_size=5),
    metadata=_json_dict,
    agent_spec=_json_dict,
)


# ---------------------------------------------------------------------------
# Property test
# ---------------------------------------------------------------------------

@given(tc=_testcase_strategy)
@settings(max_examples=200)
def test_roundtrip_consistency(tc: TestCase) -> None:
    """TestCase.from_dict(tc.to_dict()) == tc for all valid TestCase objects."""
    roundtripped = TestCase.from_dict(tc.to_dict())
    assert roundtripped == tc, (
        f"Round-trip mismatch:\n  original:     {tc}\n  roundtripped: {roundtripped}"
    )
