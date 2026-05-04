#!/bin/bash
# Security setup script for repository

echo "Installing security tools..."

# Install pre-commit
pip install pre-commit detect-secrets

# Install pre-commit hooks
pre-commit install

# Generate secrets baseline
detect-secrets scan --baseline .secrets.baseline

echo "Security tools installed successfully!"
echo "Run 'pre-commit run --all-files' to scan existing files"
