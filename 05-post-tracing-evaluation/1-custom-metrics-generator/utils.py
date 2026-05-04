import json
import boto3
import ipywidgets as widgets
from IPython.display import display
from typing import Dict, Any

class CustomMetricsGenerator:
    def __init__(self):
        self.models = self._load_models()
        self.system_prompt = self._get_system_prompt()
        self._create_widgets()
        
    def _load_models(self) -> Dict[str, Any]:
        """Load available models from model_list.json"""
        with open('model_list.json', 'r') as f:
            return json.load(f)
    
    def _get_system_prompt(self) -> str:
        """Return the embedded system prompt for custom metrics generation"""
        return """You are an expert Generative AI evaluation specialist tasked with creating comprehensive, domain-specific metrics for AI agents and LLM-based projects. Your expertise lies in generating realistic synthetic data and custom domain metrics that align with the specific business purpose of AI applications, rather than focusing solely on technical metrics..

## Your Task

Generate a comprehensive evaluation components based on the user's application details:

### 1. Custom Domain Metrics (Python/RAGAS Format)
Create comprehensive evaluation metrics using RAGAS framework:


**AspectCritic Metrics (5 minimum):**
- Focus on binary success/failure evaluation of critical domain functions
- Address core business objectives and user experience quality
- Include domain-specific accuracy, completeness, and compliance measures


**RubricScore Metrics (5 minimum):**
- Provide 5-point scoring scales for qualitative assessment
- Cover communication quality, user experience, and domain expertise
- Include detailed rubric descriptions for each score level (1-5)


**Requirements:**
- Infer first the application industry domain
- Use exact Python syntax from the reference examples
- Include meaningful metric names and definitions
- Provide comprehensive rubric descriptions
- Focus on domain-relevant evaluation criteria


## Input Information Required

To generate accurate, domain-specific evaluations, provide:

1. **Application Details**: Describe the primary objective, goals, and core functionality of your AI application. 
INPUT: {app_details}


2. **Key Features**: List the main features and capabilities your application provides to users: 
INPUT: {key_features}


3. **Business Goals**: Specify what are the business goals of the application, how is going to be measured in terms of business value.
INPUT: {business_goals}


## Output Format Requirements

All the generated metrics test MUST be all in {target_language}, respect and leave original english python variables names in english, following the below mandatory yaml structure. 

### Sample YAML Metrics Structure:
```yaml
# aspect_critics are binary metrics that return 1 or 0 (true or false)
aspect_critics:
- name: "Tone of the Agent Metric"
definition: "Return 1 if the agent communication is formal, concise, and is not verbose; otherwise, return 0."

- name: "Tool Usage Effectiveness"
definition: "Return 1 if the agent appropriately used available tools to fulfill the user's request (such as using retrieve for financial market questions and current_time for time questions). Return 0 if the agent failed to use appropriate tools or used unnecessary tools."

# rubric_scores are discrete metrics and the result depends on the specified range, e.g: 1-5
- name: "Answer Correctness"
rubrics:
"score1_description": "The answer is completely incorrect or contradicts the reference/ground truth; omits key rules or policies."
"score2_description": "The answer is mostly incorrect, with substantial errors in rules, calculations, or policies; may contain partially correct fragments but is unreliable."
"score3_description": "The answer is partially correct: covers core aspects but with omissions or inaccuracies that affect its validity for a structured task."
"score4_description": "The answer is almost entirely correct and consistent with the reference; only minor or non-critical omissions."
"score5_description": "The answer is completely correct, consistent with the reference, and covers required rules/calculations/policies without errors or omissions."
```

## Quality Guidelines

- **Realism**: Ensure all scenarios reflect actual user interactions in the application industry domain.
- **Business Goals Alignment** The custom metrics have to contribute on measure the business goals from different perspectives.
- **Completeness**: Cover the full spectrum of application functionality
- **Domain Expertise**: Demonstrate deep understanding of industry-specific requirements
- **Practical Application**: Focus on metrics that provide actionable insights for improvement.

Generate comprehensive, production-ready metrics for evaluation framework that enable thorough assessment of AI agent performance in real-world application"""
    
    def _create_widgets(self):
        """Create all UI widgets"""
        self.app_details = widgets.Textarea(
            placeholder='e.g. Assist healthcare professionals and patients with medical-related tasks, access medical information, schedule appointments...',
            layout=widgets.Layout(width='100%', height='80px')
        )
        
        self.key_features = widgets.Textarea(
            placeholder='e.g. Patient record access, appointment scheduling, prescription management, lab results retrieval...',
            layout=widgets.Layout(width='100%', height='180px')
        )
        
        self.business_goals = widgets.Textarea(
            placeholder='e.g. Decrease Average Staff Turnover Rate, Reduce Average Cost per Treatment (ACT)...',
            layout=widgets.Layout(width='100%', height='180px')
        )
        
        self.language = widgets.Dropdown(
            options=['English', 'Spanish'],
            value='English',
            description='Target Language:'
        )
        
        self.model = widgets.Dropdown(
            options=list(self.models.keys()),
            value=list(self.models.keys())[0],
            description='Select Model:',
        )

        self.num_aspect_critics = widgets.IntSlider(
            value=5, 
            min=3, 
            max=15,
            description='Binary Metrics:'
        )
        
        self.num_rubric_scores = widgets.IntSlider(
            value=5, 
            min=3, 
            max=15,
            description='Rubric Metrics:'
        )
        
        self.generate_btn = widgets.Button(
            description='Generate Custom Metrics',
            button_style='primary',
            layout=widgets.Layout(width='220px', height='40px')
        )
        
        self.output = widgets.Output()
        
        self.generate_btn.on_click(self._on_generate)
    
    def _on_generate(self, b):
        """Handle generate button click"""
        with self.output:
            self.output.clear_output()
            
            if not all([self.app_details.value.strip(), self.key_features.value.strip(), self.business_goals.value.strip()]):
                print("❌ Please fill all required fields")
                return
            
            print("🔄 Generating custom evaluation metrics. Please wait, this may take time...")
            
            try:
                result = self.generate_custom_metrics(
                    self.app_details.value,
                    self.key_features.value,
                    self.business_goals.value,
                    self.language.value,
                    self.model.value,
                    self.num_aspect_critics.value,
                    self.num_rubric_scores.value
                )
                
                print("✅ Custom evaluation metrics generated successfully!")
                
                # Display YAML with syntax highlighting and copy functionality
                from IPython.display import HTML, Javascript
                
                copy_button_html = f"""
                <div style="margin: 10px 0;">
                    <button onclick="copyToClipboard()" style="
                        background-color: #007cba; 
                        color: white; 
                        border: none; 
                        padding: 8px 16px; 
                        border-radius: 4px; 
                        cursor: pointer;
                        font-size: 14px;
                    ">📋 Copy YAML Metrics</button>
                </div>
                <pre id="yaml-content" style="
                    background-color: #f8f9fa; 
                    border: 1px solid #e9ecef; 
                    border-radius: 6px; 
                    padding: 16px; 
                    overflow-x: auto; 
                    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace; 
                    font-size: 13px; 
                    line-height: 1.4;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                "><code>{result.replace('<', '&lt;').replace('>', '&gt;')}</code></pre>
                
                <script>
                function copyToClipboard() {{
                    const content = document.getElementById('yaml-content').textContent;
                    navigator.clipboard.writeText(content).then(function() {{
                        const button = event.target;
                        const originalText = button.textContent;
                        button.textContent = '✅ Copied!';
                        button.style.backgroundColor = '#28a745';
                        setTimeout(function() {{
                            button.textContent = originalText;
                            button.style.backgroundColor = '#007cba';
                        }}, 2000);
                    }});
                }}
                </script>
                """
                
                display(HTML(copy_button_html))
                
            except Exception as e:
                print(f"❌ Error: {str(e)}")
    
    def display_ui(self):
        """Display all widgets"""
        display(widgets.HTML("<h2>1. Application Description</h2>"))
        display(self.app_details)
        
        display(widgets.HTML("<h2>2. System Prompt or Application Details</h2>"))
        display(self.key_features)
        
        display(widgets.HTML("<h2>3. What are the Key Business Goals?</h2>"))
        display(self.business_goals)
        
        display(widgets.HTML("<h2>Target Language & Model Selection</h2>"))
        display(self.language)
        display(self.model)
        
        display(widgets.HTML("<h2>Number of Metrics to Generate (Binary and Rubric)</h2>"))
        display(self.num_aspect_critics)
        display(self.num_rubric_scores)
        
        display(widgets.HTML("<br>"))
        display(self.generate_btn)
        display(self.output)
        
    
    def generate_custom_metrics(self, app_details: str, key_features: str, 
                              business_goals: str, target_language: str, 
                              selected_model: str, num_aspect_critics: int, 
                              num_rubric_scores: int) -> str:
        """Generate custom evaluation metrics using the selected model"""
        
        formatted_prompt = self.system_prompt.format(
            app_details=app_details,
            key_features=key_features,
            business_goals=business_goals,
            target_language=target_language
        )
        
        # Add specific instructions for the number of metrics
        formatted_prompt += f"\n\nGenerate exactly {num_aspect_critics} AspectCritic metrics and {num_rubric_scores} RubricScore metrics."
        
        model_config = self.models[selected_model]
        
        bedrock = boto3.client(
            'bedrock-runtime',
            region_name=model_config['region_name']
        )
        
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4000,
            "temperature": model_config['temperature'],
            "messages": [{"role": "user", "content": formatted_prompt}]
        }
        
        response = bedrock.invoke_model(
            modelId=model_config['model_id'],
            body=json.dumps(body),
            contentType='application/json'
        )
        
        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text']


