# Implementation Plan: Bedrock AgentCore - Langfuse Integration

## Overview

This implementation plan breaks down the development of a comprehensive Jupyter notebook that integrates AWS Bedrock AgentCore Evaluations with Langfuse observability platform. The notebook will demonstrate extracting traces from Langfuse using tags or trace names, executing on-demand evaluations on those traces, and registering scores (both rubric-based and text justifications) back in Langfuse.

## Tasks

- [x] 1. Set up project structure and dependencies
  - Create project directory structure
  - Create requirements.txt with all dependencies (boto3, langfuse, python-dotenv, hypothesis, pytest, jupyter, pandas, matplotlib)
  - Create .env.example file showing required environment variables
  - Create README.md with setup instructions
  - _Requirements: 8.1, 8.2_

- [x] 2. Implement configuration management
  - [x] 2.1 Create Config class with all configuration fields
    - Define fields for AWS region, Bedrock agent ARN, Langfuse credentials, and operational settings
    - Implement from_environment() class method to load from environment variables
    - _Requirements: 8.1, 8.2_
  
  - [ ]* 2.2 Write property test for configuration loading
    - **Property 18: Environment Variable Configuration Support**
    - **Validates: Requirements 8.1**
  
  - [x] 2.3 Implement configuration validation
    - Add validate() method that checks all required fields are present
    - Return list of validation errors with descriptive messages
    - _Requirements: 8.3, 8.4_
  
  - [ ]* 2.4 Write property test for configuration validation
    - **Property 19: Configuration Validation at Initialization**
    - **Validates: Requirements 8.3, 8.4**

- [ ] 3. Implement Langfuse Trace Extractor
  - [ ] 3.1 Create LangfuseTraceExtractor class
    - Initialize Langfuse client with authentication keys
    - Implement extract_traces_by_tags() method
    - Implement extract_traces_by_name() method
    - _Requirements: 1.2, 2.1_
  
  - [ ]* 3.2 Write property test for trace extraction by tags
    - **Property 2: Trace Extraction by Tags**
    - **Validates: Requirements 1.2**
  
  - [ ]* 3.3 Write property test for trace extraction by name
    - **Property 3: Trace Extraction by Name**
    - **Validates: Requirements 1.2**
  
  - [ ] 3.4 Create TraceData data class
    - Define fields for trace_id, trace_name, tags, observations, metadata
    - _Requirements: 1.2_

- [ ] 4. Implement Bedrock Evaluation Client
  - [ ] 4.1 Create BedrockEvaluationClient class
    - Initialize boto3 client with region configuration
    - Implement evaluate_traces() method for evaluating extracted traces
    - Implement evaluate_single_trace() helper method
    - _Requirements: 1.1, 1.3, 1.4_
  
  - [ ]* 4.2 Write property test for client initialization
    - **Property 1: Client Initialization Success**
    - **Validates: Requirements 1.1, 2.1**
  
  - [ ]* 4.3 Write property test for evaluator support
    - **Property 4: Evaluator Support Universality**
    - **Validates: Requirements 1.3, 1.4**
  
  - [ ] 4.4 Create EvaluationResult data class
    - Define fields for trace_id, evaluator_name, score_value, score_type, justification, metadata, timestamp
    - _Requirements: 1.5_
  
  - [ ]* 4.5 Write property test for evaluation result structure
    - **Property 5: Evaluation Result Structure**
    - **Validates: Requirements 1.5**

- [ ] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement Langfuse Score Registrar
  - [ ] 6.1 Create LangfuseScoreRegistrar class
    - Initialize Langfuse client with credentials and host
    - Implement connection validation method
    - _Requirements: 2.1, 2.2, 2.3, 2.4_
  
  - [ ]* 6.2 Write property test for connection validation
    - **Property 6: Connection Validation Before Operations**
    - **Validates: Requirements 2.2, 2.3**
  
  - [ ]* 6.3 Write property test for multi-instance support
    - **Property 21: Multi-Instance Langfuse Support**
    - **Validates: Requirements 2.4**
  
  - [ ] 6.4 Implement register_score() method
    - Accept trace_id, score_name, score_value, score_type, comment, metadata
    - Generate idempotency key from trace_id and score_name
    - Call Langfuse API to create/update score
    - Return ScoreRegistrationResult
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_
  
  - [ ]* 6.5 Write property test for score type mapping
    - **Property 7: Score Type Mapping Correctness**
    - **Validates: Requirements 3.1, 3.2**
  
  - [ ]* 6.6 Write property test for score metadata completeness
    - **Property 8: Score Metadata Completeness**
    - **Validates: Requirements 3.3, 3.4, 3.6**
  
  - [ ]* 6.7 Write property test for score idempotency
    - **Property 9: Score Idempotency**
    - **Validates: Requirements 3.5**
  
  - [ ] 6.8 Implement justification handling
    - Store justification as comment linked to score
    - Support multiple justifications with ordering
    - _Requirements: 4.1, 4.2, 4.3, 4.4_
  
  - [ ] 6.9 Write property test for justification preservation
    - **Property 10: Justification Preservation**
    - **Validates: Requirements 4.3**
  
  - [ ]* 6.10 Write property test for justification-score association
    - **Property 11: Justification-Score Association**
    - **Validates: Requirements 4.1, 4.2**
  
  - [ ]* 6.11 Write property test for multiple justifications ordering
    - **Property 12: Multiple Justifications Ordering**
    - **Validates: Requirements 4.4**
  
  - [ ] 6.12 Implement register_scores_batch() method
    - Process list of ScoreData objects
    - Return list of ScoreRegistrationResult objects
    - _Requirements: 7.1, 7.2_
  
  - [ ] 6.13 Create ScoreRegistrationResult data class
    - Define fields for success, score_id, error, trace_id, score_name
    - _Requirements: 3.1, 3.2_

