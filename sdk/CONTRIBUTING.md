# Contributing to EggAI SDK

Thank you for your interest in contributing to EggAI SDK! We welcome contributions from the community.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/EggAI.git
   cd EggAI/sdk
   ```
3. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Setup

### Prerequisites
- Python 3.10 or higher
- Poetry (for dependency management)
- Redis (for Redis transport tests)
- Kafka (optional, for Kafka transport tests)

### Install Dependencies
```bash
poetry install --all-extras
```

### Run Tests
```bash
poetry run pytest -v
```

### Code Quality
```bash
# Lint code
poetry run ruff check .

# Format code
poetry run ruff format .
```

## Making Changes

### Code Style
- Follow PEP 8 guidelines
- Use type hints for all function signatures
- Add docstrings to public APIs (Google style)
- Keep functions focused and testable

### Testing
- Write tests for new features
- Ensure all tests pass before submitting
- Add integration tests for new transports
- Test with multiple Python versions (3.10-3.13)

### Commits
- Write clear, descriptive commit messages
- One logical change per commit
- Reference issue numbers in commits (e.g., "Fix #123")

## Submitting Changes

1. **Push your changes** to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```
2. **Create a Pull Request** on GitHub
3. **Describe your changes** in the PR description:
   - What problem does this solve?
   - How did you test it?
   - Any breaking changes?

### Pull Request Guidelines
- Fill out the PR template completely
- Link related issues
- Ensure CI/CD passes
- Request review from maintainers
- Be responsive to feedback

## Code Review Process

1. Maintainers will review your PR within 1-2 weeks
2. Address any requested changes
3. Once approved, a maintainer will merge your PR
4. Your changes will be included in the next release

## Reporting Bugs

- Use GitHub Issues to report bugs
- Include reproduction steps
- Provide Python version and OS
- Share error messages and logs
- Attach minimal reproducible example if possible

## Feature Requests

- Open a GitHub Issue with "Feature Request" label
- Describe the use case and benefit
- Discuss implementation approach
- Wait for maintainer feedback before implementing

## Security Issues

**Do NOT report security issues publicly**

- Email security@eggai.dev with details
- See SECURITY.md for full policy
- We will respond within 48 hours

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## Questions?

- Open a GitHub Discussion for general questions
- Check existing issues and discussions first
- Join our community (link TBD)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to EggAI SDK! 🎉
