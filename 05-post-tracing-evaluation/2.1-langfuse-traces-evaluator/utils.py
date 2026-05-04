import os
import json
import yaml
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from langfuse import Langfuse
from langfuse.api.client import FernLangfuse
from ragas.metrics import AspectCritic, RubricsScore
from ragas.dataset_schema import SingleTurnSample, MultiTurnSample, EvaluationDataset
from ragas import evaluate
from ragas.llms import LangchainLLMWrapper
from langchain_aws import ChatBedrock


class RagasEvaluator:
    """Main class for RAGAS evaluation with LangFuse integration"""
    
    def __init__(self, langfuse_config: Dict[str, str], model_config: Dict[str, Any]):
        """Initialize evaluator with LangFuse and model configuration"""
        self.langfuse = self._init_langfuse(langfuse_config)
        self.api_client = self._init_api_client(langfuse_config)
        self.evaluator_llm = self._init_llm(model_config)
        
    def _init_langfuse(self, config: Dict[str, str]) -> Langfuse:
        """Initialize LangFuse client"""
        return Langfuse(
            secret_key=config["secret_key"],
            public_key=config["public_key"],
            host=config["host"]
        )
    
    def _init_api_client(self, config: Dict[str, str]) -> FernLangfuse:
        """Initialize LangFuse API client"""
        return FernLangfuse(
            base_url=config["host"],
            username=config["public_key"],
            password=config["secret_key"]
        )
    
    def _init_llm(self, model_config: Dict[str, Any]) -> LangchainLLMWrapper:
        """Initialize LLM for evaluation"""
        bedrock_llm = ChatBedrock(
            model_id=model_config["model_id"],
            region_name=model_config.get("region_name", "us-east-1")
        )
        return LangchainLLMWrapper(bedrock_llm)
    
    def load_metrics_config(self, config_path: str) -> Dict[str, List]:
        """Load metrics configuration from YAML file"""
        with open(config_path, 'r') as file:
            return yaml.safe_load(file)
    
    def create_metrics(self, metrics_config: Dict[str, List]) -> List:
        """Create RAGAS metrics from configuration"""
        metrics = []
        
        # Create AspectCritic metrics
        for critic_config in metrics_config.get("aspect_critics", []):
            metric = AspectCritic(
                name=critic_config["name"],
                llm=self.evaluator_llm,
                definition=critic_config["definition"]
            )
            metrics.append(metric)
        
        # Create RubricsScore metrics
        for rubric_config in metrics_config.get("rubric_scores", []):
            metric = RubricsScore(
                rubrics=rubric_config["rubrics"],
                llm=self.evaluator_llm,
                name=rubric_config["name"]
            )
            metrics.append(metric)
        
        return metrics


