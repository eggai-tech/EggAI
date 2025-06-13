from datetime import timedelta
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from agents.policies.rag.workflows.activities.retrieval_activity import (
        policy_retrieval_activity,
    )


class DocumentationQueryWorkflowInput(BaseModel):
    """Input schema for the documentation query workflow."""
    query: str
    policy_category: str
    request_id: Optional[str] = None


class DocumentationQueryResult(BaseModel):
    """Result schema for the documentation query workflow."""
    request_id: Optional[str]
    query: str
    policy_category: str
    results: List[Dict[str, Any]]
    success: bool
    error_message: Optional[str] = None


@workflow.defn
class DocumentationQueryWorkflow:
    """
    Temporal workflow for querying policy documentation using RAG.
    
    This workflow is specifically designed for documentation queries,
    using Temporal to orchestrate the retrieval process.
    """
    
    @workflow.run
    async def run(self, input_data: DocumentationQueryWorkflowInput) -> DocumentationQueryResult:
        """
        Execute the documentation query workflow.
        
        Args:
            input_data: The workflow input containing query and policy category
            
        Returns:
            DocumentationQueryResult with query results or error information
        """
        workflow.logger.info(
            f"Starting documentation query workflow for query: '{input_data.query}', "
            f"category: '{input_data.policy_category}', request_id: '{input_data.request_id}'"
        )
        
        try:
            # Execute the retrieval activity for documentation
            results = await workflow.execute_activity(
                policy_retrieval_activity,
                args=[input_data.query, input_data.policy_category],
                start_to_close_timeout=timedelta(minutes=5)
            )
            
            workflow.logger.info(
                f"Documentation query workflow completed successfully. "
                f"Retrieved {len(results)} documents for query: '{input_data.query}'"
            )
            
            return DocumentationQueryResult(
                request_id=input_data.request_id,
                query=input_data.query,
                policy_category=input_data.policy_category,
                results=results,
                success=True
            )
            
        except Exception as e:
            workflow.logger.error(
                f"Documentation query workflow failed for query: '{input_data.query}'. Error: {str(e)}"
            )
            
            return DocumentationQueryResult(
                request_id=input_data.request_id,
                query=input_data.query,
                policy_category=input_data.policy_category,
                results=[],
                success=False,
                error_message=str(e)
            )