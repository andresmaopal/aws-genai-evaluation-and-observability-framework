# Design Document: Bedrock AgentCore - Langfuse Integration

## Overview

This design describes a comprehensive integration between AWS Bedrock AgentCore Evaluations and Langfuse observability platform. The system enables developers to execute on-demand evaluations of AI agent interactions using Bedrock AgentCore's evaluation capabilities and automatically register the resulting scores (both rubric-based metrics and text justifications) into Langfuse for tracking, analysis, and visualization.

The integration is implemented as a Jupyter notebook that demonstrates the complete workflow from evaluation execution to score registration, providing a reusable pattern for production implementations.

### Key Capabilities

- Execute on-demand evaluations using Bedrock AgentCore for specific agent interactions
- Register numeric, categorical, and boolean scores in Langfuse
- Store evaluation justifications as comments linked to scores
- Handle batch processing of multiple evaluations
- Provide robust error handling and retry logic
- Support both built-in and custom evaluators

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Jupyter Notebook                          │
│  ┌────────────────────────────────────────────────────────┐ │
│  │         Integration Orchestrator                        │ │
│  │  - Configuration Management                             │ │
│  │  - Workflow Coordination                                │ │
│  │  - Error Handling                                       │ │
│  └────────────────────────────────────────────────────────┘ │
│           │                    │                    │         │
│           ▼                    ▼                    ▼         │
│  ┌─────────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Langfuse Trace  │  │   Bedrock    │  │  Langfuse    │   │
│  │   Extractor     │  │   Client     │  │    Score     │   │
│  │ - Extract by    │  │ - Evaluation │  │  Registrar   │   │
│  │   Tags          │  │   Execution  │  │ - Score API  │   │
│  │ - Extract by    │  │              │  │ - Comment API│   │
│  │   Trace Name    │  │              │  │              │   │
│  └─────────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────┘
           │                    │                    │
           ▼                    ▼                    ▼
┌──────────────────────┐  ┌──────────────┐  ┌──────────────┐
│  Langfuse Platform   │  │ AWS Bedrock  │  │  Langfuse    │
│  - Traces (Input)    │  │  AgentCore   │  │  Platform    │
│  - Tags              │  │ - Evaluations│  │ - Scores     │
│  - Trace Names       │  │   API        │  │   (Output)   │
└──────────────────────┘  └──────────────┘  └──────────────┘
```

### Component Interaction Flow

1. **Configuration Phase**: Initialize Langfuse client with authentication keys
2. **Extraction Phase**: Extract traces from Langfuse using tags or trace names
3. **Evaluation Phase**: Execute on-demand evaluations via Bedrock AgentCore API on extracted traces
4. **Transformation Phase**: Convert evaluation results to Langfuse score format
5. **Registration Phase**: Send scores and justifications back to Langfuse
6. **Verification Phase**: Confirm scores appear in Langfuse UI

## Components and Interfaces

### 1. Configuration Manager

**Purpose**: Centralize configuration for both AWS and Langfuse services

**Interface**:
```python
class Config:
    # AWS Configuration
    aws_region: str
    bedrock_agent_arn: str
    
    # Langfuse Configuration
    langfuse_public_key: str
    langfuse_secret_key: str
    langfuse_host: str
    
    # Evaluation Configuration
    evaluator_names: List[str]
    batch_size: int
    retry_attempts: int
    retry_delay: float
    
    @classmethod
    def from_environment() -> Config
    
    def validate() -> List[str]  # Returns validation errors
```

### 2. Langfuse Trace Extractor

**Purpose**: Extract traces from Langfuse based on tags or trace names

**Interface**:
```python
class LangfuseTraceExtractor:
    def __init__(self, config: Config)
    
    def extract_traces_by_tags(
        self,
        tags: List[str]
    ) -> List[TraceData]
    
    def extract_traces_by_name(
        self,
        trace_name: str
    ) -> List[TraceData]

class TraceData:
    trace_id: str
    trace_name: str
    tags: List[str]
    observations: List[Observation]
    metadata: Dict[str, Any]