class LangFuseTraceExtractor:
    """Class for extracting and processing LangFuse traces"""
    
    def __init__(self, api_client: FernLangfuse):
        self.api_client = api_client
    
    def fetch_traces(self, batch_size: int = 10, lookback_hours: int = 24, tags: Optional[List[str]] = None) -> List:
        """Fetch traces from LangFuse based on specified criteria"""
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=lookback_hours)
        print(f"Fetching traces from {start_time} to {end_time}")
        
        try:
            traces_response = self.api_client.trace.list(
                limit=batch_size,
                from_timestamp=start_time,
                to_timestamp=end_time
            )
            
            traces = []
            if hasattr(traces_response, 'data'):
                traces = traces_response.data
            elif isinstance(traces_response, list):
                traces = traces_response
            else:
                traces = [traces_response] if traces_response else []
                
            if not traces:
                print("No traces found with time filter, trying without time constraints...")
                traces_response = self.api_client.trace.list(limit=batch_size)
                traces = traces_response.data if hasattr(traces_response, 'data') else traces_response
                
        except Exception as e:
            print(f"Error fetching traces: {e}")
            try:
                traces_response = self.api_client.trace.list(limit=batch_size)
                traces = traces_response.data if hasattr(traces_response, 'data') else traces_response
            except Exception as e2:
                print(f"Fallback also failed: {e2}")
                traces = []
        
        print(f"Fetched {len(traces)} traces")
        return traces
    
    def extract_span_components(self, trace) -> Dict[str, Any]:
        """Extract user queries, agent responses, contexts and tool usage from trace"""
        user_inputs = []
        agent_responses = []
        retrieved_contexts = []
        tool_usages = []
        available_tools = []

        # Extract basic information from trace
        if hasattr(trace, 'input') and trace.input is not None:
            if isinstance(trace.input, dict) and 'args' in trace.input:
                if trace.input['args'] and len(trace.input['args']) > 0:
                    user_inputs.append(str(trace.input['args'][0]))
            elif isinstance(trace.input, str):
                user_inputs.append(trace.input)
            else:
                user_inputs.append(str(trace.input))

        if hasattr(trace, 'output') and trace.output is not None:
            if isinstance(trace.output, str):
                agent_responses.append(trace.output)
            else:
                agent_responses.append(str(trace.output))

        # Extract observations and tool usage
        try:
            observations_response = self.api_client.observations.get_many(trace_id=trace.id)
            
            observations = []
            if hasattr(observations_response, 'data'):
                observations = observations_response.data
            elif isinstance(observations_response, list):
                observations = observations_response
            else:
                observations = [observations_response] if observations_response else []

            for obs in observations:
                if hasattr(obs, 'name') and obs.name:
                    tool_name = str(obs.name)
                    tool_input = obs.input if hasattr(obs, 'input') and obs.input else None
                    tool_output = obs.output if hasattr(obs, 'output') and obs.output else None
                    tool_usages.append({
                        "name": tool_name,
                        "input": tool_input,
                        "output": tool_output
                    })
                    
                    if 'retrieve' in tool_name.lower() and tool_output:
                        retrieved_contexts.append(str(tool_output))
                        
                if hasattr(obs, 'metadata') and obs.metadata:
                    if 'attributes' in obs.metadata:
                        attributes = obs.metadata['attributes']
                        if 'agent.tools' in attributes:
                            try:
                                tools_str = attributes['agent.tools']
                                if isinstance(tools_str, str) and tools_str.startswith('['):
                                    available_tools = json.loads(tools_str)
                                elif isinstance(tools_str, list):
                                    available_tools = tools_str
                            except:
                                available_tools = [attributes['agent.tools']]
                                
        except Exception as e:
            print(f"Error fetching observations: {e}")

        return {
            "user_inputs": user_inputs,
            "agent_responses": agent_responses,
            "retrieved_contexts": retrieved_contexts,
            "tool_usages": tool_usages,
            "available_tools": available_tools
        }
    
    def process_traces(self, traces: List) -> Dict[str, Any]:
        """Process traces into samples for RAGAS evaluation"""
        single_turn_samples = []
        multi_turn_samples = []
        trace_sample_mapping = []
        
        for trace in traces:
            components = self.extract_span_components(trace)
            
            tool_info = ""
            if components["tool_usages"]:
                tool_info = "Tools used: " + ", ".join([t["name"] for t in components["tool_usages"] if "name" in t])
                
            if components["user_inputs"]:
                if components["retrieved_contexts"]:
                    single_turn_samples.append(
                        SingleTurnSample(
                            user_input=components["user_inputs"][0],
                            response=components["agent_responses"][0] if components["agent_responses"] else "",
                            retrieved_contexts=components["retrieved_contexts"],
                            metadata={
                                "tool_usages": components["tool_usages"],
                                "available_tools": components["available_tools"],
                                "tool_info": tool_info
                            }
                        )
                    )
                    trace_sample_mapping.append({
                        "trace_id": trace.id, 
                        "type": "single_turn", 
                        "index": len(single_turn_samples)-1
                    })
                else:
                    messages = []
                    for i in range(max(len(components["user_inputs"]), len(components["agent_responses"]))):
                        if i < len(components["user_inputs"]):
                            messages.append({"role": "user", "content": components["user_inputs"][i]})
                        if i < len(components["agent_responses"]):
                            messages.append({
                                "role": "assistant", 
                                "content": components["agent_responses"][i] + "\n\n" + tool_info
                            })
                    
                    multi_turn_samples.append(
                        MultiTurnSample(
                            user_input=messages,
                            metadata={
                                "tool_usages": components["tool_usages"],
                                "available_tools": components["available_tools"]
                            }
                        )
                    )
                    trace_sample_mapping.append({
                        "trace_id": trace.id, 
                        "type": "multi_turn", 
                        "index": len(multi_turn_samples)-1
                    })
        
        return {
            "single_turn_samples": single_turn_samples,
            "multi_turn_samples": multi_turn_samples,
            "trace_sample_mapping": trace_sample_mapping
        }


