"""Shared test utilities for classifier tests."""

import random
import statistics
from typing import Any, Dict, List, Tuple
from unittest.mock import Mock

import mlflow
import numpy as np

from agents.triage.models import ClassifierMetrics, TargetAgent


def calculate_test_metrics(results: List[Dict[str, Any]]) -> Dict[str, float]:
    """Calculate standard metrics from test results.
    
    Args:
        results: List of test results with 'correct' and 'metrics' keys
        
    Returns:
        Dictionary of calculated metrics
    """
    all_scores = [res['correct'] for res in results]
    accuracy = sum(all_scores) / len(all_scores) if all_scores else 0
    
    # Filter out results with errors for token metrics
    valid_results = [res for res in results if res.get("metrics") is not None]
    
    if valid_results:
        latencies_sec = [res["metrics"].latency_ms / 1_000 for res in valid_results]
        prompt_tok_counts = [res["metrics"].prompt_tokens for res in valid_results]
        completion_tok_counts = [res["metrics"].completion_tokens for res in valid_results]
        total_tok_counts = [res["metrics"].total_tokens for res in valid_results]
    else:
        latencies_sec = prompt_tok_counts = completion_tok_counts = total_tok_counts = []
    
    def ms(vals):
        return statistics.mean(vals) * 1_000 if vals else 0

    def p95(vals):
        return float(np.percentile(vals, 95)) if vals else 0

    return {
        "accuracy": accuracy * 100,
        "total_examples": len(results),
        "valid_predictions": len(valid_results),
        "error_count": len(results) - len(valid_results),
        # latency
        "latency_mean_ms": ms(latencies_sec),
        "latency_p95_ms": p95(latencies_sec) * 1_000 if latencies_sec else 0,
        "latency_max_ms": max(latencies_sec) * 1_000 if latencies_sec else 0,
        # tokens
        "tokens_total": sum(total_tok_counts),
        "tokens_prompt_total": sum(prompt_tok_counts),
        "tokens_completion_total": sum(completion_tok_counts),
        "tokens_mean": statistics.mean(total_tok_counts) if total_tok_counts else 0,
        "tokens_p95": p95(total_tok_counts),
    }


def log_failing_examples(results: List[Dict[str, Any]], logger, max_failures: int = 5):
    """Log failing test examples for debugging.
    
    Args:
        results: List of test results
        logger: Logger instance
        max_failures: Maximum number of failures to log
    """
    failing_indices = [
        i for i, res in enumerate(results) if not res.get('correct', False)
    ]
    
    if failing_indices:
        logger.error(f"Found {len(failing_indices)} failing tests:")

        # Log first few failures for debugging
        for i in failing_indices[:max_failures]:
            if i < len(results):
                logger.error(f"\n{'=' * 80}\nFAILING TEST #{i}:")
                logger.error(f"CONVERSATION:\n{results[i].get('conversation', 'N/A')}")
                logger.error(f"EXPECTED AGENT: {results[i].get('expected_agent', 'N/A')}")
                logger.error(f"PREDICTED AGENT: {results[i].get('predicted_agent', 'N/A')}")
                if 'error' in results[i]:
                    logger.error(f"ERROR: {results[i]['error']}")
                logger.error(f"{'=' * 80}")


def create_mock_classifier_result(target_agent: TargetAgent, 
                                latency_ms: float = 100.0,
                                prompt_tokens: int = 50,
                                completion_tokens: int = 5) -> Mock:
    """Create a mock classifier result for testing.
    
    Args:
        target_agent: Target agent to return
        latency_ms: Mock latency
        prompt_tokens: Mock prompt tokens
        completion_tokens: Mock completion tokens
        
    Returns:
        Mock result object
    """
    mock_result = Mock()
    mock_result.target_agent = target_agent
    mock_result.metrics = ClassifierMetrics(
        latency_ms=latency_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens
    )
    return mock_result


def setup_test_mlflow(experiment_name: str = "test_triage_classifier"):
    """Set up MLflow for testing.
    
    Args:
        experiment_name: Name of the experiment
    """
    mlflow.set_experiment(experiment_name)