```

### 3. Bedrock Evaluation Client

**Purpose**: Execute on-demand evaluations using Bedrock AgentCore on extracted traces

**Interface**:
```python
class BedrockEvaluationClient:
    def __init__(self, config: Config)
    
    def evaluate_traces(
        self,
        traces: List[TraceData],
        evaluator_names: List[str]
    ) -> List[EvaluationResult]
    
    def evaluate_single_trace(
        self,
        trace: TraceData,
        evaluator_name: str
    ) -> EvaluationResult

class EvaluationResult:
    trace_id: str
    evaluator_name: str
    score_value: Union[float, str, bool]
    score_type: Literal["numeric", "categorical", "boolean"]
    justification: Optional[str]
    metadata: Dict[str, Any]
    timestamp: datetime
```

### 4. Langfuse Score Registrar

**Purpose**: Register evaluation scores and justifications in Langfuse

**Interface**:
```python
class LangfuseScoreRegistrar:
    def __init__(self, config: Config)
    
    def register_score(
        self,
        trace_id: str,
        score_name: str,
        score_value: Union[float, str, bool],
        score_type: Literal["numeric", "categorical", "boolean"],
        comment: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ScoreRegistrationResult
    
    def register_scores_batch(
        self,
        scores: List[ScoreData]
    ) -> List[ScoreRegistrationResult]
    
    def verify_score_exists(
        self,
        trace_id: str,
        score_name: str
    ) -> bool

class ScoreRegistrationResult:
    success: bool
    score_id: Optional[str]
    error: Optional[str]
    trace_id: str
    score_name: str
```

### 5. Integration Orchestrator

**Purpose**: Coordinate the end-to-end evaluation and registration workflow

**Interface**:
```python
class IntegrationOrchestrator:
    def __init__(
        self,
        trace_extractor: LangfuseTraceExtractor,
        bedrock_client: BedrockEvaluationClient,
        langfuse_registrar: LangfuseScoreRegistrar
    )
    
    def process_evaluations_by_tags(
        self,
        tags: List[str],
        evaluator_names: List[str]
    ) -> ProcessingReport
    
    def process_evaluations_by_trace_name(
        self,
        trace_name: str,
        evaluator_names: List[str]
    ) -> ProcessingReport
    
    def process_single_trace(
        self,
        trace: TraceData,
        evaluator_name: str
    ) -> ProcessingResult

class ProcessingReport:
    total_traces: int
    total_evaluations: int
    successful_registrations: int
    failed_registrations: int
    errors: List[ProcessingError]
    duration: float
```

## Data Models

### Evaluation Result Mapping

**Bedrock Evaluation Output → Langfuse Score**:

```python
# Numeric Score Example
{
    "evaluator": "relevance_score",
    "score": 0.85,
    "justification": "Response directly addresses the user query..."
}
↓
Langfuse Score:
{
    "trace_id": "trace-123",
    "name": "relevance_score",
    "value": 0.85,
    "data_type": "NUMERIC",
    "comment": "Response directly addresses the user query..."
}

# Categorical Score Example
{
    "evaluator": "quality_rating",
    "score": "excellent",
    "justification": "Output meets all quality criteria..."
}
↓
Langfuse Score:
{
    "trace_id": "trace-123",
    "name": "quality_rating",
    "value": "excellent",
    "data_type": "CATEGORICAL",
    "comment": "Output meets all quality criteria..."
}
```

### Score Configuration

To ensure consistency, the system will create score configurations in Langfuse:

```python
score_configs = [
    {
        "name": "relevance_score",
        "data_type": "NUMERIC",
        "min_value": 0.0,
        "max_value": 1.0,
        "description": "Measures how relevant the agent response is to the user query"
    },
    {
        "name": "quality_rating",
        "data_type": "CATEGORICAL",
        "categories": ["poor", "fair", "good", "excellent"],
        "description": "Overall quality assessment of agent response"
    }
]
```

## Error Handling

### Error Categories and Strategies

1. **Configuration Errors**
   - Missing credentials
   - Invalid region or endpoint
   - Strategy: Fail fast with clear error messages

2. **Bedrock API Errors**
   - Invalid span/trace IDs
   - Evaluation timeout
   - Rate limiting
   - Strategy: Log error, skip item, continue processing

3. **Langfuse API Errors**
   - Authentication failure
   - Network timeout
   - Rate limiting
   - Strategy: Retry with exponential backoff (3 attempts)

4. **Data Transformation Errors**
   - Unexpected evaluation result format
   - Missing required fields
   - Strategy: Log warning, use default values where possible

### Retry Logic

```python
def retry_with_backoff(
    func: Callable,
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0
) -> Any:
    """
    Retry function with exponential backoff
    Delays: 1s, 2s, 4s
    """
    for attempt in range(max_attempts):
        try:
            return func()
        except RetryableError as e:
            if attempt == max_attempts - 1:
                raise
            delay = initial_delay * (backoff_factor ** attempt)
            time.sleep(delay)
```

## Testing Strategy

The integration will be validated through a combination of unit tests and property-based tests to ensure correctness across various scenarios.

### Unit Testing Approach

Unit tests will focus on:
- Configuration validation with specific valid/invalid inputs
- Error handling for known failure scenarios
- API response parsing with example data
- Score transformation logic with sample evaluations
- Integration points between components

### Property-Based Testing Approach

Property-based tests will verify universal properties using a minimum of 100 iterations per test. Each test will be tagged with its corresponding property number and feature name.

**Testing Framework**: We will use `hypothesis` for Python property-based testing, which provides:
- Automatic generation of test inputs
- Shrinking of failing examples to minimal cases
- Stateful testing capabilities
- Integration with pytest

**Test Configuration**:
```python
from hypothesis import given, settings
import hypothesis.strategies as st

@settings(max_examples=100)
@given(...)
def test_property_name(...):
    # Feature: bedrock-langfuse-integration, Property N: [property text]
    pass
```



## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Client Initialization Success

*For any* valid configuration containing proper credentials, region, and host information, initializing both Bedrock and Langfuse clients should succeed without errors.

**Validates: Requirements 1.1, 2.1**

### Property 2: Trace Extraction by Tags

*For any* valid list of Langfuse tags, the system should successfully authenticate to Langfuse and extract all traces associated with those tags.

**Validates: Requirements 1.2**

### Property 3: Trace Extraction by Name

*For any* valid Langfuse trace name, the system should successfully authenticate to Langfuse and extract all traces with that name.

**Validates: Requirements 1.2**

### Property 4: Evaluator Support Universality

*For any* evaluator (built-in or custom) and valid trace data, the system should successfully execute the evaluation and return results.

**Validates: Requirements 1.3, 1.4**

### Property 5: Evaluation Result Structure

*For any* evaluation result returned by the system, it should contain both a score value and a justification field (which may be empty but must be present).

**Validates: Requirements 1.5**

### Property 6: Connection Validation Before Operations

*For any* Langfuse configuration, the system should validate the connection before attempting to send scores, and should fail fast with clear errors if validation fails.

**Validates: Requirements 2.2, 2.3**

### Property 7: Score Type Mapping Correctness

*For any* evaluation result with a specific data type (numeric, categorical, or boolean), the corresponding Langfuse score should be created with the matching data type.

**Validates: Requirements 3.1, 3.2**

### Property 8: Score Metadata Completeness

*For any* score registered in Langfuse, it should include the correct trace ID, evaluator name as score name, timestamp, and evaluator configuration metadata.

**Validates: Requirements 3.3, 3.4, 3.6**

### Property 9: Score Idempotency

*For any* score that is registered twice with the same trace ID and evaluator name, the second registration should update the existing score rather than create a duplicate.

**Validates: Requirements 3.5**

### Property 10: Justification Preservation

*For any* evaluation justification text of any length, storing it in Langfuse and retrieving it should return the exact same text without truncation or modification (round-trip property).

**Validates: Requirements 4.3**

### Property 11: Justification-Score Association

*For any* score with an associated justification, the justification should be linked to the score in Langfuse such that querying the score returns its justification.

**Validates: Requirements 4.1, 4.2**

### Property 12: Multiple Justifications Ordering

*For any* evaluation with multiple justifications, all justifications should be stored in Langfuse in the order they were provided.

**Validates: Requirements 4.4**

### Property 13: Error Logging Completeness

*For any* API call failure (Bedrock or Langfuse), the system should log detailed error information including the operation attempted, the error type, and relevant context.

**Validates: Requirements 6.1, 6.5**

### Property 14: Retry Behavior with Exponential Backoff

*For any* Langfuse API failure, the system should retry the operation with exponentially increasing delays (1s, 2s, 4s) up to 3 attempts before giving up.

**Validates: Requirements 6.2**

### Property 15: Batch Processing Resilience

*For any* batch of evaluations where some items fail, the system should continue processing all remaining items and report all failures at the end rather than stopping at the first error.

**Validates: Requirements 6.3, 7.4**

### Property 16: Input Validation Before API Calls

*For any* operation requiring API calls, the system should validate all input parameters first and return descriptive errors for invalid inputs before making any API calls.

**Validates: Requirements 6.4**

### Property 17: Sequential Batch Processing

*For any* list of traces provided for batch processing, the system should process them in the order provided and collect all evaluation results before beginning score registration.

**Validates: Requirements 7.1, 7.2**

### Property 18: Progress Indication During Batch Operations

*For any* batch processing operation, the system should provide progress indicators showing the current item being processed and the total count.

**Validates: Requirements 7.3**

### Property 19: Environment Variable Configuration Support

*For any* sensitive credential (API keys, secrets), the system should successfully load it from environment variables when provided.

**Validates: Requirements 8.1**

### Property 20: Configuration Validation at Initialization

*For any* configuration provided to the system, validation should occur at initialization time, and any missing required values should produce clear error messages indicating exactly which configuration values are needed.

**Validates: Requirements 8.3, 8.4**

### Property 21: Multi-Instance Langfuse Support

*For any* valid Langfuse host URL (cloud-hosted or self-hosted), the system should successfully connect and extract traces.

**Validates: Requirements 2.4**


## Notebook Structure

The Jupyter notebook will be organized into the following sections:

### 1. Introduction and Setup
- Overview of the integration
- Prerequisites and dependencies
- Installation instructions using pip

### 2. Configuration
- Environment variable setup
- Configuration object creation
- Credential validation

### 3. Client Initialization and Trace Extraction
- Langfuse client setup with authentication keys
- Connection testing
- Extract traces by tags example
- Extract traces by trace name example
- Display extracted trace information

### 4. Single Evaluation Example
- Extract traces by tag or name
- Execute one on-demand evaluation on extracted trace
- Inspect evaluation results
- Register score back in Langfuse
- Verify score in Langfuse UI

### 5. Batch Evaluation Example
- Extract multiple traces by tags
- Process multiple evaluations
- Handle mixed success/failure scenarios
- Register all scores back to Langfuse
- Generate summary report

### 6. Advanced Features
- Custom evaluators
- Score configurations
- Idempotency handling
- Error recovery patterns

### 7. Verification and Visualization
- Query scores from Langfuse
- Display score analytics
- Troubleshooting guide

## Implementation Notes

### Langfuse Trace Extraction

The integration will first extract traces from Langfuse using tags or trace names:

```python
from langfuse import Langfuse

# Initialize client
langfuse = Langfuse(
    public_key=config.langfuse_public_key,
    secret_key=config.langfuse_secret_key,
    host=config.langfuse_host
)

# Extract traces by tags
traces = langfuse.fetch_traces(
    tags=["production", "customer-support"]
)

# Extract traces by name
traces = langfuse.fetch_traces(
    name="agent-conversation"
)

# Response structure
[
    {
        'id': 'trace-abc',
        'name': 'agent-conversation',
        'tags': ['production', 'customer-support'],
        'observations': [...],
        'metadata': {...}
    }
]
```

### AWS Bedrock AgentCore API Usage

The integration will use the following Bedrock AgentCore API patterns to evaluate extracted traces:

```python
# Initialize client
bedrock_client = boto3.client(
    'bedrock-agentcore',
    region_name=config.aws_region
)

# Execute on-demand evaluation on traces
response = bedrock_client.evaluate_traces(
    traceData=[
        {
            'traceId': 'trace-abc',
            'observations': [...],
            'metadata': {...}
        }
    ],
    evaluatorArns=[
        'arn:aws:bedrock:region:account:evaluator/evaluator-name'
    ]
)

# Response structure
{
    'evaluations': [
        {
            'traceId': 'trace-abc',
            'evaluatorName': 'relevance_score',
            'score': 0.85,
            'justification': 'Response directly addresses...',
            'metadata': {...}
        }
    ]
}
```

### Langfuse Score Registration

After evaluation, scores are registered back to Langfuse:

```python
# Register numeric score
langfuse.score(
    trace_id="trace-abc",
    name="relevance_score",
    value=0.85,
    data_type="NUMERIC",
    comment="Response directly addresses the user query..."
)

# Register categorical score
langfuse.score(
    trace_id="trace-abc",
    name="quality_rating",
    value="excellent",
    data_type="CATEGORICAL",
    comment="Output meets all quality criteria..."
)

# Flush to ensure scores are sent
langfuse.flush()
```

### Idempotency Key Generation

To prevent duplicate scores, the system will generate idempotency keys:

```python
def generate_idempotency_key(trace_id: str, evaluator_name: str) -> str:
    """
    Generate a consistent idempotency key for a score.
    This ensures that re-running evaluations updates existing scores
    rather than creating duplicates.
    """
    return f"{trace_id}_{evaluator_name}"
```

### Error Handling Patterns

```python
class RetryableError(Exception):
    """Errors that should trigger retry logic"""
    pass

class NonRetryableError(Exception):
    """Errors that should fail immediately"""
    pass

def handle_api_error(error: Exception) -> None:
    """
    Classify errors and determine retry strategy
    """
    if isinstance(error, (ConnectionError, TimeoutError)):
        raise RetryableError(f"Transient error: {error}")
    elif isinstance(error, AuthenticationError):
        raise NonRetryableError(f"Authentication failed: {error}")
    else:
        raise NonRetryableError(f"Unexpected error: {error}")
```

## Dependencies

The implementation requires the following Python packages:

```
boto3>=1.34.0              # AWS SDK for Bedrock AgentCore
langfuse>=2.0.0            # Langfuse observability SDK
python-dotenv>=1.0.0       # Environment variable management
hypothesis>=6.0.0          # Property-based testing
pytest>=7.0.0              # Testing framework
jupyter>=1.0.0             # Notebook environment
pandas>=2.0.0              # Data manipulation for reporting
matplotlib>=3.7.0          # Visualization
```

## Security Considerations

1. **Credential Management**
   - Never hardcode credentials in notebooks
   - Use environment variables or AWS Secrets Manager
   - Rotate API keys regularly

2. **Data Privacy**
   - Evaluation results may contain sensitive information
   - Ensure Langfuse instance has appropriate access controls
   - Consider data retention policies

3. **Network Security**
   - Use HTTPS for all API communications
   - Validate SSL certificates
   - Consider VPC endpoints for AWS services

4. **Audit Logging**
   - Log all evaluation executions
   - Track score registrations
   - Monitor for unusual patterns

## Performance Considerations

1. **Batch Size**
   - Recommended batch size: 10-50 evaluations
   - Larger batches may hit API rate limits
   - Smaller batches increase overhead

2. **Retry Strategy**
   - Exponential backoff prevents overwhelming services
   - Maximum 3 retries balances reliability and latency
   - Consider circuit breaker pattern for production

3. **Async Processing**
   - For large-scale evaluations, consider async/await patterns
   - Use connection pooling for better throughput
   - Implement queue-based processing for production workloads

## Future Enhancements

1. **Streaming Evaluations**
   - Support for real-time evaluation as spans are created
   - WebSocket integration for live updates

2. **Advanced Analytics**
   - Aggregate evaluation metrics across traces
   - Trend analysis and anomaly detection
   - Custom dashboards in Langfuse

3. **Multi-Provider Support**
   - Support for other observability platforms
   - Pluggable backend architecture
   - Unified evaluation interface

4. **Automated Evaluation Pipelines**
   - Scheduled evaluation jobs
   - Trigger-based evaluations (e.g., on deployment)
   - Integration with CI/CD pipelines
