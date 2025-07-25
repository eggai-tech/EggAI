import asyncio
from datetime import timedelta
from pathlib import Path
from typing import Dict, List

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from agents.policies.ingestion.workflows.activities.minio_activities import (
        check_document_exists_activity,
        move_to_failed_activity,
        move_to_processed_activity,
        scan_minio_inbox_activity,
    )
    from agents.policies.ingestion.workflows.ingestion_workflow import (
        DocumentIngestionWorkflow,
    )


@workflow.defn
class MinIOInboxWatcherWorkflow:
    
    @workflow.run
    async def run(self, poll_interval_seconds: int = 30) -> None:
        workflow.logger.info(f"Starting MinIO inbox watcher with {poll_interval_seconds}s interval")
        
        while True:
            try:
                # Scan inbox for new files
                files = await workflow.execute_activity(
                    scan_minio_inbox_activity,
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(
                        maximum_attempts=3,
                        initial_interval=timedelta(seconds=1)
                    )
                )
                
                if files:
                    workflow.logger.info(f"Found {len(files)} files in inbox")
                    await self._process_files(files)
                else:
                    workflow.logger.debug("No files found in inbox")
                    
            except Exception as e:
                workflow.logger.error(f"Error in watcher loop: {e}")
                # Continue running even if there's an error
                
            # Wait before next scan
            await asyncio.sleep(poll_interval_seconds)
            
    async def _process_files(self, files: List[Dict]) -> None:
        for file_info in files:
            try:
                file_key = file_info['key']
                metadata = file_info.get('metadata', {})
                document_id = metadata.get('document_id')
                
                if not document_id:
                    # Use filename (without extension) as document_id
                    filename = Path(file_key).name
                    document_id = Path(filename).stem
                    metadata['document_id'] = document_id
                    
                # Check if document already exists (prevent re-indexing)
                exists = await workflow.execute_activity(
                    check_document_exists_activity,
                    args=[document_id],
                    start_to_close_timeout=timedelta(seconds=10)
                )
                
                if exists:
                    workflow.logger.info(f"Document {document_id} already indexed, moving to processed")
                    await workflow.execute_activity(
                        move_to_processed_activity,
                        args=[file_key],
                        start_to_close_timeout=timedelta(seconds=30)
                    )
                    continue
                    
                # Process the document
                workflow.logger.info(f"Processing {file_key}")
                try:
                    await workflow.execute_child_workflow(
                        DocumentIngestionWorkflow,
                        args=[{
                            "file_path": file_key,
                            "force_rebuild": False,
                            "source": "minio",
                            "metadata": metadata
                        }],
                        id=f"document-ingestion-{document_id}",
                        execution_timeout=timedelta(minutes=10)
                    )
                    
                    # Move to processed folder on success
                    await workflow.execute_activity(
                        move_to_processed_activity,
                        args=[file_key],
                        start_to_close_timeout=timedelta(seconds=30)
                    )
                    workflow.logger.info(f"Successfully processed {file_key}")
                    
                except Exception as e:
                    workflow.logger.error(f"Failed to process {file_key}: {e}")
                    # Move to failed folder with error metadata
                    await workflow.execute_activity(
                        move_to_failed_activity,
                        args=[file_key, str(e)],
                        start_to_close_timeout=timedelta(seconds=30)
                    )
                    
            except Exception as e:
                workflow.logger.error(f"Error processing file {file_info}: {e}")
                # Continue with next file