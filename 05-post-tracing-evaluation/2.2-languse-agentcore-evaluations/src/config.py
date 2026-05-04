"""Configuration management for Bedrock-Langfuse integration."""

import os
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Config:
    """Configuration for Bedrock AgentCore and Langfuse integration.
    
    Attributes:
        aws_region: AWS region for Bedrock AgentCore
        bedrock_agent_arn: ARN of the Bedrock agent to evaluate
        langfuse_public_key: Langfuse public API key
        langfuse_secret_key: Langfuse secret API key
        langfuse_host: Langfuse host URL (cloud or self-hosted)
        evaluator_names: List of evaluator names to use
        batch_size: Number of evaluations to process in a batch
        retry_attempts: Number of retry attempts for failed API calls
        retry_delay: Initial delay in seconds for retry backoff
    """
    
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
    def from_environment(cls) -> "Config":
        """Load configuration from environment variables.
        
        Returns:
            Config instance populated from environment variables.
            
        Environment Variables:
            AWS_REGION: AWS region (default: us-east-1)
            BEDROCK_AGENT_ARN: Bedrock agent ARN
            LANGFUSE_PUBLIC_KEY: Langfuse public key
            LANGFUSE_SECRET_KEY: Langfuse secret key
            LANGFUSE_HOST: Langfuse host URL (default: https://cloud.langfuse.com)
            EVALUATOR_NAMES: Comma-separated list of evaluator names
            BATCH_SIZE: Batch size for processing (default: 10)
            RETRY_ATTEMPTS: Number of retry attempts (default: 3)
            RETRY_DELAY: Initial retry delay in seconds (default: 1.0)
        """
        # Parse evaluator names from comma-separated string
        evaluator_names_str = os.getenv("EVALUATOR_NAMES", "")
        evaluator_names = [name.strip() for name in evaluator_names_str.split(",") if name.strip()]
        
        return cls(
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
            bedrock_agent_arn=os.getenv("BEDROCK_AGENT_ARN", ""),
            langfuse_public_key=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
            langfuse_secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
            langfuse_host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
            evaluator_names=evaluator_names,
            batch_size=int(os.getenv("BATCH_SIZE", "10")),
            retry_attempts=int(os.getenv("RETRY_ATTEMPTS", "3")),
            retry_delay=float(os.getenv("RETRY_DELAY", "1.0")),
        )
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of errors.
        
        Returns:
            List of validation error messages. Empty list if valid.
        """
        errors = []
        
        # Validate AWS configuration
        if not self.aws_region:
            errors.append("AWS_REGION is required")
        
        if not self.bedrock_agent_arn:
            errors.append("BEDROCK_AGENT_ARN is required")
        elif not self.bedrock_agent_arn.startswith("arn:aws:bedrock"):
            errors.append("BEDROCK_AGENT_ARN must be a valid Bedrock ARN starting with 'arn:aws:bedrock'")
        
        # Validate Langfuse configuration
        if not self.langfuse_public_key:
            errors.append("LANGFUSE_PUBLIC_KEY is required")
        
        if not self.langfuse_secret_key:
            errors.append("LANGFUSE_SECRET_KEY is required")
        
        if not self.langfuse_host:
            errors.append("LANGFUSE_HOST is required")
        elif not (self.langfuse_host.startswith("http://") or self.langfuse_host.startswith("https://")):
            errors.append("LANGFUSE_HOST must be a valid URL starting with http:// or https://")
        
        # Validate evaluation configuration
        if not self.evaluator_names:
            errors.append("EVALUATOR_NAMES is required (provide comma-separated list)")
        
        if self.batch_size <= 0:
            errors.append("BATCH_SIZE must be greater than 0")
        
        if self.retry_attempts < 0:
            errors.append("RETRY_ATTEMPTS must be non-negative")
        
        if self.retry_delay < 0:
            errors.append("RETRY_DELAY must be non-negative")
        
        return errors
