import warnings
from typing import List

import pytest
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
                result = policies_model(chat_history=conversation)
                actual_response = (
                    result.final_response.replace(" [[ ## completed ## ]]", "")
                    if result.final_response
                    else ""
                )
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
    
    # Create evaluation samples
    samples = create_ragas_samples()
    
    if not samples:
        pytest.fail("No evaluation samples created")

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
        
        # Print results
        print("\n=== Ragas RAG Evaluation Results ===")
        for metric_name, score in results.items():
            print(f"{metric_name}: {score:.3f}")
        
        # Log individual sample results if available
        if hasattr(results, 'to_pandas'):
            df = results.to_pandas()
            print("\nDetailed Results:")
            print(df.to_string())

        # Assert minimum thresholds
        assert results.get('faithfulness', 0) >= 0.7, f"Faithfulness too low: {results.get('faithfulness', 0):.3f}"
        assert results.get('answer_relevancy', 0) >= 0.7, f"Answer relevancy too low: {results.get('answer_relevancy', 0):.3f}"
        
        print("\nRAG evaluation completed successfully!")
        
    except Exception as e:
        pytest.fail(f"Ragas evaluation failed: {str(e)}")


if __name__ == "__main__":
    # Run the test directly for debugging
    import asyncio
    asyncio.run(test_rag_with_ragas())