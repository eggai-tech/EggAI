.PHONY: services console

services:
	make -j3 agent adapter mcp_backend

agent:
	python start_agent.py

adapter:
	python start_ticket_adapter.py

mcp_backend:
	python start_ticket_backend.py

console:
	python start_console.py