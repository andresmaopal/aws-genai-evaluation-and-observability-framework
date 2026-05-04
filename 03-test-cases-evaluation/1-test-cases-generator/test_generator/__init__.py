"""test_generator — S3 Ground Truth Test Generator package.

Provides S3-based ground truth loading, dual-category (functional + boundary)
test case generation via Amazon Bedrock, externalized YAML configuration, and
both CLI and notebook entry points.
"""

from test_generator.config import Config, load_config
from test_generator.generator import GenerationResult, TestGeneratorOrchestrator
from test_generator.ground_truth_loader import load_ground_truth
from test_generator.models import Diagnostics, FieldMapping, TestCase


def __getattr__(name: str):
    """Lazy-load NotebookUI so the package works without ipywidgets installed."""
    if name == "NotebookUI":
        from test_generator.notebook_ui import NotebookUI
        return NotebookUI
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Config",
    "Diagnostics",
    "FieldMapping",
    "GenerationResult",
    "load_config",
    "load_ground_truth",
    "NotebookUI",
    "TestCase",
    "TestGeneratorOrchestrator",
]