# Keep the original TestCaseGenerator for backward compatibility
class TestCaseGenerator:
    def __init__(self):
        self.models = self._load_models()
        self.system_prompt = self._get_system_prompt()
        self._create_widgets()
        
    def _load_models(self) -> Dict[str, Any]:
        """Load available models from model_list.json"""
        with open('model_list.json', 'r') as f:
            return json.load(f)
    
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

## Input Information Required

To generate accurate, domain-specific evaluations, provide:

1. **Application Details**: Describe the primary objective, goals, and core functionality of your AI application. 
INPUT: {app_details}

2. **Key Features**: List the main features and capabilities your application provides to users.
INPUT: {key_features}

3. **Business Goals**: Specify what are the business goals of the application, how is going to be measured in terms of business value.
INPUT: {business_goals}

4. ***Number of Tests*: Specify the number of distincts tests to create
INPUT: {tests_amount}

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

The test cases MUST be all in {target_language}, respect the JSON keys and variables in original language, english on this case."""
    
    def _create_widgets(self):
        """Create all UI widgets"""
        self.app_details = widgets.Textarea(
            placeholder='e.g. Assist healthcare professionals and patients with medical-related tasks, access medical information, schedule appointments...',
            layout=widgets.Layout(width='100%', height='80px')
        )
        
        self.key_features = widgets.Textarea(
            placeholder='e.g. Patient record access, appointment scheduling, prescription management, lab results retrieval...',
            layout=widgets.Layout(width='100%', height='180px')
        )
        
        self.business_goals = widgets.Textarea(
            placeholder='e.g. Decrease Average Staff Turnover Rate, Reduce Average Cost per Treatment (ACT)...',
            layout=widgets.Layout(width='100%', height='180px')
        )
        
        self.language = widgets.Dropdown(
            options=['English', 'Spanish'],
            value='English',
            description='Target Language:'
        )
        
        self.model = widgets.Dropdown(
            options=list(self.models.keys()),
            value=list(self.models.keys())[0],
            description='Select Model:',
        )

        self.tests_amount = widgets.IntSlider(value=3, min=1, max=30)
        
        self.num_questions = widgets.IntSlider(value=2, min=1, max=10)
        
        self.generate_btn = widgets.Button(
            description='Generate Test Cases',
            button_style='primary',
            layout=widgets.Layout(width='200px', height='40px')
        )
        
        self.output = widgets.Output()
        
        self.generate_btn.on_click(self._on_generate)
    
    def _on_generate(self, b):
        """Handle generate button click"""
        with self.output:
            self.output.clear_output()
            
            if not all([self.app_details.value.strip(), self.key_features.value.strip(), self.business_goals.value.strip()]):
                print("❌ Please fill all required fields")
                return
            
            print("🔄 Generating test cases. Please wait, this may take time...")
            
            try:
                result = self.generate_test_cases(
                    self.app_details.value,
                    self.key_features.value,
                    self.business_goals.value,
                    self.language.value,
                    self.model.value,
                    self.tests_amount.value,
                    self.num_questions.value
                )
                
                print("✅ Test cases generated successfully!")
                
                # Display YAML with syntax highlighting and copy functionality
                from IPython.display import HTML, Javascript
                
                copy_button_html = f"""
                <div style="margin: 10px 0;">
                    <button onclick="copyToClipboard()" style="
                        background-color: #007cba; 
                        color: white; 
                        border: none; 
                        padding: 8px 16px; 
                        border-radius: 4px; 
                        cursor: pointer;
                        font-size: 14px;
                    ">📋 Copy YAML</button>
                </div>
                <pre id="yaml-content" style="
                    background-color: #f8f9fa; 
                    border: 1px solid #e9ecef; 
                    border-radius: 6px; 
                    padding: 16px; 
                    overflow-x: auto; 
                    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace; 
                    font-size: 13px; 
                    line-height: 1.4;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                "><code>{result.replace('<', '&lt;').replace('>', '&gt;')}</code></pre>
                
                <script>
                function copyToClipboard() {{
                    const content = document.getElementById('yaml-content').textContent;
                    navigator.clipboard.writeText(content).then(function() {{
                        const button = event.target;
                        const originalText = button.textContent;
                        button.textContent = '✅ Copied!';
                        button.style.backgroundColor = '#28a745';
                        setTimeout(function() {{
                            button.textContent = originalText;
                            button.style.backgroundColor = '#007cba';
                        }}, 2000);
                    }});
                }}
                </script>
                """
                
                display(HTML(copy_button_html))
                
            except Exception as e:
                print(f"❌ Error: {str(e)}")
    
    def display_ui(self):
        """Display all widgets"""
        display(widgets.HTML("<h2>1. Application description</h2>"))
        display(self.app_details)
        
        display(widgets.HTML("<h2>2. System Prompt or Application Details</h2>"))
        display(self.key_features)
        
        display(widgets.HTML("<h2>3. What are the key business metrics?</h2>"))
        display(self.business_goals)
        
        display(widgets.HTML("<h2>Target Language & Model Selection</h2>"))
        display(self.language)
        display(self.model)
        display(widgets.HTML("<h2># of distinct cases to generate</h2>"))
        display(self.tests_amount)
        
        display(widgets.HTML("<h2># of questions per case</h2>"))
        display(self.num_questions)
        
        display(widgets.HTML("<br>"))
        display(self.generate_btn)
        display(self.output)
        
    
    def generate_test_cases(self, app_details: str, key_features: str, 
                          business_goals: str, target_language: str, 
                          selected_model: str, tests_amount: int, num_questions: int) -> str:
        """Generate test cases using the selected model"""
        
        formatted_prompt = self.system_prompt.format(
            app_details=app_details,
            key_features=key_features,
            business_goals=business_goals,
            tests_amount=tests_amount,
            num_questions=num_questions,
            target_language=target_language
        )
        
        model_config = self.models[selected_model]
        
        bedrock = boto3.client(
            'bedrock-runtime',
            region_name=model_config['region_name']
        )
        
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4000,
            "temperature": model_config['temperature'],
            "messages": [{"role": "user", "content": formatted_prompt}]
        }
        
        response = bedrock.invoke_model(
            modelId=model_config['model_id'],
            body=json.dumps(body),
            contentType='application/json'
        )
        
        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text']
