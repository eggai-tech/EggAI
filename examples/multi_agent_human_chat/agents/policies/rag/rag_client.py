import asyncio
import logging
import uuid
from typing import Any, Dict, Optional

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker
from agents.policies.rag.config import RAGConfig
from agents.policies.rag.workflows.activities.augmentation_activity import (
    policy_augmentation_activity,
)
from agents.policies.rag.workflows.activities.generation_activity import (
    policy_generation_activity,
)
from agents.policies.rag.workflows.activities.retrieval_activity import (
    retrieve_policy_documents,
)
from agents.policies.rag.workflows.rag_workflow import (
    RAGWorkflow,
    RAGWorkflowInput,
)
from shared.utils.async_bridge import run_async

logger = logging.getLogger(__name__)

class RAGClient:
    """Client for the RAG (Retrieval Augmented Generation) system."""
    
    def __init__(self, temporal_address: str = None):
        """
        Initialize the RAG client.
        
        Args:
            temporal_address: Address of the Temporal server
        """
        self.temporal_address = temporal_address or RAGConfig.TEMPORAL_ADDRESS
        self.client = None
        self.namespace = RAGConfig.TEMPORAL_NAMESPACE
        self.task_queue = RAGConfig.TASK_QUEUE
    
    async def _get_client(self) -> Client:
        """Get or create a Temporal client."""
        if self.client is None:
            self.client = await Client.connect(
                self.temporal_address,
                data_converter=pydantic_data_converter
            )
        return self.client
    
    async def _start_worker(self):
        """Start a worker for RAG activities."""
        client = await self._get_client()
        worker = Worker(
            client,
            task_queue=self.task_queue,
            workflows=[RAGWorkflow],
            activities=[
                retrieve_policy_documents,
                policy_augmentation_activity,
                policy_generation_activity
            ],
        )
        await worker.run()
    
    
    async def process_query(
        self, 
        query: str, 
        category: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a user query through the RAG workflow.
        
        Args:
            query: The user's question
            category: Optional category filter (auto, home, life, health)
            request_id: Optional request identifier
            
        Returns:
            Result from the RAG workflow
        """
        logger.info(f"Processing query: '{query}'")
        
        client = await self._get_client()
        
        # Use a default request ID if none provided
        if not request_id:
            request_id = str(uuid.uuid4())
        
        # Create workflow input
        workflow_input = RAGWorkflowInput(
            query=query,
            policy_category=category,
            request_id=request_id
        )
        
        # Execute the workflow
        result = await client.execute_workflow(
            RAGWorkflow.run,
            args=[workflow_input],
            id=f"{RAGConfig.WORKFLOW_ID_PREFIX}-{request_id}",
            task_queue=self.task_queue,
        )
        
        logger.info(f"Query processed successfully: '{query}'")
        
        # Convert RAGResult to a dictionary for easier handling
        return {
            "query": result.query,
            "response": result.generated_response,
            "success": result.success,
            "retrieved_documents": [
                {
                    "id": doc.get("id", ""),
                    "title": doc.get("title", ""),
                    "category": doc.get("category", ""),
                    "sections": [section.get("reference", "") for section in doc.get("sections", [])]
                }
                for doc in result.retrieval_results
            ] if result.retrieval_results else []
        }
    
    def process_query_sync(
        self, 
        query: str, 
        category: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Synchronous wrapper for process_query.
        
        Args:
            query: The user's question
            category: Optional category filter (auto, home, life, health)
            request_id: Optional request identifier
            
        Returns:
            Result from the RAG workflow
        """
        return run_async(self.process_query(query, category, request_id))