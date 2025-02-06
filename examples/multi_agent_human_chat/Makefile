PYTHON := python3.12
VENV_DIR := .venv
REQ_FILE := requirements.txt
DEV_REQ_FILE := dev-requirements.txt
DOCKER_COMPOSE := docker compose

.PHONY: default
default: start

.PHONY: setup
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

.PHONY: start
start: setup docker-up start-all
	@echo "Environment, Docker Compose, and agents are running."

# test
.PHONY: test
test:
	@echo "Running tests..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest -s
	@echo "Tests completed."

.PHONY: stop
stop: docker-down
	@echo "Environment and Docker Compose have been stopped."

.PHONY: clean
clean:
	@echo "Cleaning up the environment..."
	@rm -rf $(VENV_DIR)
	@echo "Environment cleaned."

.PHONY: full-reset
full-reset: clean docker-down
	@echo "Full reset completed. All containers, volumes, and environments have been removed."

.PHONY: docker-up
docker-up:
	@echo "Starting Docker Compose..."
	@$(DOCKER_COMPOSE) up -d
	@echo "Docker Compose started."

.PHONY: docker-down
docker-down:
	@echo "Stopping and cleaning up Docker Compose..."
	@$(DOCKER_COMPOSE) down -v
	@echo "Docker Compose stopped and cleaned up."

.PHONY: start-frontend
start-frontend:
	@echo "Starting Frontend Agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/python -m agents.frontend.main

.PHONY: start-billing
start-billing:
	@echo "Starting Billing Agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/python -m agents.billing.main

.PHONY: start-escalation
start-escalation:
	@echo "Starting Escalation Agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/python -m agents.escalation.main

.PHONY: start-policies
start-policies:
	@echo "Starting Policies Agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/python -m agents.policies.main

.PHONY: start-triage
start-triage:
	@echo "Starting Triage Agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/python -m agents.triage.main

.PHONY: start-all
start-all:
	@echo "Starting all agents..."
	@make -j start-frontend start-billing start-escalation start-policies start-triage

.PHONY: restart
restart: stop start
	@echo "Environment and Docker Compose have been restarted."

.PHONY: setup-and-run
setup-and-run: setup start
	@echo "Setup and all services started."
