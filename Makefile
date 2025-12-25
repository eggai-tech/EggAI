# EggAI SDK Makefile
# For examples, see: https://github.com/eggai-tech/eggai-examples

PYTHON ?= python3.12
VENV_NAME ?= .venv

.PHONY: install install-sdk install-docs test lint format clean deep-clean publish

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