def get_standard_test_cases() -> List[Tuple[str, str]]:
    """Get standard test cases for classifier testing.
    
    Returns:
        List of (chat_history, expected_category) tuples
    """
    return [
        ("User: I need help with my insurance claim", "ClaimsAgent"),
        ("User: What's my policy coverage?", "PolicyAgent"),
        ("User: I need to pay my bill", "BillingAgent"),
        ("User: Hello, how are you?", "ChattyAgent"),
        ("User: I want to buy additional coverage", "SalesAgent"),
        ("User: My app is not working", "TechnicalSupportAgent"),
    ]


def run_basic_classifier_test(classifier_func, logger, test_cases=None):
    """Run basic classifier functionality test.
    
    Args:
        classifier_func: Classifier function to test
        logger: Logger instance
        test_cases: Optional test cases, uses standard ones if not provided
        
    Returns:
        List of results
    """
    if test_cases is None:
        test_cases = get_standard_test_cases()
    
    results = []
    
    for chat_history, expected_category in test_cases:
        try:
            result = classifier_func(chat_history=chat_history)
            
            # Check that we get a valid response
            assert result is not None
            assert hasattr(result, 'target_agent')
            assert hasattr(result, 'metrics')
            
            # Check that metrics are populated
            assert result.metrics is not None
            assert result.metrics.latency_ms >= 0
            
            logger.info(f"Input: {chat_history}")
            logger.info(f"Predicted: {result.target_agent}, Expected category: {expected_category}")
            logger.info(f"Latency: {result.metrics.latency_ms:.2f}ms")
            logger.info("---")
            
            results.append({
                'conversation': chat_history,
                'expected_agent': expected_category,
                'predicted_agent': result.target_agent,
                'metrics': result.metrics,
                'correct': True  # Basic test just checks structure
            })
            
        except Exception as e:
            logger.error(f"Classification failed for '{chat_history}': {e}")
            results.append({
                'conversation': chat_history,
                'expected_agent': expected_category,
                'predicted_agent': 'ERROR',
                'metrics': None,
                'correct': False,
                'error': str(e)
            })
    
    return results


class MockMLflowRun:
    """Mock MLflow run context manager for testing."""
    
    def __init__(self, run_name: str):
        self.run_name = run_name
        self.logged_params = {}
        self.logged_metrics = {}
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
    
    def log_param(self, key: str, value: Any):
        """Mock parameter logging."""
        self.logged_params[key] = value
    
    def log_metric(self, key: str, value: float):
        """Mock metric logging."""
        self.logged_metrics[key] = value
    
    def log_metrics(self, metrics: Dict[str, float]):
        """Mock metrics logging."""
        self.logged_metrics.update(metrics)


def create_test_dataset_sample(size: int = 10, seed: int = 42) -> List[Mock]:
    """Create a mock test dataset for classifier testing.
    
    Args:
        size: Number of examples to create
        seed: Random seed for reproducibility
        
    Returns:
        List of mock test cases
    """
    random.seed(seed)
    
    conversations = [
        "User: I need to file a claim for my car accident",
        "User: What does my health insurance cover?", 
        "User: How do I pay my monthly premium?",
        "User: Hello there, how are you today?",
        "User: I want to increase my coverage amount",
        "User: The mobile app won't let me log in",
        "User: Can you help me understand my deductible?",
        "User: I need to update my contact information",
        "User: What's the weather like today?",
        "User: My claim was denied, can you help?"
    ]
    
    agents = [
        TargetAgent.ClaimsAgent,
        TargetAgent.PolicyAgent,
        TargetAgent.BillingAgent,
        TargetAgent.ChattyAgent,
        TargetAgent.SalesAgent,
        TargetAgent.TechnicalSupportAgent,
        TargetAgent.PolicyAgent,
        TargetAgent.PolicyAgent,
        TargetAgent.ChattyAgent,
        TargetAgent.ClaimsAgent
    ]
    
    dataset = []
    for i in range(min(size, len(conversations))):
        mock_case = Mock()
        mock_case.conversation = conversations[i % len(conversations)]
        mock_case.target_agent = agents[i % len(agents)]
        dataset.append(mock_case)
    
    # If we need more examples than predefined, generate variations
    while len(dataset) < size:
        base_idx = len(dataset) % len(conversations)
        mock_case = Mock()
        mock_case.conversation = f"{conversations[base_idx]} (variation {len(dataset)})"
        mock_case.target_agent = agents[base_idx % len(agents)]
        dataset.append(mock_case)
    
    return dataset[:size]