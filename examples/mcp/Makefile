.PHONY: setup start docker-up docker-down clean

PYTHON := python3
VENV_DIR := .venv
REQ_FILE := requirements.txt
DEV_REQ_FILE := dev-requirements.txt
DOCKER_COMPOSE := docker compose
SHELL := $(shell which bash)

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

start:
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/python main.py

docker-up:
	@echo "Starting Docker Compose..."
	@$(DOCKER_COMPOSE) up -d
	@echo "Docker Compose started."

docker-down:
	@echo "Stopping and cleaning up Docker Compose..."
	@$(DOCKER_COMPOSE) down -v
	@echo "Docker Compose stopped and cleaned up."

clean:
	@echo "Cleaning up the environment..."
	@rm -rf $(VENV_DIR)
	@echo "Environment cleaned."