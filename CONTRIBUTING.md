# Contributing to EggAI Multi-Agent Meta Framework

Thank you for considering contributing to **EggAI Multi-Agent Meta Framework**! 🎉 We value your contributions and want to make the process as smooth as possible. Please follow the guidelines below to get started.

---

## Table of Contents
- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
  - [Bug Reports](#bug-reports)
  - [Feature Requests](#feature-requests)
  - [Code Contributions](#code-contributions)
- [Development Workflow](#development-workflow)
- [Commit Message Guidelines](#commit-message-guidelines)
- [Pull Request Guidelines](#pull-request-guidelines)
- [License](#license)

---

## Code of Conduct

Please read our [Code of Conduct](CODE_OF_CONDUCT.md) to ensure that you understand our expectations when interacting with the community.

---

## How Can I Contribute?

### Bug Reports
1. Check if the bug has already been reported in the [Issues](https://github.com/eggai-tech/eggai/issues) section.
2. Create a new issue and include:
   - A clear and descriptive title.
   - Steps to reproduce the bug.
   - Expected and actual results.
   - Relevant logs, screenshots, or error messages.

### Feature Requests
1. Review the [Issues](https://github.com/eggai-tech/eggai/issues) section to see if your idea has already been proposed.
2. Create a new issue and describe:
   - The problem your feature solves.
   - The proposed solution.
   - Alternatives you've considered.

### Code Contributions
1. Look for `good first issue` or `help wanted` tags in the [Issues](https://github.com/eggai-tech/eggai/issues).
2. Discuss your plans in the issue before starting work.
3. Fork the repository and work on a feature branch.

---

## Development Workflow

We have a Makefile at the root of the project that simplifies common development tasks. It's the recommended way to work with the project.

### Option 1: Using the Makefile (Recommended)

1. Clone the repository:
   ```bash
   git clone https://github.com/eggai-tech/eggai.git
   cd eggai
   ```

2. Install all dependencies (SDK, docs, examples):
   ```bash
   make install
   ```
   
   Or install specific components:
   ```bash
   # Install only SDK dependencies
   make install-sdk

   # Install only documentation dependencies
   make install-docs
   ```

   For working with examples, visit [eggai-examples](https://github.com/eggai-tech/eggai-examples).

3. Run tests:
   ```bash
   make test
   ```

4. Clean up:
   ```bash
   # Clean Python cache files
   make clean
   
   # Deep clean (removes virtual environments as well)
   make deep-clean
   ```

### Option 2: SDK Development (Alternative)

If you prefer to work directly in the SDK directory:

1. Navigate to the SDK directory:
   ```bash
   cd sdk
   ```
2. Install dependencies:
   ```bash
   poetry install
   ```
3. Run SDK tests:
   ```bash
   poetry run pytest
   ```

---

## Commit Message Guidelines

We follow the [Conventional Commits](https://www.conventionalcommits.org/) standard for commit messages:
- `feat`: A new feature.
- `fix`: A bug fix.
- `docs`: Documentation changes.
- `style`: Code style changes (formatting, missing semicolons, etc.).
- `refactor`: Code restructuring without functionality changes.
- `test`: Adding or fixing tests.
- `chore`: Maintenance tasks like updating dependencies.

Example:
```plaintext
feat: add new API endpoint for user management
fix: resolve issue with login timeout
```

---

## Pull Request Guidelines

1. Ensure your code adheres to the project's coding standards and style.
2. Ensure all tests pass locally before creating a pull request.
3. **Update `sdk/CHANGELOG.md`** under the `[Unreleased]` section with your changes.
   - Use `### Added`, `### Changed`, `### Fixed`, or `### Removed` subsections.
   - If your PR doesn't require a changelog entry (docs, CI, etc.), add the `skip-changelog` label.
4. Provide a detailed description of your changes in the pull request.
5. Reference the issue you are addressing (if applicable).
6. Be responsive to feedback and make changes as requested.

---

## For Maintainers

### Releasing a New Version

**Stable Release:**
```bash
make release VERSION=0.3.0
```

This command:
1. Verifies you're on `main` branch with clean working directory
2. Checks `[Unreleased]` section in CHANGELOG.md has content
3. Updates version in `pyproject.toml`
4. Converts `[Unreleased]` to `[VERSION] - DATE` in CHANGELOG.md
5. Creates commit and tag `vVERSION`
6. Pushes to origin (triggers PyPI publish and GitHub Release)

**Release Candidate (for testing):**
```bash
make release-rc VERSION=0.3.0rc1
```

Users can test with `pip install eggai==0.3.0rc1`. When stable, run `make release VERSION=0.3.0`.

### Branch Protection Rules

To ensure code quality and prevent accidental changes, the following branch protection rules should be enabled for the `main` branch in GitHub Settings → Branches:

**Required Settings:**
- ✅ **Require pull request before merging**
  - Required approvals: 1
  - Dismiss stale reviews when new commits are pushed
- ✅ **Require status checks to pass before merging**
  - Required checks: `all-checks-passed` (from CI workflow)
- ✅ **Require conversation resolution before merging**
- ✅ **Do not allow bypassing the above settings**
- ✅ **Restrict who can push to matching branches** (optional, recommended for core team only)
- ❌ **Allow force pushes**: Disabled
- ❌ **Allow deletions**: Disabled

These settings ensure that:
1. All changes go through peer review
2. CI checks pass before merging
3. Discussions are resolved
4. The main branch remains stable

---

## License

By contributing to **EggAI Multi-Agent Meta Framework**, you agree that your contributions will be licensed under the [Project License](LICENSE.md).

---

Thank you for contributing to **EggAI Multi-Agent Meta Framework!** 💖