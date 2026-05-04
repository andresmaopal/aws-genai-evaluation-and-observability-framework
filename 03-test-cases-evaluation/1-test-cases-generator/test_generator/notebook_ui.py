"""Modernized notebook UI for the S3 Ground Truth Test Generator.

Provides an ipywidgets-based interactive interface for Jupyter notebooks.
Replaces the legacy PDF-based UI with S3 ground truth loading, a
functional/boundary ratio slider, and diagnostics display.

Requirements: 11.1, 14.1, 16.1, 16.2, 16.3, 16.4, 16.5
"""

from __future__ import annotations

import logging
from typing import Any

import ipywidgets as widgets
from IPython.display import display

from test_generator.config import Config, load_config
from test_generator.generator import TestGeneratorOrchestrator
from test_generator.ground_truth_loader import load_ground_truth
from test_generator.models import Diagnostics, TestCase

logger = logging.getLogger(__name__)


class NotebookUI:
    """Modernized ipywidgets UI for the test case generation pipeline.

    Replaces the legacy PDF load button with an S3 URI text input, adds a
    category ratio slider, and displays diagnostics after ground truth
    loading.

    Parameters
    ----------
    config:
        Optional pre-loaded ``Config``.  When *None*, ``load_config()`` is
        called with default settings.
    """

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or load_config()
        self._orchestrator = TestGeneratorOrchestrator(self.config)
        self._ground_truth: list[TestCase] = []
        self._diagnostics: Diagnostics | None = None
        self._create_widgets()

    # ------------------------------------------------------------------
    # Widget creation
    # ------------------------------------------------------------------

    def _create_widgets(self) -> None:
        """Build all ipywidgets for the notebook interface."""

        # -- 1. Application description ------------------------------------
        self.app_description_label = widgets.HTML(
            "<h2>1. Application description</h2>"
        )
        self.app_description = widgets.Textarea(
            placeholder=(
                "e.g. Assist healthcare professionals in diagnosing patients "
                "based on symptoms and medical history"
            ),
            layout=widgets.Layout(width="100%", height="80px"),
        )

        # -- 2. System prompt / application details -------------------------
        self.system_prompt_label = widgets.HTML(
            "<h2>2. System Prompt or Application Details</h2>"
        )
        self.system_prompt_text = widgets.Textarea(
            placeholder=(
                "e.g. Patient record access, appointment scheduling, "
                "medication management, diagnostic assistance"
            ),
            layout=widgets.Layout(width="100%", height="180px"),
        )

        # -- 3. Business metrics --------------------------------------------
        self.business_metrics_label = widgets.HTML(
            "<h2>3. What are the key business metrics?</h2>"
        )
        self.business_metrics = widgets.Textarea(
            placeholder=(
                "e.g. Decrease Average Staff Turnover by 15%, "
                "Increase Patient Satisfaction Score by 20%"
            ),
            layout=widgets.Layout(width="100%", height="180px"),
        )

        # -- 4. S3 ground truth URI (replaces PDF button) -------------------
        self.s3_uri_label = widgets.HTML(
            "<h2>4. Ground Truth S3 URI</h2>"
        )
        self.s3_uri_explanation = widgets.HTML(
            "Provide an S3 URI (e.g. <code>s3://my-bucket/ground-truth/</code>) "
            "containing JSONL, JSON, or CSV ground truth files."
        )
        self.s3_uri_input = widgets.Text(
            value=self.config.s3_uri or "",
            placeholder="s3://bucket-name/prefix/",
            layout=widgets.Layout(width="100%"),
        )
        self.load_ground_truth_button = widgets.Button(
            description="Load Ground Truth",
            button_style="success",
            layout=widgets.Layout(width="200px", height="30px"),
        )
        self.load_ground_truth_button.on_click(self._on_load_ground_truth)

        # -- Language & model selection -------------------------------------
        self.language_model_label = widgets.HTML(
            "<h2>Target Language & Model Selection</h2>"
        )
        # Populate languages from config (Req 14.1)
        self.language_dropdown = widgets.Dropdown(
            options=self.config.languages,
            value=self.config.languages[0] if self.config.languages else "English",
            description="Target Language:",
        )

        model_options = self._orchestrator.available_models
        self.model_dropdown = widgets.Dropdown(
            options=model_options,
            value=model_options[0] if model_options else None,
            description="Select Model:",
        )

        # -- Num cases slider -----------------------------------------------
        self.num_cases_label = widgets.HTML(
            "<h2># of distinct cases to generate</h2>"
        )
        self.num_cases_slider = widgets.IntSlider(
            value=self.config.num_cases, min=1, max=30,
        )

        # -- Num questions slider -------------------------------------------
        self.num_questions_label = widgets.HTML(
            "<h2># of questions per case</h2>"
        )
        self.num_questions_slider = widgets.IntSlider(
            value=self.config.num_questions_per_case, min=1, max=10,
        )

        # -- Category ratio slider (Req 11.1, 16.2) -------------------------
        self.ratio_label = widgets.HTML(
            "<h2>Functional / Boundary ratio</h2>"
        )
        self.ratio_slider = widgets.IntSlider(
            value=self.config.functional_ratio,
            min=0,
            max=100,
            description="Functional %:",
        )

        # -- Generate button & output area ----------------------------------
        self.spacer = widgets.HTML("<br>")
        self.generate_button = widgets.Button(
            description="Generate Test Cases",
            button_style="primary",
            layout=widgets.Layout(width="200px", height="40px"),
        )
        self.generate_button.on_click(self._on_generate)

        self.output = widgets.Output()

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def display(self) -> None:
        """Render the complete notebook UI."""
        display(self.app_description_label)
        display(self.app_description)
        display(self.system_prompt_label)
        display(self.system_prompt_text)
        display(self.business_metrics_label)
        display(self.business_metrics)
        # S3 URI section (replaces PDF button — Req 16.1)
        display(self.s3_uri_label)
        display(self.s3_uri_explanation)
        display(self.s3_uri_input)
        display(self.load_ground_truth_button)
        # Language & model
        display(self.language_model_label)
        display(self.language_dropdown)
        display(self.model_dropdown)
        # Sliders
        display(self.num_cases_label)
        display(self.num_cases_slider)
        display(self.num_questions_label)
        display(self.num_questions_slider)
        # Ratio slider between questions slider and Generate button (Req 16.2)
        display(self.ratio_label)
        display(self.ratio_slider)
        # Generate
        display(self.spacer)
        display(self.generate_button)
        display(self.output)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_load_ground_truth(self, _button: Any = None) -> None:
        """Load ground truth from the S3 URI entered by the user."""
        with self.output:
            self.output.clear_output()
            s3_uri = self.s3_uri_input.value.strip()
            if not s3_uri:
                print("❌ Please enter an S3 URI.")
                return

            print("----------------------------------------------------------")
            print("LOADING GROUND TRUTH FROM S3")
            print("----------------------------------------------------------")
            print(f"📦 URI: {s3_uri}")
            print()

            try:
                test_cases, diagnostics = load_ground_truth(
                    s3_uri=s3_uri,
                    field_mapping=self.config.field_mapping,
                    recursive=self.config.recursive,
                    lenient=self.config.lenient,
                )
                self._ground_truth = test_cases
                self._diagnostics = diagnostics

                # Display diagnostics summary (Req 16.3)
                print("✅ Ground truth loaded successfully!")
                print()
                self._print_diagnostics(diagnostics)

            except Exception as exc:
                print(f"❌ Error loading ground truth: {exc}")
                self._ground_truth = []
                self._diagnostics = None

    def _on_generate(self, _button: Any = None) -> None:
        """Run the generation pipeline with current widget values."""
        with self.output:
            self.output.clear_output()

            app_desc = self.app_description.value.strip()
            if not app_desc:
                print("❌ Please provide an application description.")
                return

            sys_prompt = self.system_prompt_text.value.strip()
            biz_metrics = self.business_metrics.value.strip()
            s3_uri = self.s3_uri_input.value.strip()
            model_name = self.model_dropdown.value
            num_cases = self.num_cases_slider.value
            num_questions = self.num_questions_slider.value
            ratio = self.ratio_slider.value
            language = self.language_dropdown.value

            # Apply widget values as config overrides
            self.config.num_cases = num_cases
            self.config.num_questions_per_case = num_questions
            self.config.functional_ratio = ratio

            functional_count = round(num_cases * ratio / 100)
            boundary_count = num_cases - functional_count

            # Progress indicator (Req 16.5)
            print("----------------------------------------------------------")
            print("GENERATING TEST CASES.... this may take time")
            print("----------------------------------------------------------")
            print()
            print(f"📊 Model: {model_name}")
            print(f"📝 Total cases: {num_cases}")
            print(f"   ├─ Functional: {functional_count}")
            print(f"   └─ Boundary:   {boundary_count}")
            print(f"❓ Questions per case: {num_questions}")
            print(f"🌐 Language: {language}")
            if self._ground_truth:
                print(f"📄 Ground truth records: {len(self._ground_truth)}")
            else:
                print("📄 No ground truth loaded — generation will proceed without it")
            print()

            try:
                result = self._orchestrator.generate(
                    app_description=app_desc,
                    system_prompt=sys_prompt,
                    business_metrics=biz_metrics,
                    s3_uri=s3_uri or None,
                    ground_truth=self._ground_truth or None,
                    model_name=model_name,
                    language=language,
                )

                # Show diagnostics if freshly loaded via s3_uri
                if result.diagnostics and not self._diagnostics:
                    self._print_diagnostics(result.diagnostics)

                if result.warnings:
                    for w in result.warnings:
                        print(f"⚠️  {w}")
                    print()

                print("✅ Test cases generated successfully!")
                print()
                print("=" * 80)
                print("GENERATED TEST CASES:")
                print("=" * 80)
                print(result.yaml_text)

            except Exception as exc:
                print(f"❌ Error generating test cases: {exc}")
                print(
                    "Please check your AWS credentials and model access permissions."
                )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _print_diagnostics(diagnostics: Diagnostics) -> None:
        """Print a human-readable diagnostics summary to the output area."""
        print("📋 Diagnostics Summary:")
        print(f"   Files scanned:    {diagnostics.total_files_scanned}")
        print(f"   Files parsed:     {diagnostics.files_successfully_parsed}")
        print(f"   Records loaded:   {diagnostics.total_test_cases}")
        warnings_count = len(diagnostics.skipped_files) + len(
            diagnostics.malformed_records
        )
        print(f"   Warnings:         {warnings_count}")
        if diagnostics.skipped_files:
            print()
            print("   Skipped files:")
            for rec in diagnostics.skipped_files:
                print(f"     - {rec.file_key}: {rec.reason}")
        if diagnostics.malformed_records:
            print()
            print("   Malformed records:")
            for rec in diagnostics.malformed_records[:10]:
                loc = f"line/row {rec.line_or_row}" if rec.line_or_row else "N/A"
                print(f"     - {rec.file_key} ({loc}): {rec.reason}")
            remaining = len(diagnostics.malformed_records) - 10
            if remaining > 0:
                print(f"     ... and {remaining} more")
        print()
