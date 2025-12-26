# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | :white_check_mark: |
| < 0.2   | :x:                |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability, please report it responsibly.

### How to Report

1. **Do NOT** open a public GitHub issue for security vulnerabilities
2. Email your findings to: **security@eggai.dev**
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### What to Expect

- **Response Time**: We will acknowledge your report within 48 hours
- **Updates**: We will keep you informed of our progress
- **Resolution**: We aim to resolve critical issues within 7 days
- **Credit**: We will credit you in the release notes (unless you prefer anonymity)

### Scope

The following are in scope:
- EggAI SDK core library
- Transport implementations (Kafka, Redis, InMemory)
- A2A and MCP adapters
- CLI tools

The following are out of scope:
- Third-party dependencies (report to upstream)
- Documentation website
- Example applications

## Security Best Practices

When using EggAI SDK:

1. **Credentials**: Never hardcode credentials. Use environment variables or secret managers.
2. **Transport Security**: Use TLS for Redis and Kafka in production.
3. **Input Validation**: Validate message content before processing.
4. **Access Control**: Implement appropriate authentication for A2A endpoints.
5. **Logging**: Avoid logging sensitive message content.

## Known Security Considerations

- **Message Content**: Messages are not encrypted by default. Use transport-level encryption.
- **A2A Endpoints**: Configure CORS appropriately for your deployment.
- **Consumer Groups**: Use unique group IDs to prevent message interception.

## Updates

Security updates are released as patch versions. We recommend:
- Enabling GitHub Dependabot alerts
- Regularly updating dependencies
- Subscribing to release notifications

---

Thank you for helping keep EggAI SDK secure!
