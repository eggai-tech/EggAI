.PHONY: default setup start test test-billing-agent test-claims-agent test-escalation-agent test-frontend-agent test-policies-agent test-policies-retrieval-performance test-triage-classifier-v0 test-triage-classifier-v1 test-triage-classifier-v2 test-triage-classifier-v3 test-triage-classifier-v4 test-triage-classifier-v5 test-triage-classifier-v6 test-triage-classifier-v7 test-triage-classifier-v6-evaluation test-triage-classifier-v7-evaluation test-triage-classifiers-evaluation test-triage-classifiers-comprehensive test-triage-classifiers-comparison test-triage-classifiers-unit test-triage-classifiers-config test-triage-classifiers-coverage test-triage-classifiers-all eval-triage-classifier-v0 eval-triage-classifier-v1 eval-triage-classifier-v2 eval-triage-classifier-v3 eval-triage-classifier-v4 eval-triage-classifier-v5 eval-triage-classifier-v6 eval-triage-classifier-v7 eval-all-triage-classifiers eval-latest-triage-classifiers check-triage-classifier-v6-setup train-triage-classifier-v6 train-triage-classifier-v7 serve-triage-classifier-v7 invoke-triage-classifier-v7 compile-triage-classifier-v2 compile-triage-classifier-v4 compile-billing-optimizer compile-claims-optimizer compile-policies-optimizer compile-escalation-optimizer compile-all test-triage-agent test-audit test-libraries stop kill-agents clean full-reset docker-up docker-down start-frontend start-billing start-escalation start-policies start-claims start-triage start-audit start-policies-document-ingestion start-all restart setup-and-run lint lint-fix build-policy-rag-index drop-vespa-index deploy-vespa-schema

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

train-triage-classifier-v5:
	@echo "Training triage classifier v5..."
	@source $(VENV_DIR)/bin/activate && PYTHONPATH=. $(VENV_DIR)/bin/python agents/triage/attention_net/attention_net_trainer.py

train-triage-classifier-v6:
	@echo "Training triage classifier v6 (OpenAI fine-tuned model)..."
	@echo "💡 Default: 20 examples (~\$$0.40 for demo)"
	@echo "💡 Custom: export FINETUNE_SAMPLE_SIZE=100 (or -1 for full dataset)"
	@echo "⚠️  Requires OPENAI_API_KEY environment variable"
	@source $(VENV_DIR)/bin/activate && PYTHONPATH=. $(VENV_DIR)/bin/python agents/triage/classifier_v6/finetune_trainer.py

train-triage-classifier-v7:
	@echo "Training triage classifier v7 (Gemma3 via HuggingFace)..."
	@echo "💡 Default: 100 examples (LoRA fine-tuning)"
	@echo "💡 Custom: export FINETUNE_SAMPLE_SIZE=200 (or -1 for full dataset)"
	@echo "⚠️  Requires: pip install transformers peft datasets accelerate bitsandbytes"
	@source $(VENV_DIR)/bin/activate && export MLFLOW_TRACKING_URI=http://localhost:5001 && PYTHONPATH=. $(VENV_DIR)/bin/python agents/triage/classifier_v7/finetune_trainer.py

serve-triage-classifier-v7:
	@echo "Serving triage classifier v7 via MLflow..."
	@echo "💡 Default port: 5000"
	@echo "💡 Custom: make serve-triage-classifier-v7 PORT=5001"
	@source $(VENV_DIR)/bin/activate && \
	export MLFLOW_TRACKING_URI=http://localhost:5001 && \
	export MLFLOW_S3_ENDPOINT_URL=http://localhost:9000 && \
	export AWS_ACCESS_KEY_ID=user && \
	export AWS_SECRET_ACCESS_KEY=password && \
	MODEL_URI=$$(python3 -c "import mlflow; exp = mlflow.get_experiment_by_name('triage_classifier'); runs = mlflow.search_runs(experiment_ids=[exp.experiment_id], order_by=['start_time DESC'], max_results=1) if exp else None; print(f'runs:/{runs.iloc[0][\"run_id\"]}/model' if runs is not None and not runs.empty else 'No models found')"); \
	if [ "$$MODEL_URI" != "No models found" ]; then \
		echo "📡 Serving model: $$MODEL_URI"; \
		echo "🌐 API endpoint: http://127.0.0.1:$${PORT:-5000}/invocations"; \
		mlflow models serve -m "$$MODEL_URI" -p $${PORT:-5000} --env-manager local; \
	else \
		echo "❌ No trained models found. Run 'make train-triage-classifier-v7' first."; \
	fi

