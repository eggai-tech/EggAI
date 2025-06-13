import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from temporalio import workflow
from temporalio.common import RetryPolicy

from agents.policies.rag.config import RAGConfig

# Use workflow.unsafe to avoid circular imports
with workflow.unsafe.imports_passed_through():
    from agents.policies.rag.workflows.activities.augmentation_activity import (
        policy_augmentation_activity,
    )
    from agents.policies.rag.workflows.activities.generation_activity import (
        policy_generation_activity,
    )
    from agents.policies.rag.workflows.activities.retrieval_activity import (
        retrieve_policy_documents,
    )

logger = logging.getLogger(__name__)

class RAGWorkflowInput(BaseModel):
    """Input for the RAG workflow."""
    query: str
    policy_category: Optional[str] = None
    request_id: str = ""
    
class RAGResult(BaseModel):
    """Result from the RAG workflow."""
    query: str
    retrieval_results: List[Dict[str, Any]] = []
    augmented_context: Dict[str, Any] = {}
    generated_response: str = ""
    success: bool = True

@workflow.defn
class RAGWorkflow:
    """RAG workflow for policy agent."""
    
    @workflow.run
    async def run(self, input: RAGWorkflowInput) -> RAGResult:
        """
        Run the RAG workflow.
        
        Args:
            input: Input for the workflow
            
        Returns:
            Result from the workflow
        """
        logger.info(f"Starting RAG workflow for query: '{input.query}', category: '{input.policy_category}', request_id: '{input.request_id}'")
        
        result = RAGResult(query=input.query)
        
        logger.info("Starting retrieval step")
        
        # First stage: Retrieval
        retry_policy = RetryPolicy(maximum_attempts=RAGConfig.RETRY_MAX_ATTEMPTS)
        retrieval_results = await workflow.execute_activity(
            retrieve_policy_documents,
            args=[input.query, input.policy_category],
            retry_policy=retry_policy,
            start_to_close_timeout=timedelta(seconds=RAGConfig.ACTIVITY_TIMEOUT_SECONDS)
        )
        
        if retrieval_results:
            logger.info(f"Retrieved {len(retrieval_results)} documents")
        
        result.retrieval_results = retrieval_results
        logger.info(f"Retrieval step completed. Found {len(retrieval_results) if retrieval_results else 0} documents")
        
        # If no documents found, return early
        if not retrieval_results:
            logger.warning("No documents found during retrieval")
            result.generated_response = RAGConfig.ERROR_MESSAGES["no_documents"]
            result.success = True
            return result
        
        # Second stage: Augmentation
        logger.info("Starting augmentation step")
        augmented_context = await workflow.execute_activity(
            policy_augmentation_activity,
            args=[retrieval_results, input.query],
            retry_policy=retry_policy,
            start_to_close_timeout=timedelta(seconds=RAGConfig.ACTIVITY_TIMEOUT_SECONDS)
        )
        
        result.augmented_context = augmented_context
        logger.info("Augmentation step completed")
        
        # Third stage: Generation
        logger.info("Starting generation step")
        generated_response = await workflow.execute_activity(
            policy_generation_activity,
            args=[input.query, augmented_context, input.policy_category],
            retry_policy=retry_policy,
            start_to_close_timeout=timedelta(seconds=RAGConfig.ACTIVITY_TIMEOUT_SECONDS)
        )
        
        result.generated_response = generated_response
        logger.info("Generation step completed")
        
        logger.info(f"RAG workflow completed successfully for query: '{input.query}'")
        result.success = True
        return result 