class RagasEvaluationRunner:
    """Class for running RAGAS evaluations and managing results"""
    
    def __init__(self, langfuse_client: Langfuse):
        self.langfuse = langfuse_client
    
    def evaluate_samples(self, samples: List, metrics: List, sample_type: str = "multi_turn") -> pd.DataFrame:
        """Evaluate samples with RAGAS metrics"""
        if not samples:
            print(f"No {sample_type} samples to evaluate")
            return pd.DataFrame()
        
        print(f"Evaluating {len(samples)} {sample_type} samples")
        dataset = EvaluationDataset(samples=samples)
        results = evaluate(dataset=dataset, metrics=metrics)
        return results.to_pandas()
    
    def push_scores_to_langfuse(self, results_df: pd.DataFrame, trace_sample_mapping: List[Dict], sample_type: str):
        """Push evaluation scores back to LangFuse"""
        for mapping in trace_sample_mapping:
            if mapping["type"] == sample_type:
                sample_index = mapping["index"]
                trace_id = mapping["trace_id"]
                
                if sample_index < len(results_df):
                    for metric_name in results_df.columns:
                        if metric_name not in ['user_input']:
                            try:
                                metric_value = float(results_df.iloc[sample_index][metric_name])
                                if pd.isna(metric_value):
                                    metric_value = 0.0
                                
                                self.langfuse.create_score(
                                    trace_id=trace_id,
                                    name=metric_name,
                                    value=metric_value
                                )
                                print(f"Added score {metric_name}={metric_value} to trace {trace_id}")
                            except Exception as e:
                                print(f"Error adding score: {e}")
                                try:
                                    self.langfuse.score(
                                        trace_id=trace_id,
                                        name=metric_name,
                                        value=metric_value
                                    )
                                    print(f"Added score {metric_name}={metric_value} to trace {trace_id} (fallback)")
                                except Exception as e2:
                                    print(f"Both scoring methods failed: {e2}")


class CSVExporter:
    """Class for exporting evaluation results to CSV"""
    
    @staticmethod
    def save_results(results_df: pd.DataFrame, output_dir: str = "evaluation_results", prefix: str = "evaluation") -> str:
        """Save evaluation results to CSV file"""
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}.csv"
        filepath = os.path.join(output_dir, filename)
        
        if not results_df.empty:
            results_df.to_csv(filepath, index=False)
            print(f"Results saved to {filepath}")
            return filepath
        else:
            print("No results to save")
            return ""


def load_model_config(model_list_path: str, model_name: str) -> Dict[str, Any]:
    """Load model configuration from JSON file"""
    with open(model_list_path, 'r') as file:
        model_list = json.load(file)
    
    if model_name not in model_list:
        raise ValueError(f"Model '{model_name}' not found in model list")
    
    return model_list[model_name]