invoke-triage-classifier-v7:
	@echo "Testing triage classifier v7 API..."
	@echo "💡 Default: 'User: I want to know my policy due date.'"
	@echo "💡 Custom: make invoke-triage-classifier-v7 TEXT='Your message here' PORT=5001"
	@curl -X POST http://127.0.0.1:$${PORT:-5000}/invocations \
		-H 'Content-Type: application/json' \
		-d '{"inputs": ["$${TEXT:-User: I want to know my policy due date.}"]}' \
		2>/dev/null | python3 -m json.tool || echo "❌ Service not running on port $${PORT:-5000}"

start-eda-notebook:
	@echo "Start Exploratory Data Analysis Notebook..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/jupyter-notebook agents/triage/notebooks/exploratory_data_analysis.ipynb --port=8888


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

start: setup docker-up start-all
	@echo "Environment, Docker Compose, and agents are running."

test:
	@echo "Running tests..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest -s \
       --cov=agents --cov-report=xml:coverage.xml --cov-report=term \
       --junitxml=reports/pytest-results.xml \
       --html=reports/pytest-results.html --self-contained-html
	@echo "Running classifier tests for CI coverage..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest agents/triage/tests/test_classifier_v6.py agents/triage/tests/test_classifier_v7.py -s \
       --cov=agents.triage.classifier_v6 --cov=agents.triage.classifier_v7 --cov-append \
       --cov-report=xml:coverage.xml --cov-report=term
	@echo "Tests completed."

test-billing-agent:
	@echo "Running tests for billing agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest agents/billing -s \
       --cov=agents.billing --cov-report=xml:coverage.xml --cov-report=term --cov-append \
       --junitxml=reports/pytest-results.xml \
       --html=reports/pytest-results.html --self-contained-html
	@echo "Tests for billing agent completed."

test-claims-agent:
	@echo "Running tests for claims agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest agents/claims -s \
       --cov=agents.claims --cov-report=xml:coverage.xml --cov-report=term --cov-append \
       --junitxml=reports/pytest-results.xml \
       --html=reports/pytest-results.html --self-contained-html
	@echo "Tests for claims agent completed."

test-escalation-agent:
	@echo "Running tests for escalation agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest agents/escalation -s \
       --cov=agents.escalation --cov-report=xml:coverage.xml --cov-report=term --cov-append \
       --junitxml=reports/pytest-results.xml \
       --html=reports/pytest-results.html --self-contained-html
	@echo "Tests for escalation agent completed."

test-frontend-agent:
	@echo "Running tests for frontend agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest agents/frontend -s \
       --cov=agents.frontend --cov-report=xml:coverage.xml --cov-report=term --cov-append \
       --junitxml=reports/pytest-results.xml \
       --html=reports/pytest-results.html --self-contained-html
	@echo "Tests for frontend agent completed."

test-policies-agent:
	@echo "Running tests for policies agent..."
	@echo "Document indexing is handled by the policies ingestion service..."
	@echo "Starting Policy Documentation Temporal Worker in background..."
	@source $(VENV_DIR)/bin/activate && PYTHONPATH=. $(VENV_DIR)/bin/python agents/policies/ingestion/start_worker.py & \
	WORKER_PID=$$!; \
	sleep 3; \
	echo "Running pytest with temporal worker running..."; \
	$(VENV_DIR)/bin/pytest agents/policies -s \
       --cov=agents.policies --cov-report=xml:coverage.xml --cov-report=term --cov-append \
       --junitxml=reports/pytest-results.xml \
       --html=reports/pytest-results.html --self-contained-html; \
	TEST_EXIT_CODE=$$?; \
	echo "Stopping Policy Documentation Temporal Worker..."; \
	kill $$WORKER_PID 2>/dev/null || true; \
	wait $$WORKER_PID 2>/dev/null || true; \
	echo "Tests for policies agent completed."; \
	exit $$TEST_EXIT_CODE

