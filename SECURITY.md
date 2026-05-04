# Security Policy

## Reporting Security Vulnerabilities

If you discover a security vulnerability, please report it responsibly:

1. **Do NOT** create a public GitHub issue
2. Email security concerns to: [your-security-email@domain.com]
3. Include detailed steps to reproduce the vulnerability
4. Allow reasonable time for response before public disclosure

## Security Best Practices

### For Contributors:
- Never commit credentials, API keys, or secrets
- Use environment variables for sensitive configuration
- Run security scans before submitting PRs
- Keep dependencies updated

### For Users:
- Use IAM roles instead of access keys when possible
- Store secrets in AWS Secrets Manager or Parameter Store
- Enable CloudTrail logging for audit trails
- Use least privilege access principles

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| Latest  | :white_check_mark: |

## Security Tools

This repository uses:
- Pre-commit hooks for secret detection
- Dependency vulnerability scanning
- Code security analysis
