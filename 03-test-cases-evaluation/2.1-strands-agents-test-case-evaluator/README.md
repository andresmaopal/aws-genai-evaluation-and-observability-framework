# AWS Strands Agents SDK - Unified Testing Framework

A comprehensive testing framework for evaluating AWS Bedrock models using the Strands Agents SDK with unified testing methods and human-readable results.

## 🚀 Quick Start

```bash
# Install dependencies
pip install ipywidgets "strands-agents==0.1.9" "strands-agents-tools==0.1.7"

# Run unified tests
from utils_unified import UnifiedTester
tester = UnifiedTester()
results = tester.run_test(
    models=["claude-4-sonnet"],
    prompts=["version1"],
    queries=["What is the current bitcoin price?"],
    prompts_dict=prompts,
    tool=tool_list
)
```

## 📁 Project Structure

```
01-experiment-tracking/
├── README.md                                    # This file
├── experiments_testings_unified.ipynb          # Unified testing notebook
├── utils_unified.py                            # Unified testing framework
├── test_config.json                           # Test configuration
├── model_list.json                            # Available models
├── sync_models.py                             # Model synchronization
└── test_results/                              # Test output directory
```

## ⚙️ Configuration Guide

### 1. test_config.json Configuration

The `test_config.json` file contains your system prompts and test queries:

```json
{
  "system_prompts": {
    "version1": "Your detailed system prompt for version 1...",
    "version2": "Your alternative system prompt for version 2..."
  },
  "test_queries": [
    "What is the current bitcoin price?",
    "What is the performance of Nvidia stock today?",
    "Can you provide a comparison between Bitcoin and Ethereum prices?",
    "What are the top 5 performing stocks in the tech sector today?"
  ]
}
```

#### System Prompts Structure

**Key Components:**
- **Role Definition**: Define the agent's primary role and expertise
- **Available Tools**: List and describe available sub-agents/tools
- **Coordination Protocols**: How the agent should route queries
- **Response Guidelines**: Formatting and behavior rules
- **Error Handling**: How to handle failures and limitations

**Example System Prompt:**
```json
{
  "version1": "
You are a Financial Market Orchestrator that coordinates between multiple financial expert agents.

AVAILABLE SUB-AGENTS:
1. StockInfoExpertAgent - Stock market data and analysis
2. CryptoExpertAgent - Cryptocurrency market information

COORDINATION PROTOCOLS:
- Analyze queries to identify relevant experts
- Route questions to appropriate specialists
- Synthesize responses from multiple agents

RESPONSE FORMATTING:
- Credit information sources
- Present data in structured format
- Include relevant metrics and disclaimers
"
}
```

#### Test Queries Guidelines

**Query Types:**
- **Single Domain**: Queries targeting one specific tool/agent
- **Multi-Domain**: Queries requiring multiple agents
- **Complex Analysis**: Queries needing synthesis of multiple data sources
- **Edge Cases**: Queries testing error handling and limitations

**Best Practices:**
```json
{
  "test_queries": [
    "What is the current bitcoin price?",                    // Single domain - crypto
    "What is the performance of Nvidia stock today?",       // Single domain - stocks  
    "Compare Bitcoin and Ethereum prices",                  // Single domain - complex
    "What are tech stocks and crypto trends today?"         // Multi-domain
  ]
}
```

### 2. Agent Setup

#### Basic Agent Configuration

```python
from strands import Agent, tool
from strands.models.bedrock import BedrockModel

# Define your tools
@tool
def StockInfoExpertAgent(query):
    """Stock market analysis tool"""
    # Your implementation here
    return stock_analysis_result

@tool  
def CryptoExpertAgent(query):
    """Cryptocurrency analysis tool"""
    # Your implementation here
    return crypto_analysis_result

# Create tool list
tool_list = [StockInfoExpertAgent, CryptoExpertAgent]
```

#### Advanced Tool Implementation