test-policies-retrieval-performance:
	@source $(VENV_DIR)/bin/activate && PYTHONPATH=. LIMIT_DATASET_ITEMS=5 $(VENV_DIR)/bin/pytest agents/policies/tests/test_retrieval_performance.py \
       -v -s \
       --junitxml=reports/pytest-policies-retrieval-performance.xml \
       --html=reports/pytest-results.html --self-contained-html



test-triage-classifier-v0:
	@echo "Running tests for basic classifier v0 (minimal prompt)..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest agents/triage/tests/test_classifier_v0.py -s \
       --junitxml=reports/pytest-results.xml \
       --html=reports/pytest-results.html --self-contained-html

test-triage-classifier-v1:
	@echo "Running tests classifier v1 for triage agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest agents/triage/tests/test_classifier_v1.py -s \
       --junitxml=reports/pytest-results.xml \
       --html=reports/pytest-results.html --self-contained-html

test-triage-classifier-v2:
	@echo "Running test classifier v2 for triage agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest agents/triage/tests/test_classifier_v2.py -s \
       --junitxml=reports/pytest-results.xml \
       --html=reports/pytest-results.html --self-contained-html

test-triage-classifier-v3:
	@echo "Running tests classifier v3 for triage agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest agents/triage/tests/test_classifier_v3.py -s \
       --junitxml=reports/pytest-results.xml \
       --html=reports/pytest-results.html --self-contained-html
       
test-triage-classifier-v4:
	@echo "Running tests classifier v4 for triage agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest agents/triage/tests/test_classifier_v4.py -s \
       --junitxml=reports/pytest-results.xml \
       --html=reports/pytest-results.html --self-contained-html

test-triage-classifier-v5:
	@echo "Running tests classifier v5 for triage agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest agents/triage/tests/test_classifier_v5.py -s \
       --junitxml=reports/pytest-results.xml \
       --html=reports/pytest-results.html --self-contained-html

test-triage-classifier-v6:
	@echo "Running comprehensive tests for classifier v6 (OpenAI fine-tuned)..."
	@echo "🧪 Includes unit tests, integration tests, and coverage"
	@echo "💡 Uses mocked dependencies - no API costs"
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest agents/triage/tests/test_classifier_v6.py agents/triage/tests/test_shared_data_utils.py -v \
       --cov=agents.triage.classifier_v6 --cov=agents.triage.shared --cov-report=term \
       --junitxml=reports/pytest-v6-results.xml \
       --html=reports/pytest-v6-results.html --self-contained-html

test-triage-classifier-v7:
	@echo "Running comprehensive tests for classifier v7 (Gemma3 via HuggingFace)..."
	@echo "🧪 Includes unit tests, integration tests, device utils, and coverage"
	@echo "💡 Uses mocked dependencies - no transformers required for tests"
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest agents/triage/tests/test_classifier_v7.py agents/triage/tests/test_shared_data_utils.py -v \
       --cov=agents.triage.classifier_v7 --cov=agents.triage.shared --cov-report=term \
       --junitxml=reports/pytest-v7-results.xml \
       --html=reports/pytest-v7-results.html --self-contained-html

test-triage-classifier-v6-evaluation:
	@echo "Running MLflow evaluation for classifier v6 (OpenAI fine-tuned)..."
	@echo "📊 Logs performance metrics to MLflow for comparison with v3/v5"
	@echo "⚠️  Requires OPENAI_API_KEY and MLflow server running"
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest agents/triage/tests/test_classifier_v6_evaluation.py -s \
       --junitxml=reports/pytest-v6-evaluation-results.xml \
       --html=reports/pytest-v6-evaluation-results.html --self-contained-html

test-triage-classifier-v7-evaluation:
	@echo "Running MLflow evaluation for classifier v7 (Gemma3 via HuggingFace)..."
	@echo "📊 Logs performance metrics to MLflow for comparison with v3/v5"
	@echo "⚠️  Requires MLflow server running and HuggingFace transformers"
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest agents/triage/tests/test_classifier_v7_evaluation.py -s \
       --junitxml=reports/pytest-v7-evaluation-results.xml \
       --html=reports/pytest-v7-evaluation-results.html --self-contained-html

