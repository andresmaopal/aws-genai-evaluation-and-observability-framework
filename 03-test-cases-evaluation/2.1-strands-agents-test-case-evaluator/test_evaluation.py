#!/usr/bin/env python3
"""
Test script to verify the evaluation functionality
"""

import yaml
from utils import UnifiedTester
from strands import tool

# Simple test tool
@tool
def TestTool(query: str) -> str:
    """A simple test tool that returns a basic response"""
    return f"Test response for: {query}"

def main():
    print("🧪 Testing Evaluation Functionality")
    print("=" * 50)
    
    # Initialize tester
    tester = UnifiedTester()
    
    # Load configuration
    with open('config_experiments.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    prompts = config['system_prompts']
    
    # Create simple tool list
    tool_list = [TestTool]
    
    try:
        # Test the evaluation function with a small subset
        print("🚀 Running evaluation test...")
        
        results = tester.run_evaluation(
            models=["claude-4-sonnet"],  # Single model for testing
            system_prompts=["version1"],  # Single prompt
            prompts_dict=prompts,
            tool=tool_list,
            test_cases_path="config_evaluation.yaml",
            save_to_csv=False  # Don't save during testing
        )
        
        print(f"✅ Evaluation completed successfully!")
        print(f"📊 Generated {len(results)} evaluation results")
        
        # Display first result as example
        if results:
            first_result = results[0]
            print(f"\n📝 Example Result:")
            print(f"  Test: {first_result['test_name']}")
            print(f"  Model: {first_result['model']}")
            print(f"  Passed: {first_result['passed']}")
            print(f"  Score: {first_result['score']:.2f}")
            print(f"  Questions: {first_result['passed_questions']}/{first_result['total_questions']}")
        
    except Exception as e:
        print(f"❌ Error during evaluation: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
