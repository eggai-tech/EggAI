# EggAI SDK Makefile
# For examples, see: https://github.com/eggai-tech/eggai-examples

PYTHON ?= python3.12
VENV_NAME ?= .venv

.PHONY: install install-sdk install-docs test lint format clean deep-clean publish release

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

# Release a new version
# Usage: make release VERSION=0.2.9
release:
ifndef VERSION
	$(error VERSION is required. Usage: make release VERSION=0.2.9)
endif
	@echo "Preparing release v$(VERSION)..."
	@# Check we're on main branch
	@if [ "$$(git branch --show-current)" != "main" ]; then \
		echo "Error: Must be on main branch to release"; \
		exit 1; \
	fi
	@# Check working directory is clean
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "Error: Working directory is not clean. Commit or stash changes first."; \
		exit 1; \
	fi
	@# Check [Unreleased] section has content
	@if ! grep -A 5 "## \[Unreleased\]" sdk/CHANGELOG.md | grep -qE "^### "; then \
		echo "Error: No changes found under [Unreleased] in CHANGELOG.md"; \
		exit 1; \
	fi
	@# Update version in pyproject.toml
	@sed -i.bak 's/^version = ".*"/version = "$(VERSION)"/' sdk/pyproject.toml && rm sdk/pyproject.toml.bak
	@echo "Updated sdk/pyproject.toml"
	@# Update version in __init__.py
	@sed -i.bak 's/__version__ = ".*"/__version__ = "$(VERSION)"/' sdk/eggai/__init__.py && rm sdk/eggai/__init__.py.bak
	@echo "Updated sdk/eggai/__init__.py"
	@# Update CHANGELOG.md - replace [Unreleased] with [VERSION] - DATE
	@DATE=$$(date +%Y-%m-%d); \
	sed -i.bak "s/## \[Unreleased\]/## [Unreleased]\n\n## [$(VERSION)] - $$DATE/" sdk/CHANGELOG.md && rm sdk/CHANGELOG.md.bak
	@echo "Updated sdk/CHANGELOG.md"
	@# Commit and tag
	@git add sdk/pyproject.toml sdk/eggai/__init__.py sdk/CHANGELOG.md
	@git commit -m "chore: release v$(VERSION)"
	@git tag -a "v$(VERSION)" -m "Release v$(VERSION)"
	@echo "Created commit and tag v$(VERSION)"
	@# Push
	@git push origin main
	@git push origin "v$(VERSION)"
	@echo ""
	@echo "Release v$(VERSION) complete!"
	@echo "GitHub Actions will now build and publish to PyPI."