test-triage-classifiers-evaluation:
	@echo "Running MLflow evaluation for all classifiers v6 and v7..."
	@echo "📊 Comprehensive metrics logging for classifier comparison dashboard"
	@echo "🚀 Use this target to populate MLflow with latest performance data"
	@make test-triage-classifier-v6-evaluation
	@make test-triage-classifier-v7-evaluation
	@echo "✅ MLflow evaluation completed for v6 and v7!"

test-triage-classifiers-unit:
	@echo "Running comprehensive unit tests for classifiers v6 and v7..."
	@echo "🧪 Unit tests with mocked dependencies - no API calls"
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest agents/triage/tests/test_classifier_v6.py agents/triage/tests/test_classifier_v7.py -v \
       --tb=short \
       --junitxml=reports/pytest-classifier-unit-results.xml \
       --html=reports/pytest-classifier-unit-results.html --self-contained-html

test-triage-classifiers-config:
	@echo "Running configuration tests for classifiers v6 and v7..."
	@echo "⚙️  Testing configuration validation and setup"
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest \
       "agents/triage/tests/test_classifier_v6.py::TestClassifierV6Configuration" \
       "agents/triage/tests/test_classifier_v7.py::TestClassifierV7Configuration" \
       "agents/triage/tests/test_classifier_v7.py::TestClassifierV7DeviceUtils" \
       -v --tb=short

test-triage-classifiers-comparison:
	@echo "Running comparison tests between classifiers v6 and v7..."
	@echo "⚖️  Comparing performance, accuracy, and architecture"
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest agents/triage/tests/test_classifier_comparison.py -v -s \
       --tb=short \
       --junitxml=reports/pytest-comparison-results.xml \
       --html=reports/pytest-comparison-results.html --self-contained-html

test-triage-classifiers-comprehensive:
	@echo "Running comprehensive test suite using custom test runner..."
	@echo "📋 Includes unit, integration, and comparison tests"
	@source $(VENV_DIR)/bin/activate && PYTHONPATH=. $(VENV_DIR)/bin/python agents/triage/tests/run_classifier_tests.py --all

test-triage-classifiers-coverage:
	@echo "Running classifiers v6 and v7 with coverage reporting..."
	@echo "📈 Comprehensive tests designed to maximize code coverage"
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest agents/triage/tests/test_classifier_v6.py agents/triage/tests/test_classifier_v7.py -v \
       --tb=short \
       --cov=agents.triage.classifier_v6 --cov=agents.triage.classifier_v7 \
       --cov-report=term --cov-report=xml:coverage.xml \
       --junitxml=reports/pytest-coverage-results.xml \
       --html=reports/pytest-coverage-results.html --self-contained-html

test-triage-classifiers-all:
	@echo "Running all classifier tests (v0-v7 + comprehensive coverage)..."
	@echo "🚀 Complete classifier test suite"
	@make test-triage-classifier-v0
	@make test-triage-classifier-v1
	@make test-triage-classifier-v2
	@make test-triage-classifier-v3
	@make test-triage-classifier-v4
	@make test-triage-classifier-v5
	@make test-triage-classifier-v6
	@make test-triage-classifier-v7
	@make test-triage-classifiers-unit
	@make test-triage-classifiers-comparison
	@make test-triage-classifiers-coverage
	@echo "✅ All classifier tests completed!"

# ================================================================================
# STANDARDIZED EVALUATION INTERFACE
# ================================================================================
# These commands provide a consistent interface for MLflow evaluation across all 
# classifier versions. Use these commands when you want to compare classifier 
# performance in MLflow.

eval-triage-classifier-v0:
	@echo "📊 Running MLflow evaluation for classifier v0..."
	@echo "🎯 Standardized evaluation interface - logs to 'triage_classifier' experiment"
	@make test-triage-classifier-v0

eval-triage-classifier-v1:
	@echo "📊 Running MLflow evaluation for classifier v1..."
	@echo "🎯 Standardized evaluation interface - logs to 'triage_classifier' experiment"
	@make test-triage-classifier-v1

eval-triage-classifier-v2:
	@echo "📊 Running MLflow evaluation for classifier v2..."
	@echo "🎯 Standardized evaluation interface - logs to 'triage_classifier' experiment"
	@make test-triage-classifier-v2

eval-triage-classifier-v3:
	@echo "📊 Running MLflow evaluation for classifier v3..."
	@echo "🎯 Standardized evaluation interface - logs to 'triage_classifier' experiment"
	@make test-triage-classifier-v3