- [ ] 7. Implement error handling and retry logic
  - [ ] 7.1 Create custom exception classes
    - Define RetryableError and NonRetryableError
    - _Requirements: 6.1, 6.2_
  
  - [ ] 7.2 Implement retry_with_backoff() function
    - Accept function, max_attempts, initial_delay, backoff_factor
    - Implement exponential backoff (1s, 2s, 4s)
    - _Requirements: 6.2_
  
  - [ ]* 7.3 Write property test for retry behavior
    - **Property 14: Retry Behavior with Exponential Backoff**
    - **Validates: Requirements 6.2**
  
  - [ ] 7.4 Implement error logging
    - Log detailed error information for all API failures
    - Include operation, error type, and context
    - _Requirements: 6.1, 6.5_
  
  - [ ]* 7.5 Write property test for error logging
    - **Property 13: Error Logging Completeness**
    - **Validates: Requirements 6.1, 6.5**
  
  - [ ] 7.6 Implement input validation
    - Validate parameters before API calls
    - Return descriptive errors for invalid inputs
    - _Requirements: 6.4_
  
  - [ ]* 7.7 Write property test for input validation
    - **Property 16: Input Validation Before API Calls**
    - **Validates: Requirements 6.4**

- [ ] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Implement Integration Orchestrator
  - [ ] 9.1 Create IntegrationOrchestrator class
    - Accept LangfuseTraceExtractor, BedrockEvaluationClient, and LangfuseScoreRegistrar in constructor
    - _Requirements: 7.1, 7.2, 7.3, 7.4_
  
  - [ ] 9.2 Implement process_single_trace() method
    - Execute evaluation for one trace/evaluator pair
    - Register score in Langfuse
    - Return ProcessingResult
    - _Requirements: 1.4, 3.1, 3.2_
  
  - [ ] 9.3 Implement process_evaluations_by_tags() method for batch processing
    - Extract traces from Langfuse using tags
    - Process list of traces sequentially
    - Collect all evaluation results before registration
    - Provide progress indicators
    - Continue on errors and report at end
    - _Requirements: 1.2, 7.1, 7.2, 7.3, 7.4_
  
  - [ ] 9.4 Implement process_evaluations_by_trace_name() method
    - Extract traces from Langfuse using trace name
    - Process extracted traces
    - Follow same pattern as process_evaluations_by_tags()
    - _Requirements: 1.2, 7.1, 7.2, 7.3, 7.4_
  
  - [ ]* 9.5 Write property test for sequential batch processing
    - **Property 17: Sequential Batch Processing**
    - **Validates: Requirements 7.1, 7.2**
  
  - [ ]* 9.6 Write property test for progress indication
    - **Property 18: Progress Indication During Batch Operations**
    - **Validates: Requirements 7.3**
  
  - [ ]* 9.7 Write property test for batch processing resilience
    - **Property 15: Batch Processing Resilience**
    - **Validates: Requirements 6.3, 7.4**
  
  - [ ] 9.8 Create ProcessingReport data class
    - Define fields for total_traces, total_evaluations, successful_registrations, failed_registrations, errors, duration
    - _Requirements: 7.4_

- [ ] 10. Create Jupyter notebook structure
  - [ ] 10.1 Create notebook with introduction section
    - Add title and overview
    - List prerequisites
    - Add installation instructions for dependencies
    - _Requirements: 5.1_
  
  - [ ] 10.2 Add configuration section
    - Show environment variable setup
    - Demonstrate Config.from_environment()
    - Show configuration validation
    - _Requirements: 5.2, 8.1, 8.2_
  
  - [ ] 10.3 Add client initialization and trace extraction section
    - Demonstrate Langfuse client setup with authentication keys
    - Show connection testing
    - Demonstrate extracting traces by tags
    - Demonstrate extracting traces by trace name
    - Display extracted trace information
    - _Requirements: 5.2, 1.2_
  
  - [ ] 10.4 Add single evaluation example section
    - Extract traces by tag or name
    - Execute one on-demand evaluation on extracted trace
    - Display evaluation results
    - Register score back in Langfuse
    - Show verification in Langfuse UI
    - _Requirements: 5.3, 5.4, 5.6_
  
  - [ ] 10.5 Add batch evaluation example section
    - Extract multiple traces by tags
    - Process multiple evaluations
    - Show mixed success/failure handling
    - Register all scores back to Langfuse
    - Generate and display summary report
    - _Requirements: 5.3, 5.4_
  
  - [ ] 10.6 Add error handling examples section
    - Demonstrate handling of common failures
    - Show retry behavior
    - Show error recovery patterns
    - _Requirements: 5.5_
  
  - [ ] 10.7 Add verification and visualization section
    - Query scores from Langfuse
    - Display score analytics with pandas/matplotlib
    - Add troubleshooting guide
    - _Requirements: 5.6_
  
  - [ ] 10.8 Add explanatory markdown cells throughout
    - Describe each step clearly
    - Explain key concepts (trace extraction, evaluation, score registration)
    - Provide context for code examples
    - _Requirements: 5.7_

- [ ] 11. Final checkpoint - Ensure all tests pass and notebook runs end-to-end
  - Run all property-based tests with 100 iterations each
  - Execute notebook from start to finish
  - Verify traces are extracted from Langfuse
  - Verify evaluations are executed on extracted traces
  - Verify scores appear in Langfuse
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties using hypothesis framework
- Unit tests validate specific examples and edge cases
- The notebook serves as both documentation and working implementation
- All property tests should run with minimum 100 iterations
- Configuration should support both cloud and self-hosted Langfuse instances
- The workflow is: Extract traces from Langfuse → Evaluate with Bedrock → Register scores back to Langfuse
