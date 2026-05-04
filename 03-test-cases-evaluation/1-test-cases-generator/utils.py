import json
import boto3
import ipywidgets as widgets
from IPython.display import display
from typing import Dict, Any, List
import PyPDF2
import io

class TestCaseGenerator:
    def __init__(self):
        self.models = self._load_models()
        self.system_prompt = self._get_system_prompt()
        self.uploaded_docs_content = ""
        self._create_widgets()
        
    def _load_models(self) -> Dict[str, Any]:
        """Load available models from model_list.json"""
        with open('model_list.json', 'r') as f:
            return json.load(f)
    
    def _pdf_to_markdown(self, pdf_content: bytes) -> str:
        """Convert PDF content to markdown format"""
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_content))
            markdown_content = []
            
            print(f"    📖 PDF has {len(pdf_reader.pages)} pages")
            
            for page_num, page in enumerate(pdf_reader.pages, 1):
                text = page.extract_text()
                if text.strip():
                    markdown_content.append(f"## Page {page_num}\n\n{text}\n")
                    print(f"    📄 Page {page_num}: {len(text)} characters extracted")
            
            result = "\n".join(markdown_content)
            print(f"    ✅ Total markdown length: {len(result)} characters")
            return result
            
        except Exception as e:
            error_msg = f"Error processing PDF: {str(e)}"
            print(f"    ❌ {error_msg}")
            return error_msg
    
    def _get_system_prompt(self) -> str:
        """Return the system prompt for test case generation"""
        return """You are an expert Generative AI evaluation specialist tasked with creating comprehensive, domain-specific evaluation tests for AI agents and LLM based projects. Your expertise lies in generating realistic synthetic data and custom domain metrics that align with the specific business purpose of AI applications, rather than focusing solely on technical metrics.

## Your Task

Generate exactly {tests_amount} comprehensive evaluations components based on the user's application details:

### 1. Multi-turn Evaluation Tests (YAML Format)
Create realistic, natural conversation flows that test the agent's capabilities in domain-specific scenarios. Each test should include:
- **Sequential multi-turn interactions** that mirror real user conversations
- **Realistic expected results** that demonstrate successful agent responses
- **Domain-appropriate language and context**
- **Progressive complexity** within each conversation flow

**Requirements:**
- Generate exactly {tests_amount} ** distinct test scenarios**
- Each scenario should have **exactly {num_questions} question/response pairs**
- Use the exact YAML format structure provided in the reference
- Ensure conversations flow naturally and test different aspects of the application
- if provided use ONLY data from "Related Documentation" as ground-truth data sources, dont invent data use the provided data to generate realistic test cases

## Input Information Required

To generate accurate, domain-specific evaluations, provide:

1. **Application Details**: Describe the primary objective, goals, and core functionality of your AI application. 
INPUT: {app_details}

2. **Key Features**: List the main features and capabilities your application provides to users.
INPUT: {key_features}

3. **Business Goals**: Specify what are the business goals of the application, how is going to be measured in terms of business value.
INPUT: {business_goals}

4. **Related Documentation**: Analyze and use the following documentation as the only trusted ground-truth data source to generate realistic single and multi-turn test cases to be able to generated realistic test cases based on ground-truth provided data and simulate grounded input scenarios for the agentic application .
INPUT: {docs_content}

## Output Format Requirements

Only output the bellow yaml structure without any other text with {tests_amount} tests.

### YAML Test Structure:
```yaml
test_scenario_name:
question_1:
question: "Natural user question in domain context"
expected_results: "Detailed description of successful agent response"
question_2:
question: "Follow-up question building on previous context"
expected_results: "Expected agent behavior and information provided"
question_3:
question: "Complex scenario testing agent capabilities"
expected_results: "Comprehensive expected response including edge cases"
```

Focus on creating realistic scenarios that would actually occur in the application's domain, incorporating terminology and context from the provided documentation."""

    def _create_widgets(self):
        """Create all UI widgets"""
        # Application description
        self.app_description_label = widgets.HTML('<h2>1. Application description</h2>')
        self.app_description = widgets.Textarea(
            placeholder='e.g. Assist healthcare professionals in diagnosing patients based on symptoms and medical history',
            layout=widgets.Layout(width='100%', height='80px')
        )
        
        # System prompt/details
        self.system_prompt_label = widgets.HTML('<h2>2. System Prompt or Application Details</h2>')
        self.system_prompt_text = widgets.Textarea(
            placeholder='e.g. Patient record access, appointment scheduling, medication management, diagnostic assistance',
            layout=widgets.Layout(width='100%', height='180px')
        )
        
        # Business metrics
        self.business_metrics_label = widgets.HTML('<h2>3. What are the key business metrics?</h2>')
        self.business_metrics = widgets.Textarea(
            placeholder='e.g. Decrease Average Staff Turnover by 15%, Increase Patient Satisfaction Score by 20%',
            layout=widgets.Layout(width='100%', height='180px')
        )
        
        # PDF Context Section
        self.docs_upload_label = widgets.HTML('<h2>4. Related context files</h2>')
        self.docs_explanation_label = widgets.HTML('Upload and load pdf files fom "/context_pdf_files" folder with ground-truth data to have more realistic test cases.')
        
        # Create output widget first
        self.output = widgets.Output()
        
        # Context load button
        self.context_button = widgets.Button(
            description='Load context PDF files',
            button_style='success',
            layout=widgets.Layout(width='200px', height='30px')
        )
        self.context_button.on_click(self._load_context_pdfs)
        
        # Language and model selection
        self.language_model_label = widgets.HTML('<h2>Target Language & Model Selection</h2>')
        self.language_dropdown = widgets.Dropdown(
            options=['English', 'Spanish'],
            value='English',
            description='Target Language:'
        )
        
        model_options = list(self.models.keys())
        self.model_dropdown = widgets.Dropdown(
            options=model_options,
            value=model_options[0] if model_options else None,
            description='Select Model:'
        )
        
        # Number controls
        self.num_cases_label = widgets.HTML('<h2># of distinct cases to generate</h2>')
        self.num_cases_slider = widgets.IntSlider(value=3, min=1, max=30)
        
        self.num_questions_label = widgets.HTML('<h2># of questions per case</h2>')
        self.num_questions_slider = widgets.IntSlider(value=2, min=1, max=10)
        
        # Generate button and output
        self.spacer = widgets.HTML('<br>')
        self.generate_button = widgets.Button(
            description='Generate Test Cases',
            button_style='primary',
            layout=widgets.Layout(width='200px', height='40px')
        )
        self.generate_button.on_click(self._generate_test_cases)
    
    def _load_context_pdfs(self, button=None):
        """Load PDFs from context_pdf_files folder"""
        with self.output:
            self.output.clear_output()
            
            try:
                from pathlib import Path
                
                pdf_dir = Path("context_pdf_files")
                if not pdf_dir.exists():
                    print("📁 No context_files folder found - continuing without context")
                    self.uploaded_docs_content = ""
                    return
                
                pdf_files = list(pdf_dir.glob("*.pdf"))
                if not pdf_files:
                    print("📁 No PDF files found in context_files folder - continuing without context")
                    self.uploaded_docs_content = ""
                    return
                
                print(f"----------------------------------------------------------")
                print(f"LOADING CONTEXT PDF FILES")
                print(f"----------------------------------------------------------")
                print(f" ")
                print(f"📁 Found {len(pdf_files)} PDF files in context_pdf_files/")
                
                all_content = []
                for pdf_file in pdf_files:
                    print(f"📄 Loading {pdf_file.name}...")
                    
                    with open(pdf_file, 'rb') as f:
                        pdf_content = f.read()
                    
                    markdown_content = self._pdf_to_markdown(pdf_content)
                    all_content.append(f"# Document: {pdf_file.name}\n\n{markdown_content}")
                    print(f"✅ Processed {pdf_file.name}")
                
                self.uploaded_docs_content = "\n\n---\n\n".join(all_content)
                print(f"✅ Loaded {len(all_content)} PDFs ({len(self.uploaded_docs_content)} characters)")
                
            except Exception as e:
                print(f"❌ Error loading PDFs: {e}")
                self.uploaded_docs_content = ""
    
    def display_ui(self):
        """Display the complete UI"""
        display(self.app_description_label)
        display(self.app_description)
        display(self.system_prompt_label)
        display(self.system_prompt_text)
        display(self.business_metrics_label)
        display(self.business_metrics)
        display(self.docs_upload_label)
        display(self.docs_explanation_label)
        display(self.context_button)
        display(self.language_model_label)
        display(self.language_dropdown)
        display(self.model_dropdown)
        display(self.num_cases_label)
        display(self.num_cases_slider)
        display(self.num_questions_label)
        display(self.num_questions_slider)
        display(self.spacer)
        display(self.generate_button)
        display(self.output)
    
    def _generate_test_cases(self, button):
        """Generate test cases using the selected model"""
        with self.output:
            self.output.clear_output()
            
            # Validate inputs
            if not self.app_description.value.strip():
                print("--------------------------------------------")
                print("ERROR")
                print("--------------------------------------------")
                print("")
                print("❌ Please provide an application description")
                return
            
            if not self.system_prompt_text.value.strip():
                print("--------------------------------------------")
                print("ERROR")
                print("--------------------------------------------")
                print("")
                print("❌ Please provide system prompt or application details")
                return
            
            try:
                # Get model configuration
                selected_model = self.model_dropdown.value
                model_config = self.models[selected_model]
                
                # Prepare the prompt
                prompt = self.system_prompt.format(
                    tests_amount=self.num_cases_slider.value,
                    num_questions=self.num_questions_slider.value,
                    app_details=self.app_description.value,
                    key_features=self.system_prompt_text.value,
                    business_goals=self.business_metrics.value,
                    docs_content=self.uploaded_docs_content if self.uploaded_docs_content else "No additional documentation provided."
                )
                
                print("--------------------------------------------")
                print("GENERATING TEST CASES.... this may take time")
                print("--------------------------------------------")
                print(" ")
                print(f"📊 Model: {selected_model}")
                print(f"📝 Cases: {self.num_cases_slider.value}")
                print(f"❓ Questions per case: {self.num_questions_slider.value}")
                
                if self.uploaded_docs_content:
                    print("📄 Using uploaded documentation for context")
                    print(f"📏 Documentation length: {len(self.uploaded_docs_content)} characters")
                else:
                    print("📄 No uploaded documentation - using default message")
                
                # Initialize Bedrock client
                bedrock = boto3.client('bedrock-runtime')
                
                # Prepare request based on model type
                if 'claude' in selected_model.lower():
                    body = {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": model_config.get("max_tokens", 4000),
                        "messages": [
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ]
                    }
                else:
                    body = {
                        "inputText": prompt,
                        "textGenerationConfig": {
                            "maxTokenCount": model_config.get("max_tokens", 4000),
                            "temperature": model_config.get("temperature", 0.7)
                        }
                    }
                
                # Make the API call
                response = bedrock.invoke_model(
                    modelId=model_config["model_id"],
                    body=json.dumps(body)
                )
                
                # Parse response
                response_body = json.loads(response['body'].read())
                
                if 'claude' in selected_model.lower():
                    generated_text = response_body['content'][0]['text']
                else:
                    generated_text = response_body['results'][0]['outputText']
                
                print("✅ Test cases generated successfully!")
                print("\n" + "="*80)
                print("GENERATED TEST CASES:")
                print("="*80)
                print(generated_text)
                
            except Exception as e:
                print(f"❌ Error generating test cases: {str(e)}")
                print("Please check your AWS credentials and model access permissions.")
