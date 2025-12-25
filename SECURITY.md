# Security Policy

## Supported Versions

We actively support the following versions of EggAI with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | :white_check_mark: |
| < 0.2.0 | :x:                |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability in EggAI, please report it responsibly.

### How to Report

**DO NOT** open a public GitHub issue for security vulnerabilities.

Instead, please report security issues via email to:

**security@eggai-tech.com**

Or use GitHub's private vulnerability reporting:
https://github.com/eggai-tech/EggAI/security/advisories/new

### What to Include

Please include the following information in your report:

- Description of the vulnerability
- Steps to reproduce the issue
- Affected versions
- Potential impact assessment
- Any suggested fixes (optional)

### Response Timeline

- **Initial Response:** Within 48 hours
- **Status Update:** Within 7 days
- **Fix Timeline:** Depends on severity
  - Critical: 7-14 days
  - High: 14-30 days
  - Medium: 30-60 days
  - Low: 60-90 days

### Security Update Process

1. We will confirm receipt of your report
2. We will investigate and assess the severity
3. We will develop and test a fix
4. We will release a patch version
5. We will publish a security advisory (with your credit, if desired)

## Known Security Considerations

### Optional Dependencies

EggAI has several optional features that include third-party dependencies:

- **A2A Integration** (`pip install eggai[a2a]`) - Uses a2a-sdk
- **MCP Integration** (`pip install eggai[mcp]`) - Uses fastmcp
- **CLI Tools** (`pip install eggai[cli]`) - Uses click, jinja2

Please review the security advisories of these packages if you use these features.

### Transport Security

#### Kafka Transport
- Uses aiokafka library
- Ensure your Kafka brokers use TLS/SSL in production
- Use SASL authentication when available
- Never expose Kafka ports publicly

#### Redis Transport
- Uses redis library via FastStream
- Always use password authentication in production
- Use TLS/SSL for Redis connections in production
- Never expose Redis ports publicly

#### In-Memory Transport
- Suitable for development and testing only
- NOT recommended for production use
- No persistence or security features

## Security Best Practices

When using EggAI in production:

1. **Use Environment Variables** for sensitive configuration
2. **Enable TLS/SSL** for all transport connections
3. **Use Authentication** for message brokers
4. **Keep Dependencies Updated** - regularly update EggAI and dependencies
5. **Monitor Security Advisories** - subscribe to GitHub security advisories
6. **Use Network Isolation** - run agents in isolated networks when possible
7. **Implement Rate Limiting** - prevent abuse of agent endpoints
8. **Validate Input** - sanitize all external input before processing
9. **Audit Logs** - maintain logs of agent activities

## Security Advisories

View published security advisories:
https://github.com/eggai-tech/EggAI/security/advisories

Subscribe to security updates via GitHub Watch → Custom → Security alerts

## Acknowledgments

We appreciate the security research community's efforts in helping keep EggAI secure. Security researchers who responsibly disclose vulnerabilities will be acknowledged in our security advisories (with permission).

---

Last updated: December 25, 2024