eval-triage-classifier-v4:
	@echo "📊 Running MLflow evaluation for classifier v4..."
	@echo "🎯 Standardized evaluation interface - logs to 'triage_classifier' experiment"
	@make test-triage-classifier-v4

eval-triage-classifier-v5:
	@echo "📊 Running MLflow evaluation for classifier v5..."
	@echo "🎯 Standardized evaluation interface - logs to 'triage_classifier' experiment"
	@make test-triage-classifier-v5

eval-triage-classifier-v6:
	@echo "📊 Running MLflow evaluation for classifier v6..."
	@echo "🎯 Standardized evaluation interface - logs to 'triage_classifier' experiment"
	@make test-triage-classifier-v6-evaluation

eval-triage-classifier-v7:
	@echo "📊 Running MLflow evaluation for classifier v7..."
	@echo "🎯 Standardized evaluation interface - logs to 'triage_classifier' experiment"
	@make test-triage-classifier-v7-evaluation

eval-all-triage-classifiers:
	@echo "🚀 Running MLflow evaluation for ALL classifiers (v0-v7)..."
	@echo "📈 Complete performance comparison - populate MLflow dashboard"
	@echo "⏱️  This will take several minutes..."
	@make eval-triage-classifier-v0
	@make eval-triage-classifier-v1
	@make eval-triage-classifier-v2
	@make eval-triage-classifier-v3
	@make eval-triage-classifier-v4
	@make eval-triage-classifier-v5
	@make eval-triage-classifier-v6
	@make eval-triage-classifier-v7
	@echo "✅ All classifier evaluations completed!"
	@echo "🎯 View results at: http://localhost:5001/#/experiments/4"

eval-latest-triage-classifiers:
	@echo "🔥 Running MLflow evaluation for latest classifiers (v6 & v7)..."
	@echo "⚡ Quick comparison of most recent implementations"
	@make eval-triage-classifier-v6
	@make eval-triage-classifier-v7
	@echo "✅ Latest classifier evaluations completed!"
	@echo "🎯 View results at: http://localhost:5001/#/experiments/4"

test-triage-agent:
	@echo "Running tests for triage agent..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest agents/triage/tests/test_agent.py -s \
       --cov=agents.triage --cov-report=xml:coverage.xml --cov-report=term --cov-append \
       --junitxml=reports/pytest-results.xml \
       --html=reports/pytest-results.html --self-contained-html
	@echo "Tests for triage agent completed."

test-audit-agent:
	@echo "Running tests for audit agent..."
	@source $(VENV_DIR)/bin/activate && PYTHONPATH=. $(VENV_DIR)/bin/pytest agents/audit -s \
       --cov=agents.audit --cov-report=xml:coverage.xml --cov-report=term --cov-append \
       --junitxml=reports/pytest-results.xml \
       --html=reports/pytest-results.html --self-contained-html
	@echo "Tests for audit agent completed."

test-libraries:
	@echo "Running tests for libraries module..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pytest libraries/testing/tests/ -v \
       --cov=libraries --cov-report=xml:coverage.xml --cov-report=term --cov-append \
       --junitxml=reports/pytest-results.xml \
       --html=reports/pytest-results.html --self-contained-html
	@echo "Libraries tests completed."

stop: docker-down
	@echo "Environment and Docker Compose have been stopped."

kill-agents:
	@echo "Killing all agent processes..."
	@pkill -f "python.*agents.*main" || true
	@pkill -f "start_worker" || true
	@pkill -f "agents\..*\.start_worker" || true
	@pkill -f "agents/.*start_worker" || true
	@echo "All agent processes have been killed."

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
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/python -m agents.policies.agent.main

start-policies-document-ingestion:
	@echo "Starting Policies Document Ingestion Service..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/python -m agents.policies.ingestion.start_worker

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
	@echo "Starting all agents and workers..."
	@make -j start-frontend start-billing start-escalation start-policies start-triage start-audit start-claims start-policies-document-ingestion

restart: stop start
	@echo "Environment and Docker Compose have been restarted."