**Bedrock Agent Integration:**
```python
@tool
def StockInfoExpertAgent(query):
    print("CALLING BEDROCK STOCKS AGENT")
    
    # Configuration
    region = "us-east-1"
    agent_id = "YOUR_AGENT_ID"
    alias_id = "YOUR_ALIAS_ID"
    
    # Initialize client
    bedrock_client = boto3.client("bedrock-agent-runtime", region_name=region)
    session_id = str(uuid.uuid1())
    
    try:
        # Invoke agent
        response = bedrock_client.invoke_agent(
            inputText=query,
            agentId=agent_id,
            agentAliasId=alias_id,
            sessionId=session_id,
            enableTrace=True,
            endSession=False
        )
        
        # Process response
        event_stream = response['completion']
        agent_answer = ""
        for event in event_stream:
            if 'chunk' in event:
                data = event['chunk']['bytes']
                agent_answer += data.decode('utf8')
        
        return agent_answer
        
    except Exception as e:
        return f"Error: {str(e)}"
```

**External API Integration:**
```python
@tool
def MarketDataAgent(query):
    """External market data API integration"""
    import requests
    
    try:
        # Call external API
        response = requests.get(
            "https://api.example.com/market-data",
            params={"query": query},
            headers={"Authorization": "Bearer YOUR_TOKEN"}
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return f"API Error: {response.status_code}"
            
    except Exception as e:
        return f"Error: {str(e)}"
```

### 3. Model Configuration

#### model_list.json Structure

```json
{
  "claude-4-sonnet": {
    "model_id": "us.anthropic.claude-sonnet-4-20250514-v1:0",
    "region_name": "us-east-1",
    "temperature": 0.1,
    "inference_type": "INFERENCE_PROFILE",
    "tooling_enabled": true
  },
  "qwen3-235b": {
    "model_id": "qwen.qwen3-235b-a22b-2507-v1:0", 
    "region_name": "us-west-2",
    "temperature": 0.1,
    "inference_type": "ON_DEMAND",
    "tooling_enabled": true
  }
}
```

#### Adding New Models

1. **Check Model Availability:**
```python
# Use sync_models.py to update available models
python sync_models.py
```

2. **Add Model Configuration:**
```json
{
  "your-model-name": {
    "model_id": "provider.model-id-v1:0",
    "region_name": "us-east-1",
    "temperature": 0.1,
    "inference_type": "ON_DEMAND",
    "tooling_enabled": true
  }
}
```

## 🧪 Testing Guide

### 1. Basic Testing

```python
from utils_unified import UnifiedTester
import json

# Initialize tester
tester = UnifiedTester()

# Load configuration
with open('test_config.json', 'r') as f:
    config = json.load(f)

prompts = config['system_prompts']
test_queries = config['test_queries']

# Single test
results = tester.run_test(
    models=["claude-4-sonnet"],
    prompts=["version1"],
    queries=[test_queries[0]],
    prompts_dict=prompts,
    tool=tool_list
)

# Display results
tester.display_results(results)
```

### 2. Comprehensive Testing

```python
# Test multiple models
results = tester.run_test(
    models=["claude-4-sonnet", "qwen3-235b"],
    prompts=["version1", "version2"],
    queries=test_queries,  # All queries
    prompts_dict=prompts,
    tool=tool_list
)

# Analyze results
analysis = tester.analyze_results(results)

# Export results to CSV with timestamp
tester.export_results(results, "comprehensive_test_results")
```

### 3. Test Scenarios

#### Model Comparison
```python
# Compare different models with same prompt and query
model_comparison = tester.run_test(
    models=["claude-4-sonnet", "qwen3-235b", "nova-pro"],
    prompts=["version1"],
    queries=["What is the current bitcoin price?"],
    prompts_dict=prompts,
    tool=tool_list
)
```

#### Prompt Engineering
```python
# Test different prompts with same model and query
prompt_comparison = tester.run_test(
    models=["claude-4-sonnet"],
    prompts=["version1", "version2"],
    queries=["What is the current bitcoin price?"],
    prompts_dict=prompts,
    tool=tool_list
)
```

