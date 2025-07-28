.PHONY: server console docker-up

server:
	make -j3 agent adapter mcp_backend

agent:
	python start_ticketing_agent.py

adapter:
	python start_ticketing_adapter.py

mcp_backend:
	python start_ticketing_backend.py

console:
	python start_console.py

docker-up:
	docker-compose up -d