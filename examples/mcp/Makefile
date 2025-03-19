PYTHON := python
VENV_DIR := .venv
REQ_FILE := requirements.txt
DEV_REQ_FILE := dev-requirements.txt
DOCKER_COMPOSE := docker compose
SHELL := $(shell which bash)

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