#### Query Analysis
```python
# Test all queries with best performing configuration
query_analysis = tester.run_test(
    models=["claude-4-sonnet"],
    prompts=["version1"],
    queries=test_queries,  # All queries
    prompts_dict=prompts,
    tool=tool_list
)
```

## 📊 Results Analysis

### Result Structure

Each test result contains:
```python
{
    "test_id": "claude-4-sonnet_version1_1234",
    "model": "claude-4-sonnet",
    "prompt": "version1", 
    "query": "What is the current bitcoin price?",
    "response": "According to our analysis...",
    "response_time": 12.34,
    "success": True,
    "error": None,
    "timestamp": "2025-01-27T10:30:00",
    "model_config": {...}
}
```

### Analysis Features

**Performance Metrics:**
- Success rates by model and prompt
- Response time statistics
- Error analysis and patterns
- Model rankings by performance

**Human-Readable Display:**
- 📈 Results Summary
- 🤖 Model Performance
- 📝 Prompt Performance  
- 📋 Detailed Results
- 🔍 Performance Analysis
- 🏆 Model Rankings

### Export Options

```python
# Export to CSV with timestamp (creates: test_results_YYYYMMDD_HHMMSS.csv)
tester.export_results(results, "test_results")

# Display models in human-readable table
tester.list_models_by_provider()

# Custom analysis
analysis = tester.analyze_results(results)
print(f"Best performing model: {analysis['model_rankings'][0]['model']}")
```

## 🛠️ Advanced Configuration

### Custom Tools

```python
@tool
def CustomAnalysisAgent(query):
    """Custom analysis implementation"""
    # Your custom logic here
    analysis_result = perform_custom_analysis(query)
    return analysis_result

# Add to tool list
tool_list = [StockInfoExpertAgent, CryptoExpertAgent, CustomAnalysisAgent]
```

### Environment Variables

```bash
# AWS Configuration
export AWS_REGION=us-east-1
export AWS_PROFILE=your-profile

# API Keys (if using external APIs)
export MARKET_API_KEY=your-api-key
export CRYPTO_API_KEY=your-crypto-key
```

### Error Handling

```python
# Custom error handling in tools
@tool
def RobustAgent(query):
    try:
        result = call_external_service(query)
        return result
    except ConnectionError:
        return "Service temporarily unavailable. Please try again later."
    except ValueError as e:
        return f"Invalid query format: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"
```

## 🔧 Troubleshooting

### Common Issues

**1. Model Not Found**
```
Error: Model 'model-name' not found
```
**Solution:** Check `model_list.json` and ensure model is available in your region.

**2. Tool Import Errors**
```
Error: Tool 'ToolName' not found
```
**Solution:** Ensure tools are properly decorated with `@tool` and imported.

**3. Authentication Issues**
```
Error: Unable to locate credentials
```
**Solution:** Configure AWS credentials using `aws configure` or environment variables.

**4. Region Mismatch**
```
Error: Model not available in region
```
**Solution:** Update model configuration with correct region or change AWS region.

### Debug Mode

```python
# Enable detailed logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Test with error details
try:
    results = tester.run_test(...)
except Exception as e:
    print(f"Detailed error: {str(e)}")
    import traceback
    traceback.print_exc()
```

## 📚 Best Practices

### 1. Prompt Engineering
- Start with clear role definitions
- Include specific examples
- Define error handling scenarios
- Test with edge cases

### 2. Tool Design
- Keep tools focused and single-purpose
- Include proper error handling
- Add informative logging
- Test tools independently

### 3. Testing Strategy
- Start with single configurations
- Gradually increase complexity
- Compare similar models
- Document findings

### 4. Performance Optimization
- Use appropriate model sizes
- Optimize prompt length
- Implement caching where possible
- Monitor response times

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Add tests for new functionality
4. Update documentation
5. Submit pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section
2. Review existing issues
3. Create detailed bug reports
4. Include configuration and error logs
