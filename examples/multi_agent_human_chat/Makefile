.PHONY: default setup start test test-billing test-escalation test-frontend test-policies test-triage-classifier-v1 test-triage-classifier-v2 test-triage-classifier-v3 compile-triage-classifier-v2 test-triage-agent test-audit stop clean full-reset docker-up docker-down start-frontend start-billing start-escalation start-policies start-claims start-triage start-audit start-all restart setup-triage setup-and-run

PYTHON := python3.11
VENV_DIR := .venv
REQ_FILE := requirements.txt
DEV_REQ_FILE := dev-requirements.txt
DOCKER_COMPOSE := docker compose
SHELL := $(shell which bash)


default: start

train-triage-classifier-v3:
	@echo "Training triage classifier v3..."
	@source $(VENV_DIR)/bin/activate && PYTHONPATH=. $(VENV_DIR)/bin/python agents/triage/baseline_model/fewshot_trainer.py

test-triage-classifier-v3:
	@echo "Evaluating the triage classifier v3..."
	@source $(VENV_DIR)/bin/activate && PYTHONPATH=. $(VENV_DIR)/bin/python agents/triage/baseline_model/fewshot_eval.py

setup:
	@echo "Setting up the environment..."
	@if [ ! -d "$(VENV_DIR)" ]; then \
		$(PYTHON) -m venv $(VENV_DIR); \
		echo "Virtual environment created."; \
	else \
		echo "Virtual environment already exists."; \
	fi
	@$(VENV_DIR)/bin/pip install --upgrade pip
	@if [ -f $(REQ_FILE) ]; then $(VENV_DIR)/bin/pip install -r $(REQ_FILE); fi
	@if [ -f $(DEV_REQ_FILE) ]; then $(VENV_DIR)/bin/pip install -r $(DEV_REQ_FILE); fi
	@echo "Environment setup complete."

start: setup docker-up setup-triage start-all
	@echo "Environment, Docker Compose, and agents are running."

test:
	@echo "Running tests..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest -s
	@echo "Tests completed."

test-billing:
	@echo "Running tests for billing agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest agents/billing -s
	@echo "Tests for billing agent completed."

test-escalation:
	@echo "Running tests for escalation agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest agents/escalation -s
	@echo "Tests for escalation agent completed."

test-frontend:
	@echo "Running tests for frontend agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest agents/frontend -s
	@echo "Tests for frontend agent completed."

test-policies:
	@echo "Running tests for policies agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest agents/policies -s
	@echo "Tests for policies agent completed."

test-triage-classifier-v1:
	@echo "Running tests classifier v1 for triage agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest agents/triage/tests/test_classifier_v1.py -s \
       --junitxml=reports/pytest-results.xml \
       --html=reports/pytest-results.html --self-contained-html

test-triage-classifier-v2:
	@echo "Running test classifier v2 for triage agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest agents/triage/tests/test_classifier_v2.py -s

test-triage-classifier-v3:
	@echo "Running tests classifier v3 for triage agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest agents/triage/tests/test_classifier_v3.py -s

test-triage-agent:
	@echo "Running tests for triage agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest agents/triage/tests/test_agent.py -s \
       --junitxml=reports/pytest-results.xml \
       --html=reports/pytest-results.html --self-contained-html
	@echo "Tests for triage agent completed."

test-audit:
	@echo "Running tests for audit agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest agents/audit -s
	@echo "Tests for audit agent completed."

stop: docker-down
	@echo "Environment and Docker Compose have been stopped."

clean:
	@echo "Cleaning up the environment..."
	@rm -rf $(VENV_DIR)
	@echo "Environment cleaned."

full-reset: clean docker-down
	@echo "Full reset completed. All containers, volumes, and environments have been removed."

docker-up:
	@echo "Starting Docker Compose..."
	@$(DOCKER_COMPOSE) up -d
	@echo "Docker Compose started."

docker-down:
	@echo "Stopping and cleaning up Docker Compose..."
	@$(DOCKER_COMPOSE) down -v
	@echo "Docker Compose stopped and cleaned up."

start-frontend:
	@echo "Starting Frontend Agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/python -m agents.frontend.main

start-billing:
	@echo "Starting Billing Agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/python -m agents.billing.main

start-escalation:
	@echo "Starting Escalation Agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/python -m agents.escalation.main

start-policies:
	@echo "Starting Policies Agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/python -m agents.policies.main

start-claims:
	@echo "Starting Claims Agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/python -m agents.claims.main

start-triage:
	@echo "Starting Triage Agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/python -m agents.triage.main

start-audit:
	@echo "Starting Audit Agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/python -m agents.audit.main

start-all:
	@echo "Starting all agents..."
	@make -j start-frontend start-billing start-escalation start-policies start-triage start-audit start-claims

restart: stop start
	@echo "Environment and Docker Compose have been restarted."


compile-triage-classifier-v2:
	@echo "Compiling Classifier Dspy Optimizer..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/python -m agents.triage.dspy_modules.classifier_v2.classifier_v2_optimizer
	@echo "Triage Agent setup completed."

setup-triage:
	@echo "Setting up Triage Agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/python -m agents.triage.mlflow_experiments.upload_checkpoints
	@echo "Triage Agent setup completed."

setup-and-run: setup setup-triage start
	@echo "Setup and all services started."