def print_metric_summary(df: pd.DataFrame, title: str, performance_range: List[float] = [0, 1]) -> None:
    """Print formatted metric summary with dynamic performance evaluation ranges
    
    Args:
        df: DataFrame with evaluation results
        title: Title for the summary section
        performance_range: [min, max] range for performance evaluation (default: [0, 1])
    """
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")
    print(f"📊 Samples Evaluated: {len(df)}")
    
    numeric_cols = [col for col in df.select_dtypes(include=['number']).columns if col != 'user_input']
    
    if numeric_cols:
        print(f"\n📈 METRIC SCORES SUMMARY")
        print("-" * 40)
        
        # Calculate dynamic thresholds based on provided range
        range_span = performance_range[1] - performance_range[0]
        excellent_threshold = performance_range[0] + (range_span * 0.8)
        good_threshold = performance_range[0] + (range_span * 0.6)
        needs_improvement_threshold = performance_range[0] + (range_span * 0.4)
        
        for col in numeric_cols:
            scores = df[col].dropna()
            if len(scores) > 0:
                mean_val = scores.mean()
                min_val = scores.min()
                max_val = scores.max()
                
                # Determine performance indicator based on dynamic range
                if mean_val >= excellent_threshold:
                    indicator = "🟢 EXCELLENT"
                elif mean_val >= good_threshold:
                    indicator = "🟡 GOOD"
                elif mean_val >= needs_improvement_threshold:
                    indicator = "🟠 NEEDS IMPROVEMENT"
                else:
                    indicator = "🔴 POOR"
                
                print(f"\n{col}:")
                print(f"  Mean: {mean_val:.3f} | Min: {min_val:.3f} | Max: {max_val:.3f} | {indicator}")


def run_evaluation_pipeline(
    langfuse_config: Dict[str, str],
    model_name: str,
    lookback_hours: int = 24,
    batch_size: int = 10,
    tags: Optional[List[str]] = None,
    save_csv: bool = False,
    metrics_config_path: str = "metrics_config.yaml",
    model_list_path: str = "model_list.json"
) -> Dict[str, Any]:
    """Main function to run the complete evaluation pipeline"""
    
    # Load model configuration
    model_config = load_model_config(model_list_path, model_name)
    
    # Initialize evaluator
    evaluator = RagasEvaluator(langfuse_config, model_config)
    
    # Load metrics configuration and create metrics
    metrics_config = evaluator.load_metrics_config(metrics_config_path)
    metrics = evaluator.create_metrics(metrics_config)
    
    # Initialize trace extractor
    trace_extractor = LangFuseTraceExtractor(evaluator.api_client)
    
    # Fetch and process traces
    traces = trace_extractor.fetch_traces(batch_size, lookback_hours, tags)
    if not traces:
        print("No traces found. Exiting.")
        return {}
    
    processed_data = trace_extractor.process_traces(traces)
    
    # Initialize evaluation runner
    eval_runner = RagasEvaluationRunner(evaluator.langfuse)
    
    # Evaluate samples
    results = {}
    if processed_data["multi_turn_samples"]:
        conv_df = eval_runner.evaluate_samples(
            processed_data["multi_turn_samples"], 
            metrics, 
            "multi_turn"
        )
        eval_runner.push_scores_to_langfuse(conv_df, processed_data["trace_sample_mapping"], "multi_turn")
        results["conversation_results"] = conv_df
        
        if save_csv and not conv_df.empty:
            CSVExporter.save_results(conv_df, prefix="conversation_evaluation")
    
    if processed_data["single_turn_samples"]:
        single_df = eval_runner.evaluate_samples(
            processed_data["single_turn_samples"], 
            metrics, 
            "single_turn"
        )
        eval_runner.push_scores_to_langfuse(single_df, processed_data["trace_sample_mapping"], "single_turn")
        results["single_turn_results"] = single_df
        
        if save_csv and not single_df.empty:
            CSVExporter.save_results(single_df, prefix="single_turn_evaluation")
    
    return results