compile-triage-classifier-v2:
	@echo "Compiling Classifier Dspy Optimizer..."
	# ask the user if he wants to continue
	@read -p "Do you want to compile the classifier (and delete existing optimizations_v2.json if it exists)? (y/n): " choice; \
	if [ "$$choice" != "y" ]; then \
		echo "Aborting..."; \
		exit 1; \
	fi

	@if [ -f agents/triage/dspy_modules/classifier_v2/optimizations_v2.json ]; then \
		rm agents/triage/dspy_modules/classifier_v2/optimizations_v2.json; \
		echo "Deleted existing optimization file"; \
	else \
		echo "No existing optimization file found, creating new one"; \
	fi
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/python -m agents.triage.dspy_modules.classifier_v2.classifier_v2_optimizer
	@echo "Triage Agent setup completed."

compile-triage-classifier-v4:
	@echo "Compiling Classifier v4 with COPRO Zero-Shot Optimizer..."
	# ask the user if he wants to continue
	@read -p "Do you want to compile the zero-shot classifier (and delete existing optimizations_v4.json if it exists)? (y/n): " choice; \
	if [ "$$choice" != "y" ]; then \
		echo "Aborting..."; \
		exit 1; \
	fi
	
	@if [ -f agents/triage/dspy_modules/classifier_v4/optimizations_v4.json ]; then \
		rm agents/triage/dspy_modules/classifier_v4/optimizations_v4.json; \
		echo "Deleted existing optimization file"; \
	else \
		echo "No existing optimization file found, creating new one"; \
	fi
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/python -m agents.triage.dspy_modules.classifier_v4.classifier_v4_optimizer
	@echo "Triage Agent v4 setup completed."

compile-billing-optimizer:
	@echo "Compiling Billing Agent with SIMBA Optimizer..."
	# ask the user if he wants to continue
	@read -p "Do you want to compile the billing agent optimizer (and delete existing optimized_billing_simba.json if it exists)? (y/n): " choice; \
	if [ "$$choice" != "y" ]; then \
		echo "Aborting..."; \
		exit 1; \
	fi
	
	@if [ -f agents/billing/dspy_modules/optimized_billing_simba.json ]; then \
		rm agents/billing/dspy_modules/optimized_billing_simba.json; \
		echo "Deleted existing optimization file"; \
	else \
		echo "No existing optimization file found, creating new one"; \
	fi
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/python -m agents.billing.dspy_modules.billing_optimizer_simba
	@echo "Billing Agent optimization completed with SIMBA."

compile-claims-optimizer:
	@echo "Compiling Claims Agent with SIMBA Optimizer..."
	# ask the user if he wants to continue
	@read -p "Do you want to compile the claims agent optimizer (and delete existing optimized_claims_simba.json if it exists)? (y/n): " choice; \
	if [ "$$choice" != "y" ]; then \
		echo "Aborting..."; \
		exit 1; \
	fi
	
	@if [ -f agents/claims/dspy_modules/optimized_claims_simba.json ]; then \
		rm agents/claims/dspy_modules/optimized_claims_simba.json; \
		echo "Deleted existing optimization file"; \
	else \
		echo "No existing optimization file found, creating new one"; \
	fi
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/python -m agents.claims.dspy_modules.claims_optimizer_simba
	@echo "Claims Agent optimization completed with SIMBA."

compile-policies-optimizer:
	@echo "Compiling Policies Agent with SIMBA Optimizer..."
	# ask the user if he wants to continue
	@read -p "Do you want to compile the policies agent optimizer (and delete existing optimized_policies_simba.json if it exists)? (y/n): " choice; \
	if [ "$$choice" != "y" ]; then \
		echo "Aborting..."; \
		exit 1; \
	fi
	
	@if [ -f agents/policies/dspy_modules/optimized_policies_simba.json ]; then \
		rm agents/policies/dspy_modules/optimized_policies_simba.json; \
		echo "Deleted existing optimization file"; \
	else \
		echo "No existing optimization file found, creating new one"; \
	fi
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/python -m agents.policies.dspy_modules.policies_optimizer_simba
	@echo "Policies Agent optimization completed with SIMBA."

