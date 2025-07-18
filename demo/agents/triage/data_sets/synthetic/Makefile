.PHONY: setup start stop rebuild db clean venv install install-dev run-web run-gen test

# Variables
PYTHON = python
PIP = pip
VENV_DIR = .venv
DOCKER_COMPOSE = docker-compose

# Main targets
setup: venv install-dev ## Setup development environment

start: ## Start the application with Docker
	$(DOCKER_COMPOSE) up -d
	@echo "Triage Toolkit started on http://localhost:8000"
	@echo "View logs with: make logs"

stop: ## Stop the application
	$(DOCKER_COMPOSE) down

db: ## Start only the database
	$(DOCKER_COMPOSE) up -d db
	@echo "PostgreSQL database started"

rebuild: ## Rebuild and start the application
	$(DOCKER_COMPOSE) up -d --build

logs: ## Show Docker container logs
	$(DOCKER_COMPOSE) logs -f

clean: ## Clean up temporary files and build artifacts
	rm -rf build/ dist/ *.egg-info/ **/__pycache__/ **/*.pyc **/*.pyo .pytest_cache/ .coverage htmlcov/

# Development environment targets
venv: ## Create a virtual environment
	$(PYTHON) -m venv $(VENV_DIR)
	@echo "Virtual environment created at $(VENV_DIR)"
	@echo "Activate with: source $(VENV_DIR)/bin/activate (Unix/macOS) or $(VENV_DIR)\\Scripts\\activate (Windows)"

install: ## Install the package
	$(PIP) install -e .

install-dev: install ## Install the package with development dependencies
	$(PIP) install -e ".[dev]"

# Local development targets (without Docker)
run-web: ## Run the web server (without Docker)
	$(PYTHON) dev_webserver.py

run-gen: ## Run the dataset generator (without Docker)
	$(PYTHON) dev_generator.py

# Testing targets
test: ## Run tests
	pytest

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# We're using Tailwind CSS CDN, so no build steps are needed

# Default target
.DEFAULT_GOAL := help