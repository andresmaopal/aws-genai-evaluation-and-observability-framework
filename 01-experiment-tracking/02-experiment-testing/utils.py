"""
Fixed LiteLLM Unified Tester with proper Langfuse V3 integration and context management
"""

import os
import json
import yaml
import time
import uuid
import asyncio
import pandas as pd
import csv
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from strands import Agent
from strands.models.litellm import LiteLLMModel

class UnifiedTester:
    """Unified testing framework for LiteLLM models with proper Langfuse V3 tracing"""
    
    def __init__(self):
        """Initialize the UnifiedTester"""
        self.model_configs = self._load_model_configs()
        
    def _load_model_configs(self) -> Dict[str, Dict]:
        """Load model configurations from bedrock_model_list.json"""
        try:
            with open('bedrock_model_list.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print("⚠️ bedrock_model_list.json not found, using empty config")
            return {}
    
    def run_test(self, models: List[str], system_prompts: List[str], queries: str,
                 prompts_dict: Dict[str, str], tool: List = None, 
                 trace_attributes: Optional[Dict[str, Any]] = None,
                 save_to_csv: bool = True) -> List[Dict[str, Any]]:
        """Run unified tests with proper Langfuse V3 tracing"""
        
        # Setup Langfuse V3 if trace_attributes provided
        langfuse_client = None
        
        if trace_attributes:
            langfuse_client = self._setup_langfuse_v3(trace_attributes)
        
        results = []
        total_tests = len(models) * len(system_prompts)
        
        print(f"\n🚀 Starting LiteLLM Test Suite")
        print(f"📊 Total combinations to test: {total_tests}")
        print(f"🤖 Models: {models}")
        print(f"📝 Prompts: {system_prompts}")
        print(f"❓ Queries: 1 query(ies)")
        print("=" * 80)
        
        # Run tests within Langfuse context if available
        if langfuse_client:
            trace_name = trace_attributes.get("langfuse.trace.name", "LiteLLM Test Suite")
            
            with langfuse_client.start_as_current_span(
                name=trace_name,
                input={
                    "test_type": "litellm_unified_test",
                    "session_id": trace_attributes.get("session.id"),
                    "user_id": trace_attributes.get("user.id"),
                    "models": models,
                    "prompts": system_prompts
                },
                metadata={
                    "environment": trace_attributes.get("langfuse.environment", "development"),
                    "tags": trace_attributes.get("langfuse.tags", []),
                    "framework": "Strands Agents LiteLLM",
                    "version": "1.0"
                }
            ):
                results = self._run_tests_internal(models, system_prompts, queries, prompts_dict, tool, trace_attributes, langfuse_client)
                
                # Update trace with results
                langfuse_client.update_current_trace(
                    output={
                        "total_tests": len(results),
                        "successful_tests": sum(1 for r in results if r["success"]),
                        "results_summary": results
                    }
                )
                
                # Score the trace
                success_rate = sum(1 for r in results if r["success"]) / len(results) if results else 0
                langfuse_client.score_current_trace(
                    name="test_suite_success_rate",
                    value=success_rate,
                    comment=f"Test suite completed with {success_rate:.1%} success rate"
                )
                
                langfuse_client.flush()
                print("✅ Langfuse trace finalized")
        else:
            results = self._run_tests_internal(models, system_prompts, queries, prompts_dict, tool, trace_attributes, None)
        
        print(f"\n🎉 Test Suite Completed! {len(results)} results generated.")
        
        if save_to_csv:
            self._save_results_to_csv(results)
        
        return results
    
    def _setup_langfuse_v3(self, trace_attributes: Dict[str, Any]):
        """Setup Langfuse V3 client"""
        try:
            from langfuse import Langfuse
            
            langfuse_client = Langfuse(
                public_key=os.environ.get("LANGFUSE_PUBLIC_KEY"),
                secret_key=os.environ.get("LANGFUSE_SECRET_KEY"),
                host=os.environ.get("LANGFUSE_HOST")
            )
            
            print("✅ Langfuse V3 tracing enabled")
            return langfuse_client
            
        except Exception as e:
            print(f"⚠️ Langfuse setup failed: {str(e)}")
            return None
    
    def _run_tests_internal(self, models: List[str], system_prompts: List[str], queries: str,
                           prompts_dict: Dict[str, str], tool: List = None,
                           trace_attributes: Optional[Dict[str, Any]] = None,
                           langfuse_client=None) -> List[Dict[str, Any]]:
        """Internal method to run tests"""
        results = []
        total_tests = len(models) * len(system_prompts)
        test_counter = 0
        
        for model_endpoint in models:
            for prompt_name in system_prompts:
                test_counter += 1
                print(f"\n[{test_counter}/{total_tests}] Testing: {model_endpoint} | {prompt_name}")
                print(f"Query: {queries}")
                print("-" * 60)
                
                result = self._execute_single_test(
                    model_endpoint, prompt_name, queries, prompts_dict, tool, 
                    trace_attributes, langfuse_client
                )
                results.append(result)
        
        return results
    
    def _execute_single_test(self, model_endpoint: str, prompt_name: str, query: str,
                           prompts_dict: Dict[str, str], tool: List = None,
                           trace_attributes: Optional[Dict[str, Any]] = None,
                           langfuse_client=None) -> Dict[str, Any]:
        """Execute a single test"""
        
        start_time = time.time()
        
        try:
            region = self._get_model_region(model_endpoint)
            print(f"🔧 Using AWS region: {region}")
            
            # Create agent
            agent = self._create_litellm_agent(
                model_endpoint, prompt_name, prompts_dict, tool, trace_attributes
            )
            
            # Execute test using synchronous call with error handling for streaming issues
            try:
                response = agent(query)
                
                # Handle both streaming and non-streaming responses
                if hasattr(response, 'content'):
                    response_text = response.content
                elif hasattr(response, 'choices') and len(response.choices) > 0:
                    # Handle LiteLLM ModelResponse format
                    response_text = response.choices[0].message.content
                else:
                    response_text = str(response)
                    
            except Exception as streaming_error:
                # If streaming fails, try direct LiteLLM call with stream=False
                if "async for" in str(streaming_error) or "streaming" in str(streaming_error).lower():
                    print("⚠️ Streaming issue detected, trying direct LiteLLM call with stream=False")
                    
                    import litellm
                    system_prompt = prompts_dict.get(prompt_name, f"You are a helpful assistant. (Prompt: {prompt_name})")
                    
                    messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": query}
                    ]
                    
                    direct_response = litellm.completion(
                        model=model_endpoint,
                        messages=messages,
                        stream=False,
                        temperature=0.1,
                        max_tokens=4000
                    )
                    
                    response_text = direct_response.choices[0].message.content
                    response = direct_response  # Fix: Update response variable
                    print("✅ Direct LiteLLM call successful")
                else:
                    raise streaming_error
            
            print(response_text)
            
            # Check for tool usage
            tools_used = []
            if hasattr(response, 'tool_calls') and response.tool_calls:
                for i, tool_call in enumerate(response.tool_calls, 1):
                    tool_name = tool_call.get('name', 'Unknown')
                    tools_used.append(tool_name)
                    print(f"Tool #{i}: {tool_name}")
            
            end_time = time.time()
            response_time = end_time - start_time
            
            print(f"✅ SUCCESS | Time: {response_time:.2f}s")
            
            return {
                "test_id": f"{model_endpoint}_{prompt_name}_{int(time.time())}",
                "model": model_endpoint,
                "prompt": prompt_name,
                "query": query,
                "response": response_text,
                "tools_used": tools_used,
                "response_time": response_time,
                "success": True,
                "error": None,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            end_time = time.time()
            response_time = end_time - start_time
            
            print(f"❌ FAILED | Error: {str(e)} | Time: {response_time:.2f}s")
            
            return {
                "test_id": f"{model_endpoint}_{prompt_name}_{int(time.time())}",
                "model": model_endpoint,
                "prompt": prompt_name,
                "query": query,
                "response": None,
                "tools_used": [],
                "response_time": response_time,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def _create_litellm_agent(self, model_endpoint: str, prompt_name: str,
                             prompts_dict: Dict[str, str], tool: List = None,
                             trace_attributes: Optional[Dict[str, Any]] = None) -> Agent:
        """Create an agent with LiteLLM model"""
        
        # Create model without stream parameter to let Strands handle it
        model = LiteLLMModel(model_id=model_endpoint)
        system_prompt = prompts_dict.get(prompt_name, f"You are a helpful assistant. (Prompt: {prompt_name})")
        
        agent_kwargs = {
            "model": model,
            "system_prompt": system_prompt
        }
        
        if tool:
            agent_kwargs["tools"] = tool
        
        if trace_attributes:
            import copy
            dynamic_trace_attributes = copy.deepcopy(trace_attributes)
            
            if "langfuse.tags" in dynamic_trace_attributes:
                original_tags = [tag for tag in dynamic_trace_attributes["langfuse.tags"] 
                               if not tag.startswith("Model-")]
                dynamic_trace_attributes["langfuse.tags"] = original_tags + [f"Model-{model_endpoint}"]
            else:
                dynamic_trace_attributes["langfuse.tags"] = [f"Model-{model_endpoint}"]
            
            agent_kwargs["trace_attributes"] = dynamic_trace_attributes
        
        return Agent(**agent_kwargs)
    
    def _get_model_region(self, model_endpoint: str) -> str:
        """Get AWS region for model endpoint"""
        model_name = model_endpoint.replace("bedrock/", "")
        
        for config_name, config in self.model_configs.items():
            if config.get("model_id", "").replace("bedrock/", "") == model_name:
                return config.get("region_name", "us-east-1")
        
        return "us-east-1"
    
    def _save_results_to_csv(self, results: List[Dict]):
        """Save results to CSV file"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"test_results/test_results_{timestamp}.csv"
            
            os.makedirs("test_results", exist_ok=True)
            
            df = pd.DataFrame(results)
            df.to_csv(filename, index=False)
            
            print(f"📁 Results automatically saved to {filename}")
            
        except Exception as e:
            print(f"⚠️ Error saving results to CSV: {str(e)}")
    
    def display_results(self, results: List[Dict]):
        """Display test results in a human-readable format"""
        if not results:
            print("No results to display")
            return
        
        total_tests = len(results)
        successful_tests = sum(1 for r in results if r["success"])
        failed_tests = total_tests - successful_tests
        
        response_times = [r["response_time"] for r in results if r["response_time"] is not None]
        avg_time = sum(response_times) / len(response_times) if response_times else 0
        min_time = min(response_times) if response_times else 0
        max_time = max(response_times) if response_times else 0
        
        print(f"\n📈 RESULTS SUMMARY")
        print("=" * 50)
        print(f"Total Tests: {total_tests}")
        print(f"✅ Successful: {successful_tests} ({successful_tests/total_tests*100:.1f}%)")
        print(f"❌ Failed: {failed_tests} ({failed_tests/total_tests*100:.1f}%)")
        print(f"⏱️  Response Times - Avg: {avg_time:.2f}s | Min: {min_time:.2f}s | Max: {max_time:.2f}s")
        
        # Model performance
        print(f"\n🤖 MODEL PERFORMANCE")
        print("=" * 50)
        model_stats = {}
        for result in results:
            model = result["model"]
            if model not in model_stats:
                model_stats[model] = {"success": 0, "total": 0, "times": []}
            
            model_stats[model]["total"] += 1
            if result["success"]:
                model_stats[model]["success"] += 1
            if result["response_time"] is not None:
                model_stats[model]["times"].append(result["response_time"])
        
        for model, stats in model_stats.items():
            success_rate = stats["success"] / stats["total"] * 100 if stats["total"] > 0 else 0
            avg_time = sum(stats["times"]) / len(stats["times"]) if stats["times"] else 0
            print(f"{model:<50} | Success: {success_rate:5.1f}% | Avg Time: {avg_time:6.2f}s | Tests: {stats['total']}")
        
        # Prompt performance
        print(f"\n📝 PROMPT PERFORMANCE")
        print("=" * 50)
        prompt_stats = {}
        for result in results:
            prompt = result["prompt"]
            if prompt not in prompt_stats:
                prompt_stats[prompt] = {"success": 0, "total": 0, "times": []}
            
            prompt_stats[prompt]["total"] += 1
            if result["success"]:
                prompt_stats[prompt]["success"] += 1
            if result["response_time"] is not None:
                prompt_stats[prompt]["times"].append(result["response_time"])
        
        for prompt, stats in prompt_stats.items():
            success_rate = stats["success"] / stats["total"] * 100 if stats["total"] > 0 else 0
            avg_time = sum(stats["times"]) / len(stats["times"]) if stats["times"] else 0
            print(f"{prompt:<20} | Success: {success_rate:5.1f}% | Avg Time: {avg_time:6.2f}s | Tests: {stats['total']}")

    def run_evaluation(self, 
                      models: List[str], 
                      system_prompts: List[str], 
                      prompts_dict: Dict[str, str], 
                      tool: List = None,
                      test_cases_path: str = None,
                      langfuse_public_key: str = None,
                      langfuse_secret_key: str = None, 
                      langfuse_api_url: str = None,
                      save_to_csv: bool = True) -> List[Dict[str, Any]]:
        """
        Run evaluation using test cases from YAML file with LLM-as-judge evaluation.
        
        Args:
            models: List of model IDs to test
            system_prompts: List of prompt versions to test
            prompts_dict: Dictionary containing system prompts
            tool: List of tools to use
            test_cases_path: Path to YAML file containing test cases
            langfuse_public_key: Optional Langfuse public key for tracing
            langfuse_secret_key: Optional Langfuse secret key for tracing
            langfuse_api_url: Optional Langfuse API URL for tracing
            save_to_csv: Whether to save results to CSV (default: True)
            
        Returns: List of evaluation results
        """
        import yaml
        import re
        
        if not test_cases_path:
            raise ValueError("test_cases_path is required")
        
        # Load test cases from YAML
        try:
            with open(test_cases_path, 'r', encoding='utf-8') as f:
                test_cases = yaml.safe_load(f)
        except FileNotFoundError:
            print(f"⚠️ Test cases file not found: {test_cases_path}")
            return []
        except Exception as e:
            print(f"⚠️ Error loading test cases: {str(e)}")
            return []
        
        # Initialize Langfuse if credentials provided
        langfuse_client = None
        main_trace = None
        if langfuse_public_key and langfuse_secret_key and langfuse_api_url:
            try:
                from langfuse import Langfuse
                langfuse_client = Langfuse(
                    public_key=langfuse_public_key,
                    secret_key=langfuse_secret_key,
                    host=langfuse_api_url
                )
                
                # Create main trace for the entire evaluation (root span)
                main_trace = langfuse_client.start_span(
                    name="Agent Eval - " + (models[0] if models else 'Multiple Models'),
                    input={
                        "config_file": test_cases_path,
                        "evaluation_metadata": {
                            "models": models,
                            "system_prompts": system_prompts,
                            "test_cases": list(test_cases.keys()),
                            "total_combinations": len(models) * len(system_prompts) * len(test_cases),
                            "evaluation_timestamp": datetime.now().isoformat()
                        }
                    },
                    metadata={
                        "evaluation_framework": "Strands Agents Test Evaluator",
                        "version": "1.0",
                        "langfuse_version": "v3"
                    }
                )
                
                print("✅ Langfuse tracing enabled")
            except ImportError:
                print("⚠️ Langfuse not available, continuing without tracing")
        
        results = []
        total_combinations = len(models) * len(system_prompts) * len(test_cases)
        current_combination = 0
        
        print(f"\n🧪 Starting Test Case Evaluation")
        print(f"📊 Total combinations: {total_combinations}")
        print(f"🤖 Models: {models}")
        print(f"📝 Prompts: {system_prompts}")
        print(f"📋 Test Cases: {len(test_cases)} test case(s)")
        print("=" * 80)
        
        for model_name in models:
            for prompt_name in system_prompts:
                for test_name, test_data in test_cases.items():
                    current_combination += 1
                    print(f"\n[{current_combination}/{total_combinations}] Evaluating: {model_name} | {prompt_name} | {test_name}")
                    print("-" * 60)
                    
                    # Create evaluator agent for this combination
                    evaluator_agent = self._create_litellm_agent(model_name, prompt_name, prompts_dict, tool)
                    
                    # Create judge agent (using same model for simplicity)
                    judge_agent = self._create_litellm_judge_agent(model_name)
                    
                    # Run evaluation for this test case
                    eval_result = self._evaluate_test_case(
                        test_name, test_data, evaluator_agent, judge_agent, 
                        model_name, prompt_name, langfuse_client, main_trace
                    )
                    
                    results.append(eval_result)
                    
                    # Brief status
                    status = "✅ PASSED" if eval_result['passed'] else "❌ FAILED"
                    print(f"{status} | Score: {eval_result['score']:.2f}")
        
        print(f"\n🎉 Evaluation Completed! {len(results)} results generated.")
        
        # Finalize Langfuse main trace if available
        if main_trace and langfuse_client:
            try:
                # Calculate overall metrics
                total_tests = len(results)
                passed_tests = sum(1 for r in results if r['passed'])
                overall_score = float(passed_tests) / float(total_tests) if total_tests > 0 else 0.0
                overall_result = "PASS" if passed_tests == total_tests else "FAILED"
                
                # Update main trace with final results
                main_trace.update(
                    input={
                        "config_file": test_cases_path,
                        "evaluation_metadata": {
                            "models": models,
                            "system_prompts": system_prompts,
                            "test_cases": list(test_cases.keys()),
                            "total_combinations": len(models) * len(system_prompts) * len(test_cases),
                            "evaluation_timestamp": datetime.now().isoformat()
                        }
                    },
                    output={
                        "overall_result": overall_result,
                        "overall_results": {
                            "total_tests": total_tests,
                            "passed_tests": passed_tests,
                            "pass_rate": f"{(overall_score * 100):.1f}%",
                            "overall_passed": passed_tests == total_tests
                        }
                    }
                )
                
                # Update main trace with final results
                main_trace.update_trace(
                    tags=[f"Agent-Eval-{models[0] if models else 'Multiple-Models'}"],
                    input={
                        "Eval File": test_cases_path
                    },
                    output={
                        "Test Passed": str(passed_tests == total_tests).upper()
                    }
                )
                
                # End main trace
                main_trace.end()
                
                # Add overall score
                langfuse_client.create_score(
                    trace_id=main_trace.trace_id,
                    observation_id=main_trace.id,
                    name="overall_evaluation",
                    value=overall_score,
                    data_type="NUMERIC",
                    comment=f"Overall evaluation: {passed_tests}/{total_tests} tests passed ({(overall_score * 100):.1f}%)"
                )
                
                # Flush data
                langfuse_client.flush()
                print(f"✅ Langfuse trace finalized: {main_trace.trace_id}")
                
            except Exception as e:
                print(f"⚠️ Error finalizing Langfuse trace: {str(e)}")
        
        # Display summary
        self._display_evaluation_summary(results)
        
        # Save to CSV if requested
        if save_to_csv:
            self._export_evaluation_results(results)
        
        return results

    def _create_litellm_judge_agent(self, model_name: str) -> Agent:
        """Create a judge agent for evaluation using LiteLLM"""
        
        judge_system_prompt = """You are an expert quality assurance engineer evaluating an agent's response to a user question.

Your job is to analyze the user question, agent response, and expected result to determine if the agent's response meets the expected criteria.

You MUST classify the response into one of these categories:
- PASSED: The agent's response meets or exceeds the expected result criteria
- FAILED: The agent's response does not meet the expected result criteria

CRITICAL: You MUST format your response exactly as follows:

<analysis>
[Your one paragraph detailed analysis of whether the response meets the criteria]
</analysis>

<category>PASSED</category>

OR

<category>FAILED</category>

Do not include any other text outside of these tags."""

        model = LiteLLMModel(model_id=model_name)
        return Agent(model=model, system_prompt=judge_system_prompt)

    def _evaluate_test_case(self, test_name: str, test_data: Dict, 
                           evaluator_agent: Agent, judge_agent: Agent,
                           model_name: str, prompt_name: str,
                           langfuse_client=None, main_trace=None) -> Dict[str, Any]:
        """Evaluate a single test case with multi-turn conversation"""
        """Evaluate a single test case with multi-turn conversation"""
        
        # Extract questions and expected results
        questions = []
        expected_results = []
        
        for question_key in sorted(test_data.keys()):
            if question_key.startswith('question_'):
                questions.append(test_data[question_key]['question'])
                expected_results.append(test_data[question_key]['expected_results'])
        
        conversation_history = []
        question_results = []
        
        print(f"📝 Test Case: {test_name}")
        
        # Process each question as a separate turn
        for i, (question, expected_result) in enumerate(zip(questions, expected_results)):
            print(f"\n  Turn {i + 1}: {question[:60]}{'...' if len(question) > 60 else ''}")
            
            try:
                # Get agent response
                start_time = time.time()
                response = evaluator_agent(question)
                end_time = time.time()
                
                # Extract response text
                if hasattr(response, 'message') and 'content' in response.message:
                    agent_response = response.message['content']
                else:
                    agent_response = str(response)
                
                conversation_history.append(("USER", question))
                conversation_history.append(("AGENT", agent_response))
                
                # Evaluate this question-answer pair
                print(f"\n{'='*50}")
                print("AGENT EVALUATION RESULTS")
                print(f"{'='*50}")
                eval_category, reasoning = self._judge_response(
                    judge_agent, expected_result, question, agent_response
                )
                print(f"{'='*50}")
                
                question_passed = eval_category.strip().upper() == "PASSED"
                
                question_result = {
                    "question_number": i + 1,
                    "question": question,
                    "expected_result": expected_result,
                    "agent_response": agent_response,
                    "passed": question_passed,
                    "reasoning": reasoning,
                    "response_time": end_time - start_time
                }
                question_results.append(question_result)
                
                status = "✅" if question_passed else "❌"
                print(f"{status} Question {i + 1}")
                
            except Exception as e:
                print(f"    ❌ Error in question {i + 1}: {str(e)}")
                question_result = {
                    "question_number": i + 1,
                    "question": question,
                    "expected_result": expected_result,
                    "agent_response": f"Error: {str(e)}",
                    "passed": False,
                    "reasoning": f"Error occurred: {str(e)}",
                    "response_time": 0
                }
                question_results.append(question_result)
        
        # Calculate overall test result
        passed_questions = sum(1 for r in question_results if r['passed'])
        total_questions = len(question_results)
        overall_passed = passed_questions == total_questions
        score = passed_questions / total_questions if total_questions > 0 else 0.0
        
        # Create evaluation result
        eval_result = {
            "test_id": f"{model_name}_{prompt_name}_{test_name}",
            "model": model_name,
            "prompt": prompt_name,
            "test_name": test_name,
            "passed": overall_passed,
            "score": score,
            "passed_questions": passed_questions,
            "total_questions": total_questions,
            "conversation": conversation_history,
            "question_results": question_results,
            "timestamp": datetime.now().isoformat()
        }
        
        # Add Langfuse tracing if available - create spans for each question
        if langfuse_client and main_trace:
            try:
                
                # Create spans for each question directly as children of main trace (like reference)
                for i, question_result in enumerate(question_results):
                    question_span = main_trace.start_span(
                        name=f"Question: {test_name} - Q{i+1}",
                        input={
                            "test_name": test_name,
                            "question_id": f"{test_name}_q{i+1}",
                            "question": question_result['question'],
                            "expected_result": question_result['expected_result']
                        },
                        output={
                            "agent_response": question_result['agent_response'],
                            "question_passed": question_result['passed'],
                            "reasoning": question_result['reasoning']
                        },
                        metadata={
                            "question_number": i + 1,
                            "test_passed": overall_passed,
                            "evaluation_category": "A" if question_result['passed'] else "B",
                            "test_name": test_name
                        },
                        level="DEFAULT"
                    )
                    
                    # Update and end the question span
                    question_span.update(
                        output={
                            "agent_response": question_result['agent_response'],
                            "question_passed": question_result['passed'],
                            "reasoning": question_result['reasoning']
                        }
                    )
                    question_span.end()
                    
                    # Add score to the question span
                    langfuse_client.create_score(
                        trace_id=main_trace.trace_id,
                        observation_id=question_span.id,
                        name="question_evaluation",
                        value=1.0 if question_result['passed'] else 0.0,
                        data_type="NUMERIC",
                        comment=question_result['reasoning'] or "No reasoning provided"
                    )

                
                print(f"  ✅ Created {len(question_results)} question spans for test: {test_name}")
                
            except Exception as e:
                print(f"⚠️ Langfuse tracing error: {str(e)}")
                import traceback
                traceback.print_exc()
        
        return eval_result

    def _judge_response(self, judge_agent: Agent, expected_result: str, 
                       question: str, agent_response: str) -> Tuple[str, str]:
        """Use judge agent to evaluate response"""
        
        prompt = f"""Here is the evaluation scenario:

<question>
{question}
</question>

<agent_response>
{agent_response}
</agent_response>

<expected_result>
{expected_result}
</expected_result>

Evaluate whether the agent's response meets the expected result criteria or not."""
        
        try:
            response = judge_agent(prompt)
            
            # Handle different response formats
            if hasattr(response, 'message') and 'content' in response.message:
                completion = response.message['content']
            else:
                completion = str(response)
            
            # Handle list responses (Bedrock sometimes returns lists)
            if isinstance(completion, list):
                if len(completion) > 0 and isinstance(completion[0], dict) and 'text' in completion[0]:
                    completion = completion[0]['text']
                else:
                    completion = str(completion)
            
            # Extract category and reasoning from XML tags
            category, reasoning = self._extract_xml_content(completion)
            
            return category, reasoning
            
        except Exception as e:
            return "FAILED", f"Evaluation error: {str(e)}"

    def _extract_xml_content(self, text: str) -> Tuple[str, str]:
        """Extract content from XML tags"""
        import re
        
        # Ensure text is a string
        if not isinstance(text, str):
            text = str(text)
        
        # Extract analysis text from <analysis> tags
        analysis_match = re.search(r'<analysis>(.*?)</analysis>', text, re.DOTALL | re.IGNORECASE)
        analysis_text = analysis_match.group(1).strip() if analysis_match else "Analysis complete"
        
        # Simple, bulletproof extraction using string matching
        if '<category>PASSED</category>' in text:
            return "PASSED", analysis_text
        elif '<category>FAILED</category>' in text:
            return "FAILED", analysis_text
        elif '<category>A</category>' in text:
            return "PASSED", analysis_text  
        elif '<category>B</category>' in text:
            return "FAILED", analysis_text
        else:
            # Fallback for any edge cases
            if 'PASSED' in text.upper():
                return "PASSED", analysis_text
            else:
                return "FAILED", analysis_text

    def _display_evaluation_summary(self, results: List[Dict[str, Any]]) -> None:
        """Display evaluation results summary"""
        if not results:
            print("No evaluation results to display.")
            return
        
        total_tests = len(results)
        passed_tests = sum(1 for r in results if r['passed'])
        avg_score = sum(r['score'] for r in results) / total_tests
        
        print(f"\n📊 EVALUATION SUMMARY")
        print(f"{'='*50}")
        print(f"Total Test Cases: {total_tests}")
        print(f"✅ Passed: {passed_tests} ({passed_tests/total_tests*100:.1f}%)")
        print(f"❌ Failed: {total_tests - passed_tests} ({(total_tests - passed_tests)/total_tests*100:.1f}%)")
        print(f"📈 Average Score: {avg_score:.2f}")
        
        # Group by model and prompt
        by_model = defaultdict(list)
        by_prompt = defaultdict(list)
        
        for result in results:
            by_model[result['model']].append(result)
            by_prompt[result['prompt']].append(result)
        
        # Model performance
        print(f"\n🤖 MODEL PERFORMANCE")
        print(f"{'='*50}")
        for model, model_results in by_model.items():
            model_avg_score = sum(r['score'] for r in model_results) / len(model_results)
            model_passed = sum(1 for r in model_results if r['passed'])
            print(f"{model:20} | Score: {model_avg_score:5.2f} | Passed: {model_passed}/{len(model_results)}")
        
        # Prompt performance
        print(f"\n📝 PROMPT PERFORMANCE")
        print(f"{'='*50}")
        for prompt, prompt_results in by_prompt.items():
            prompt_avg_score = sum(r['score'] for r in prompt_results) / len(prompt_results)
            prompt_passed = sum(1 for r in prompt_results if r['passed'])
            print(f"{prompt:20} | Score: {prompt_avg_score:5.2f} | Passed: {prompt_passed}/{len(prompt_results)}")

    def _export_evaluation_results(self, results: List[Dict[str, Any]], 
                                  base_filename: str = "evaluation_results") -> None:
        """Export evaluation results to CSV"""
        import os
        
        # Create evaluation_results directory if it doesn't exist
        eval_dir = "evaluation_results"
        os.makedirs(eval_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(eval_dir, f"{base_filename}_{timestamp}.csv")
        
        if not results:
            print("No evaluation results to export.")
            return
        
        # Flatten results to include individual question data with analysis
        flattened_results = []
        for result in results:
            question_results = result.get('question_results', [])
            for q_result in question_results:
                flattened_results.append({
                    'test_id': result.get('test_id', ''),
                    'model': result.get('model', ''),
                    'prompt': result.get('prompt', ''),
                    'test_name': result.get('test_name', ''),
                    'question_number': q_result.get('question_number', ''),
                    'question': q_result.get('question', ''),
                    'agent_response': q_result.get('agent_response', ''),
                    'analysis_text': q_result.get('reasoning', ''),
                    'passed': q_result.get('passed', False),
                    'response_time': q_result.get('response_time', 0),
                    'timestamp': result.get('timestamp', '')
                })
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'test_id', 'model', 'prompt', 'test_name', 'question_number', 'question',
                'agent_response', 'analysis_text', 'passed', 'response_time', 'timestamp'
            ])
            writer.writeheader()
            for row in flattened_results:
                writer.writerow(row)
        
        print(f"📁 Evaluation results exported to {filename}")
