# EggAI SDK Makefile
# For examples, see: https://github.com/eggai-tech/eggai-examples

PYTHON ?= python3.12
VENV_NAME ?= .venv

.PHONY: install install-sdk install-docs test lint format clean deep-clean publish release release-rc

# Install SDK and docs
install: install-sdk install-docs

# Install SDK
install-sdk:
	@echo "Installing SDK dependencies..."
	cd sdk && poetry install

# Install docs
install-docs:
	@echo "Installing documentation dependencies..."
	cd docs && poetry install

# Run SDK tests
test:
	@echo "Running SDK tests..."
	cd sdk && poetry run pytest -v

# Lint SDK code
lint:
	@echo "Linting SDK code..."
	cd sdk && poetry run ruff check .

# Format SDK code
format:
	@echo "Formatting SDK code..."
	cd sdk && poetry run ruff format .

# Build SDK package
build:
	@echo "Building SDK package..."
	cd sdk && poetry build

# Publish to PyPI (requires credentials)
publish: build
	@echo "Publishing to PyPI..."
	cd sdk && poetry publish

# Clean Python cache files
clean:
	@echo "Cleaning Python cache files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type f -name "*.pyd" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true

# Deep clean - removes virtual environments as well
deep-clean: clean
	@echo "Removing virtual environments..."
	find . -type d -name "$(VENV_NAME)" -exec rm -rf {} + 2>/dev/null || true

# Release a new version (creates PR, auto-tags on merge)
# Usage: make release VERSION=0.2.9
release:
ifndef VERSION
	$(error VERSION is required. Usage: make release VERSION=0.2.9)
endif
	@echo "Preparing release v$(VERSION)..."
	@# Check we're on main branch
	@if [ "$$(git branch --show-current)" != "main" ]; then \
		echo "Error: Must be on main branch to start release"; \
		exit 1; \
	fi
	@# Check working directory is clean
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "Error: Working directory is not clean. Commit or stash changes first."; \
		exit 1; \
	fi
	@# Ensure we're up to date
	@git pull origin main
	@# Check [Unreleased] section has content
	@if ! grep -A 5 "## \[Unreleased\]" sdk/CHANGELOG.md | grep -qE "^### "; then \
		echo "Error: No changes found under [Unreleased] in CHANGELOG.md"; \
		exit 1; \
	fi
	@# Create release branch
	@git checkout -b release/v$(VERSION)
	@# Update version in pyproject.toml
	@sed -i.bak 's/^version = ".*"/version = "$(VERSION)"/' sdk/pyproject.toml && rm sdk/pyproject.toml.bak
	@echo "Updated sdk/pyproject.toml"
	@# Update CHANGELOG.md - add version section with date
	@DATE=$$(date +%Y-%m-%d); \
	sed -i.bak "s/## \[Unreleased\]/## [Unreleased]\n\n## [$(VERSION)] - $$DATE/" sdk/CHANGELOG.md && rm sdk/CHANGELOG.md.bak
	@echo "Updated sdk/CHANGELOG.md"
	@# Commit
	@git add sdk/pyproject.toml sdk/CHANGELOG.md
	@git commit -m "chore: release v$(VERSION)"
	@# Push branch
	@git push -u origin release/v$(VERSION)
	@# Create PR with release label
	@gh pr create --title "chore: release v$(VERSION)" \
		--body "Release v$(VERSION)" \
		--label "release"
	@echo ""
	@echo "Release PR created for v$(VERSION)!"
	@echo "After PR is merged, the tag will be created automatically."
	@echo ""
	@echo "To complete: merge the PR on GitHub"

# Release a release candidate for testing (creates PR, auto-tags on merge)
# Usage: make release-rc VERSION=0.3.0rc1
release-rc:
ifndef VERSION
	$(error VERSION is required. Usage: make release-rc VERSION=0.3.0rc1)
endif
	@# Validate version format (must contain rc, alpha, or beta)
	@if ! echo "$(VERSION)" | grep -qE "(rc|alpha|beta)[0-9]+$$"; then \
		echo "Error: VERSION must be a pre-release (e.g., 0.3.0rc1, 0.3.0alpha1, 0.3.0beta1)"; \
		exit 1; \
	fi
	@echo "Preparing release candidate v$(VERSION)..."
	@# Check we're on main branch
	@if [ "$$(git branch --show-current)" != "main" ]; then \
		echo "Error: Must be on main branch to start release"; \
		exit 1; \
	fi
	@# Check working directory is clean
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "Error: Working directory is not clean. Commit or stash changes first."; \
		exit 1; \
	fi
	@# Ensure we're up to date
	@git pull origin main
	@# Create release branch
	@git checkout -b release/v$(VERSION)
	@# Update version in pyproject.toml
	@sed -i.bak 's/^version = ".*"/version = "$(VERSION)"/' sdk/pyproject.toml && rm sdk/pyproject.toml.bak
	@echo "Updated sdk/pyproject.toml"
	@# Commit (no changelog update for RCs)
	@git add sdk/pyproject.toml
	@git commit -m "chore: release v$(VERSION)"
	@# Push branch
	@git push -u origin release/v$(VERSION)
	@# Create PR with release and skip-changelog labels
	@gh pr create --title "chore: release v$(VERSION)" \
		--body "Release candidate v$(VERSION) for testing.\n\nInstall with: \`pip install eggai==$(VERSION)\`" \
		--label "release" --label "skip-changelog"
	@echo ""
	@echo "Release candidate PR created for v$(VERSION)!"
	@echo "After PR is merged, the tag will be created automatically."
	@echo ""
	@echo "To complete: merge the PR on GitHub"