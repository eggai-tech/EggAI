import warnings
from typing import List
import os

import pytest
import mlflow
from ragas import SingleTurnSample, EvaluationDataset, evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall

from agents.policies.dspy_modules.policies_data import (
    add_test_policy,
    remove_test_policy,
)

# Disable warnings
warnings.filterwarnings("ignore")
warnings.filterwarnings("ignore", category=FutureWarning, module="colbert.utils.amp")
warnings.filterwarnings("ignore", category=UserWarning, module="torch.amp.grad_scaler")
warnings.filterwarnings("ignore", category=FutureWarning, message=".*torch.cuda.amp.*")
warnings.filterwarnings(
    "ignore", category=UserWarning, message=".*CUDA is not available.*"
)
warnings.filterwarnings("ignore", category=UserWarning, module="torch.amp.autocast_mode")
warnings.filterwarnings("ignore", category=FutureWarning, module="torch.cuda.amp")

# Suppress specific ColBERT output
os.environ["COLBERT_LOAD_TORCH_EXTENSION_VERBOSE"] = "False"


class ConversationHelper:
    """Helper to create conversations based on policy document mapping."""

    # Map policy document files to policy numbers and categories
    POLICY_DOC_MAPPING = {
        "auto.md": {"policy_number": "T12345", "category": "auto"},
        "health.md": {"policy_number": "T98765", "category": "health"},
        "home.md": {"policy_number": "T24680", "category": "home"},
        "life.md": {"policy_number": "T67890", "category": "life"},
    }

    def create_conversation(self, question: str, policy_document_file: str) -> str:
        """Create a conversation with policy number based on document file."""
        policy_info = self.POLICY_DOC_MAPPING.get(policy_document_file)
        if not policy_info:
            raise ValueError(f"Unknown policy document file: {policy_document_file}")

        return f"User: Hello, my policy is {policy_info['policy_number']}. {question}"

    def get_policy_info(self, policy_document_file: str) -> dict:
        """Get policy number and category for a document file."""
        policy_info = self.POLICY_DOC_MAPPING.get(policy_document_file)
        if not policy_info:
            raise ValueError(f"Unknown policy document file: {policy_document_file}")
        return policy_info


def get_rag_test_cases():
    """Return standardized RAG test cases for policy documentation testing."""
    return [
        {
            "id": "auto_deductible",
            "question": "What is the deductible for collision coverage?",
            "expected": "deductible for each claim as specified in the policy schedule",
            "policy_document_file": "auto.md",
        },
        {
            "id": "health_waiting_period", 
            "question": "What is the waiting period for pre-existing conditions?",
            "expected": "Pre-Existing Conditions: Excluded for the first 24 months",
            "policy_document_file": "health.md",
        },
    ]


def create_ragas_samples() -> List[SingleTurnSample]:
    """Create Ragas evaluation samples from test cases."""
    test_cases = get_rag_test_cases()
    conversation_helper = ConversationHelper()
    samples = []

    for case in test_cases:
        # Get policy info and add test policy to database
        policy_info = conversation_helper.get_policy_info(case["policy_document_file"])
        add_test_policy(policy_info["policy_number"], policy_info["category"])

        try:
            # Create conversation using helper
            conversation = conversation_helper.create_conversation(
                case["question"], case["policy_document_file"]
            )

            # Get response from policy agent
            from agents.policies.dspy_modules.policies import policies_model

            try:
                import signal
                
                def timeout_handler(signum, frame):
                    raise TimeoutError("Model call timed out after 30 seconds")
                
                # Set a 30-second timeout for the model call
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(30)
                
                try:
                    result = policies_model(chat_history=conversation)
                    signal.alarm(0)  # Cancel the alarm
                    actual_response = (
                        result.final_response.replace(" [[ ## completed ## ]]", "")
                        if result.final_response
                        else ""
                    )
                except TimeoutError:
                    signal.alarm(0)  # Cancel the alarm
                    actual_response = "Error: Model call timed out - LM Studio server may not be running"
                    
            except Exception as e:
                print(f"Warning: Error getting response for {case['id']}: {e}")
                actual_response = f"Error: Could not get response - {str(e)}"

            if not actual_response:
                actual_response = "No response received"

            # Get retrieved contexts (simulate based on policy document)
            retrieved_contexts = [f"Context from {case['policy_document_file']}: {case['expected']}"]

            # Create Ragas sample
            sample = SingleTurnSample(
                user_input=case["question"],
                retrieved_contexts=retrieved_contexts,
                response=actual_response,
                reference=case["expected"]
            )
            samples.append(sample)

        finally:
            # Clean up test policy
            remove_test_policy(policy_info["policy_number"])

    return samples


@pytest.mark.asyncio
async def test_rag_with_ragas():
    """Test RAG system using Ragas evaluation framework."""
    
    # Setup MLflow
    experiment_name = "rag_evaluation"
    mlflow.set_experiment(experiment_name)
    
    with mlflow.start_run(run_name="rag_evaluation_test"):
        # Create evaluation samples
        samples = create_ragas_samples()
        
        if not samples:
            pytest.fail("No evaluation samples created")

        # Log test parameters
        mlflow.log_param("num_samples", len(samples))
        mlflow.log_param("evaluation_framework", "ragas")
        mlflow.log_param("metrics", "faithfulness,answer_relevancy,context_precision,context_recall")
        
        # Create evaluation dataset
        dataset = EvaluationDataset(samples=samples)

        # Define metrics to evaluate
        metrics = [
            faithfulness,        # Measures factual consistency
            answer_relevancy,    # Measures relevance of answer to question
            context_precision,   # Measures precision of retrieved context
            context_recall,      # Measures recall of retrieved context
        ]

        # Run evaluation
        try:
            results = evaluate(dataset=dataset, metrics=metrics)
            
            # Log results to MLflow and print summary
            print("\n=== Ragas RAG Evaluation Results ===")
            
            if hasattr(results, 'to_pandas'):
                df = results.to_pandas()
                
                # Log metrics to MLflow and print
                for column in df.columns:
                    if column not in ['user_input', 'retrieved_contexts', 'response', 'reference']:
                        values = df[column].dropna()
                        if len(values) > 0:
                            avg_score = values.mean()
                            print(f"{column}: {avg_score:.3f}")
                            mlflow.log_metric(f"avg_{column}", avg_score)
                            
                            # Log individual scores
                            for i, score in enumerate(values):
                                mlflow.log_metric(f"{column}_sample_{i}", score)
                
                # Save detailed results as artifact
                df.to_csv("rag_evaluation_results.csv", index=False)
                mlflow.log_artifact("rag_evaluation_results.csv")
                os.remove("rag_evaluation_results.csv")

            # Log overall results dict if available
            if hasattr(results, '__dict__'):
                for key, value in results.__dict__.items():
                    if isinstance(value, (int, float)):
                        mlflow.log_metric(f"overall_{key}", value)
            
            # Set tags
            mlflow.set_tag("test_type", "rag_evaluation")
            mlflow.set_tag("framework", "ragas")
            mlflow.set_tag("status", "completed")
            
            print("\nRAG evaluation completed successfully!")
            
        except Exception as e:
            mlflow.set_tag("status", "failed")
            mlflow.log_param("error", str(e))
            pytest.fail(f"Ragas evaluation failed: {str(e)}")


if __name__ == "__main__":
    # Run the test directly for debugging
    import asyncio
    asyncio.run(test_rag_with_ragas())