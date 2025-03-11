# EggAI Main Makefile

PYTHON ?= python3.12
VENV_NAME ?= .venv

.PHONY: install install-sdk install-docs install-examples test-all test-sdk test-example clean

# Install all sub-projects
install: install-sdk install-docs install-examples

# Install SDK
install-sdk:
	@echo "Installing SDK dependencies..."
	cd sdk && poetry install

# Install docs
install-docs:
	@echo "Installing documentation dependencies..."
	cd docs && poetry install

# Install specific example
install-example:
	@if [ -z "$(EXAMPLE)" ]; then \
		echo "Usage: make install-example EXAMPLE=example_name"; \
		exit 1; \
	fi
	@echo "Setting up examples/$(EXAMPLE)"
	@if [ -f examples/$(EXAMPLE)/Makefile ]; then \
		(cd examples/$(EXAMPLE) && make setup); \
	else \
		(cd examples/$(EXAMPLE) && $(PYTHON) -m venv $(VENV_NAME) && \
		$(VENV_NAME)/bin/pip install --upgrade pip && \
		$(VENV_NAME)/bin/pip install -r requirements.txt); \
	fi

# Install all examples
install-examples:
	@echo "Installing examples dependencies..."
	@for dir in examples/*; do \
		if [ -f $$dir/requirements.txt ]; then \
			echo "Setting up $$dir"; \
			if [ -f $$dir/Makefile ]; then \
				(cd $$dir && make setup || echo "⚠️  Setup failed for $$dir, but continuing..."); \
			else \
				(cd $$dir && $(PYTHON) -m venv $(VENV_NAME) && \
				$(VENV_NAME)/bin/pip install --upgrade pip && \
				$(VENV_NAME)/bin/pip install -r requirements.txt || \
				echo "⚠️  Installation failed for $$dir, but continuing..."); \
			fi; \
		fi; \
	done

# Run all tests
test-all:
	$(PYTHON) -m scripts.run_all_tests

# Run SDK tests only
test-sdk:
	$(PYTHON) -m scripts.run_tests sdk

# Run specific example tests
test-example:
	@if [ -z "$(EXAMPLE)" ]; then \
		echo "Usage: make test-example EXAMPLE=example_name"; \
		exit 1; \
	fi
	@echo "Running tests for $(EXAMPLE)..."
	@if [ -d "examples/$(EXAMPLE)/tests" ] && ls examples/$(EXAMPLE)/tests/test_*.py >/dev/null 2>&1; then \
		$(PYTHON) -m scripts.run_tests $(EXAMPLE) || echo "⚠️  Tests failed for $(EXAMPLE), but continuing..."; \
	else \
		echo "ℹ️  No tests found for $(EXAMPLE)"; \
	fi

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

# Deep clean - removes virtual environments as well
deep-clean: clean
	@echo "Removing virtual environments..."
	find . -type d -name "$(VENV_NAME)" -exec rm -rf {} + 2>/dev/null || true