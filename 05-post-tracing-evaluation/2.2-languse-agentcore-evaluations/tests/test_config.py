"""Tests for configuration management."""

import os
import pytest
from src.config import Config


class TestConfig:
    """Test suite for Config class."""
    
    def test_from_environment_with_all_values(self, monkeypatch):
        """Test loading configuration from environment variables."""
        # Set up environment variables
        monkeypatch.setenv("AWS_REGION", "us-west-2")
        monkeypatch.setenv("BEDROCK_AGENT_ARN", "arn:aws:bedrock:us-west-2:123456789012:agent/test-agent")
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test-123")
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test-456")
        monkeypatch.setenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        monkeypatch.setenv("EVALUATOR_NAMES", "relevance_score,quality_rating")
        monkeypatch.setenv("BATCH_SIZE", "20")
        monkeypatch.setenv("RETRY_ATTEMPTS", "5")
        monkeypatch.setenv("RETRY_DELAY", "2.0")
        
        # Load configuration
        config = Config.from_environment()
        
        # Verify all fields
        assert config.aws_region == "us-west-2"
        assert config.bedrock_agent_arn == "arn:aws:bedrock:us-west-2:123456789012:agent/test-agent"
        assert config.langfuse_public_key == "pk-test-123"
        assert config.langfuse_secret_key == "sk-test-456"
        assert config.langfuse_host == "https://cloud.langfuse.com"
        assert config.evaluator_names == ["relevance_score", "quality_rating"]
        assert config.batch_size == 20
        assert config.retry_attempts == 5
        assert config.retry_delay == 2.0
    
    def test_from_environment_with_defaults(self, monkeypatch):
        """Test that defaults are applied when environment variables are not set."""
        # Clear all relevant environment variables
        for key in ["AWS_REGION", "BEDROCK_AGENT_ARN", "LANGFUSE_PUBLIC_KEY", 
                    "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST", "EVALUATOR_NAMES",
                    "BATCH_SIZE", "RETRY_ATTEMPTS", "RETRY_DELAY"]:
            monkeypatch.delenv(key, raising=False)
        
        config = Config.from_environment()
        
        # Verify defaults
        assert config.aws_region == "us-east-1"
        assert config.langfuse_host == "https://cloud.langfuse.com"
        assert config.batch_size == 10
        assert config.retry_attempts == 3
        assert config.retry_delay == 1.0
    
    def test_validate_valid_config(self):
        """Test validation passes for valid configuration."""
        config = Config(
            aws_region="us-east-1",
            bedrock_agent_arn="arn:aws:bedrock:us-east-1:123456789012:agent/test",
            langfuse_public_key="pk-test",
            langfuse_secret_key="sk-test",
            langfuse_host="https://cloud.langfuse.com",
            evaluator_names=["test_evaluator"],
            batch_size=10,
            retry_attempts=3,
            retry_delay=1.0
        )
        
        errors = config.validate()
        assert errors == []
    
    def test_validate_missing_aws_region(self):
        """Test validation fails when AWS region is missing."""
        config = Config(
            aws_region="",
            bedrock_agent_arn="arn:aws:bedrock:us-east-1:123456789012:agent/test",
            langfuse_public_key="pk-test",
            langfuse_secret_key="sk-test",
            langfuse_host="https://cloud.langfuse.com",
            evaluator_names=["test_evaluator"],
            batch_size=10,
            retry_attempts=3,
            retry_delay=1.0
        )
        
        errors = config.validate()
        assert "AWS_REGION is required" in errors
    
    def test_validate_invalid_bedrock_arn(self):
        """Test validation fails for invalid Bedrock ARN."""
        config = Config(
            aws_region="us-east-1",
            bedrock_agent_arn="invalid-arn",
            langfuse_public_key="pk-test",
            langfuse_secret_key="sk-test",
            langfuse_host="https://cloud.langfuse.com",
            evaluator_names=["test_evaluator"],
            batch_size=10,
            retry_attempts=3,
            retry_delay=1.0
        )
        
        errors = config.validate()
        assert any("BEDROCK_AGENT_ARN must be a valid Bedrock ARN" in error for error in errors)
    
    def test_validate_missing_langfuse_credentials(self):
        """Test validation fails when Langfuse credentials are missing."""
        config = Config(
            aws_region="us-east-1",
            bedrock_agent_arn="arn:aws:bedrock:us-east-1:123456789012:agent/test",
            langfuse_public_key="",
            langfuse_secret_key="",
            langfuse_host="https://cloud.langfuse.com",
            evaluator_names=["test_evaluator"],
            batch_size=10,
            retry_attempts=3,
            retry_delay=1.0
        )
        
        errors = config.validate()
        assert "LANGFUSE_PUBLIC_KEY is required" in errors
        assert "LANGFUSE_SECRET_KEY is required" in errors
    
    def test_validate_invalid_langfuse_host(self):
        """Test validation fails for invalid Langfuse host URL."""
        config = Config(
            aws_region="us-east-1",
            bedrock_agent_arn="arn:aws:bedrock:us-east-1:123456789012:agent/test",
            langfuse_public_key="pk-test",
            langfuse_secret_key="sk-test",
            langfuse_host="invalid-url",
            evaluator_names=["test_evaluator"],
            batch_size=10,
            retry_attempts=3,
            retry_delay=1.0
        )
        
        errors = config.validate()
        assert any("LANGFUSE_HOST must be a valid URL" in error for error in errors)
    
    def test_validate_missing_evaluator_names(self):
        """Test validation fails when evaluator names are missing."""
        config = Config(
            aws_region="us-east-1",
            bedrock_agent_arn="arn:aws:bedrock:us-east-1:123456789012:agent/test",
            langfuse_public_key="pk-test",
            langfuse_secret_key="sk-test",
            langfuse_host="https://cloud.langfuse.com",
            evaluator_names=[],
            batch_size=10,
            retry_attempts=3,
            retry_delay=1.0
        )
        
        errors = config.validate()
        assert any("EVALUATOR_NAMES is required" in error for error in errors)
    
    def test_validate_invalid_batch_size(self):
        """Test validation fails for invalid batch size."""
        config = Config(
            aws_region="us-east-1",
            bedrock_agent_arn="arn:aws:bedrock:us-east-1:123456789012:agent/test",
            langfuse_public_key="pk-test",
            langfuse_secret_key="sk-test",
            langfuse_host="https://cloud.langfuse.com",
            evaluator_names=["test_evaluator"],
            batch_size=0,
            retry_attempts=3,
            retry_delay=1.0
        )
        
        errors = config.validate()
        assert "BATCH_SIZE must be greater than 0" in errors
    
    def test_validate_negative_retry_attempts(self):
        """Test validation fails for negative retry attempts."""
        config = Config(
            aws_region="us-east-1",
            bedrock_agent_arn="arn:aws:bedrock:us-east-1:123456789012:agent/test",
            langfuse_public_key="pk-test",
            langfuse_secret_key="sk-test",
            langfuse_host="https://cloud.langfuse.com",
            evaluator_names=["test_evaluator"],
            batch_size=10,
            retry_attempts=-1,
            retry_delay=1.0
        )
        
        errors = config.validate()
        assert "RETRY_ATTEMPTS must be non-negative" in errors
