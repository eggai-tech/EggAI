.PHONY: help setup demo demo-bg start-adapters start-react-agent start-console start-simple clean check-deps logs status stop-all

# Default target
help:
	@echo "External Tools Adapter Demo - Available Commands:"
	@echo "================================================"
	@echo ""
	@echo "Quick Start (Kafka assumed running):"
	@echo "  demo            - Start all processes in parallel: make -j demo"
	@echo "  demo-bg         - Start all processes in background"
	@echo ""
	@echo "Individual Components:"
	@echo "  start-filesystem-adapter - Start FileSystem MCP adapter process"
	@echo "  start-react-agent - Start DSPy ReAct agent process"
	@echo "  start-console   - Start console interface"
	@echo ""
	@echo ""
	@echo "Process Management:"
	@echo "  stop-all        - Stop all demo processes"
	@echo "  status          - Show process status"
	@echo "  logs            - Show logs from all processes"
	@echo "  clean           - Clean up all processes and files"
	@echo ""
	@echo "Usage with parallel execution:"
	@echo "  make -j demo    # Start all processes in parallel"

# Setup and dependency checking
setup:
	@echo "🔧 Setting up demo environment..."
	@if [ ! -f "../../../.env" ]; then \
		echo "Creating .env file..."; \
		echo "OPENAI_API_KEY=your_openai_api_key_here" > ../../../.env; \
		echo "⚠️  Please edit .env and add your OpenAI API key"; \
	fi
	@echo "✅ Setup complete"

check-deps:
	@echo "🔍 Checking dependencies..."
	@python3 -c "import dspy, eggai, mcp, httpx, aioconsole" 2>/dev/null || \
		(echo "❌ Missing dependencies. Run: pip install -r ../requirements.txt" && exit 1)
	@if [ -z "$$OPENAI_API_KEY" ]; then \
		echo "⚠️  OPENAI_API_KEY not set. Please export it: export OPENAI_API_KEY=your-key"; \
	else \
		echo "✅ OpenAI API key found"; \
	fi
	@echo "✅ Dependencies check complete"

# Individual process targets (for parallel execution)
start-filesystem-adapter:
	@mkdir -p logs
	@python3 start_filesystem_adapter.py 2>&1 | tee logs/filesystem-adapter.log

start-react-agent: check-deps
	@mkdir -p logs
	@python3 start_react_agent.py 2>&1 | tee logs/react-agent.log

start-console: check-deps
	@mkdir -p logs
	@python3 start_console.py 2>&1 | tee logs/console.log


# Parallel demo target - use with make -j demo
demo: start-filesystem-adapter start-react-agent start-console

# Background processes
start-filesystem-adapter-bg:
	@echo "📁 Starting FileSystem MCP adapter in background..."
	@mkdir -p logs
	@python3 start_filesystem_adapter.py > logs/filesystem-adapter.log 2>&1 & echo $$! > logs/filesystem-adapter.pid
	@sleep 2
	@echo "✅ FileSystem adapter started (PID: `cat logs/filesystem-adapter.pid`)"

start-react-agent-bg: check-deps
	@echo "🧠 Starting DSPy ReAct agent in background..."
	@mkdir -p logs
	@python3 start_react_agent.py > logs/react-agent.log 2>&1 & echo $$! > logs/react-agent.pid
	@sleep 3
	@echo "✅ ReAct agent started (PID: `cat logs/react-agent.pid`)"

start-console-bg: check-deps
	@echo "💬 Starting console interface in background..."
	@mkdir -p logs  
	@python3 start_console.py > logs/console.log 2>&1 & echo $$! > logs/console.pid
	@echo "✅ Console interface started (PID: `cat logs/console.pid`)"

# Background demo
demo-bg: start-filesystem-adapter-bg start-react-agent-bg
	@echo "🎉 All processes started in background!"
	@echo "📊 Use 'make status' to check processes"
	@echo "📝 Use 'make logs' to view logs"
	@echo "💬 Run 'make start-console' to start interactive session"

# Process management
stop-all:
	@echo "🛑 Stopping all processes..."
	@if [ -f logs/filesystem-adapter.pid ]; then \
		kill `cat logs/filesystem-adapter.pid` 2>/dev/null || true; \
		rm logs/filesystem-adapter.pid; \
		echo "✅ FileSystem adapter stopped"; \
	fi
	@if [ -f logs/react-agent.pid ]; then \
		kill `cat logs/react-agent.pid` 2>/dev/null || true; \
		rm logs/react-agent.pid; \
		echo "✅ ReAct agent stopped"; \
	fi
	@if [ -f logs/console.pid ]; then \
		kill `cat logs/console.pid` 2>/dev/null || true; \
		rm logs/console.pid; \
		echo "✅ Console interface stopped"; \
	fi
	@echo "✅ All processes stopped"

# Monitoring
status:
	@echo "📊 Process Status:"
	@echo "=================="
	@echo -n "FileSystem Adapter: "
	@if [ -f logs/filesystem-adapter.pid ] && kill -0 `cat logs/filesystem-adapter.pid` 2>/dev/null; then \
		echo "✅ Running (PID: `cat logs/filesystem-adapter.pid`)"; \
	else \
		echo "❌ Not running"; \
	fi
	@echo -n "ReAct Agent: "
	@if [ -f logs/react-agent.pid ] && kill -0 `cat logs/react-agent.pid` 2>/dev/null; then \
		echo "✅ Running (PID: `cat logs/react-agent.pid`)"; \
	else \
		echo "❌ Not running"; \
	fi
	@echo -n "Console Interface: "
	@if [ -f logs/console.pid ] && kill -0 `cat logs/console.pid` 2>/dev/null; then \
		echo "✅ Running (PID: `cat logs/console.pid`)"; \
	else \
		echo "❌ Not running"; \
	fi

logs:
	@echo "📋 Recent Process Logs:"
	@echo "======================"
	@if [ -f logs/filesystem-adapter.log ]; then \
		echo "📁 FileSystem Adapter (last 10 lines):"; \
		tail -10 logs/filesystem-adapter.log; \
		echo ""; \
	fi
	@if [ -f logs/react-agent.log ]; then \
		echo "🧠 ReAct Agent (last 10 lines):"; \
		tail -10 logs/react-agent.log; \
		echo ""; \
	fi
	@if [ -f logs/console.log ]; then \
		echo "💬 Console Interface (last 10 lines):"; \
		tail -10 logs/console.log; \
		echo ""; \
	fi

# Cleanup
clean:
	@echo "🧹 Cleaning up..."
	@make stop-all 2>/dev/null || true
	@rm -rf logs/
	@rm -f *.pyc
	@rm -rf __pycache__/
	@rm -rf ../__pycache__/
	@echo "✅ Cleanup complete"

# Testing
test-system: demo-bg
	@echo "🧪 Testing complete system..."
	@sleep 5
	@echo "Testing FileSystem adapter connectivity..."
	@python3 -c "import asyncio; \
		import sys; sys.path.insert(0, '..'); \
		from agent_integration import setup_external_tools; \
		async def test(): \
			tm = await setup_external_tools('Test', ['FileSystem']); \
			tools = tm.get_all_tools(); \
			print(f'✅ Found {len(tools)} tools: {[t.name for t in tools]}'); \
		asyncio.run(test())" || true
	@echo "🎉 System test complete!"

# Development
dev-setup: setup
	@echo "🔧 Setting up development environment..."
	@pip install -r ../requirements.txt
	@echo "✅ Development setup complete"