PYTHON := python
VENV_DIR := .venv
REQ_FILE := requirements.txt
DEV_REQ_FILE := dev-requirements.txt
DOCKER_COMPOSE := docker compose
SHELL := $(shell which bash)

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
	@echo "Checking dependencies..."
	@command -v uvx >/dev/null 2>&1 || { echo "uvx not found, installing..."; $(VENV_DIR)/bin/pip install uvx; }
	@command -v npx >/dev/null 2>&1 || { echo "npx not found, installing..."; npm install -g npx; }
	@echo "Environment setup complete."

.PHONY: start-mcp-fetch
start-mcp-fetch:
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/python -m mcp_servers.fetch

.PHONY: start-mcp-filesystem
start-mcp-filesystem:
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/python -m mcp_servers.filesystem

.PHONY: start-mcp-chat
start-mcp-chat:
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/python -m main

.PHONY: start-all
start-all:
	@make -j start-mcp-fetch start-mcp-filesystem start-mcp-chat

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

.PHONY: clean
clean:
	@echo "Cleaning up the environment..."
	@rm -rf $(VENV_DIR)
	@echo "Environment cleaned."