compile-escalation-optimizer:
	@echo "Compiling Escalation Agent with SIMBA Optimizer..."
	# ask the user if he wants to continue
	@read -p "Do you want to compile the escalation agent optimizer (and delete existing optimized_escalation_simba.json if it exists)? (y/n): " choice; \
	if [ "$$choice" != "y" ]; then \
		echo "Aborting..."; \
		exit 1; \
	fi
	
	@if [ -f agents/escalation/dspy_modules/optimized_escalation_simba.json ]; then \
		rm agents/escalation/dspy_modules/optimized_escalation_simba.json; \
		echo "Deleted existing optimization file"; \
	else \
		echo "No existing optimization file found, creating new one"; \
	fi
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/python -m agents.escalation.dspy_modules.escalation_optimizer_simba
	@echo "Escalation Agent optimization completed with SIMBA."

compile-all:
	@echo "Compiling all agent optimizers with SIMBA..."
	@echo "This will sequentially run all optimizers with automatic 'yes' responses."
	@read -p "Do you want to proceed? This will overwrite existing optimization files. (y/n): " choice; \
	if [ "$$choice" != "y" ]; then \
		echo "Aborting..."; \
		exit 1; \
	fi
	
	@echo "Starting Billing Agent SIMBA optimizer..."
	@echo "y" | make compile-billing-optimizer
	
	@echo "Starting Claims Agent SIMBA optimizer..."
	@echo "y" | make compile-claims-optimizer
	
	@echo "Starting Policies Agent SIMBA optimizer..."
	@echo "y" | make compile-policies-optimizer
	
	@echo "Starting Escalation Agent SIMBA optimizer..."
	@echo "y" | make compile-escalation-optimizer
	
	@echo "Starting Triage Classifier v2 optimizer..."
	@echo "y" | make compile-triage-classifier-v2
	
	@echo "Starting Triage Classifier v4 optimizer..."
	@echo "y" | make compile-triage-classifier-v4
	
	@echo "All optimizers completed successfully."

setup-and-run: setup start
	@echo "Setup and all services started."

lint:
	@echo "Running ruff linter..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/ruff check .
	@echo "Linting completed."

lint-fix:
	@echo "Fixing lint issues..."
	@source $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/ruff check . --fix
	@echo "Lint fixes applied."

build-policy-rag-index:
	@echo "Building policy index..."
	@echo "Starting ingestion worker to build index..."
	@source $(VENV_DIR)/bin/activate && PYTHONPATH=. $(VENV_DIR)/bin/python agents/policies/ingestion/start_worker.py &
	@echo "Policy index built successfully."

drop-vespa-index:
	@echo "Dropping Vespa index..."
	@echo "This will delete all documents from the Vespa search index."
	@read -p "Are you sure you want to proceed? (y/n): " choice; \
	if [ "$$choice" != "y" ]; then \
		echo "Operation cancelled."; \
		exit 1; \
	fi
	@source $(VENV_DIR)/bin/activate && PYTHONPATH=. $(VENV_DIR)/bin/python agents/policies/vespa/drop_index.py
	@echo "Vespa index dropped successfully."

generate-vespa-package:
	@echo "Generating Vespa application package..."
	@source $(VENV_DIR)/bin/activate && PYTHONPATH=. $(VENV_DIR)/bin/python agents/policies/vespa/generate_package.py $(ARGS)
	@echo "Vespa package generation completed."

deploy-vespa-package:
	@echo "Deploying Vespa package..."
	@if [ -z "$(VESPA_CONFIG_SERVER)" ]; then \
		echo "Using local Docker configuration"; \
		source $(VENV_DIR)/bin/activate && PYTHONPATH=. $(VENV_DIR)/bin/python agents/policies/vespa/deploy_package.py \
			--config-server http://localhost:19071 \
			--query-url http://localhost:8080 \
			--deployment-mode production \
			--node-count 3 \
			$(ARGS); \
	else \
		echo "Using environment configuration"; \
		source $(VENV_DIR)/bin/activate && PYTHONPATH=. $(VENV_DIR)/bin/python agents/policies/vespa/deploy_package.py \
			--config-server $(VESPA_CONFIG_SERVER) \
			--query-url $(VESPA_QUERY_URL) \
			--deployment-mode $(VESPA_DEPLOYMENT_MODE) \
			--node-count $(VESPA_NODE_COUNT) \
			$(if $(VESPA_HOSTS_CONFIG),--hosts-config $(VESPA_HOSTS_CONFIG),) \
			$(ARGS); \
	fi
	@echo "Vespa package deployment completed."