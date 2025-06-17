#!/usr/bin/env python3
"""
Simple script to initialize the Policy RAG index without Temporal dependencies.
This is useful for testing environments where we need to ensure the index is created.
"""

import shutil
from pathlib import Path

import torch
from ragatouille import RAGPretrainedModel

from agents.policies.rag.indexing import get_policy_content
from libraries.logger import get_console_logger

logger = get_console_logger("policies_agent.rag.init_index")


def init_policies_index(force_rebuild: bool = False):
    """
    Initialize the policies RAG index by ingesting all policy documents.
    
    Args:
        force_rebuild: Whether to force rebuild the index even if it exists
    """
    logger.info("Initializing policies RAG index...")
    
    # Log environment info for debugging
    logger.info(f"PyTorch version: {torch.__version__}")
    logger.info(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        logger.info(f"CUDA version: {torch.version.cuda}")
        logger.info(f"GPU count: {torch.cuda.device_count()}")
    
    try:
        # Get paths
        current_dir = Path(__file__).parent
        policies_dir = current_dir / "policies"
        index_root = current_dir / ".ragatouille"
        index_path = index_root / "colbert" / "indexes" / "policies_index"
        metadata_path = index_path / "metadata.json"
        
        # Check if index already exists
        if not force_rebuild and index_path.exists() and metadata_path.exists():
            logger.info("Index already exists and force_rebuild=False. Skipping initialization.")
            return True
            
        # Remove existing index if force rebuild
        if force_rebuild and index_path.exists():
            logger.info("Removing existing index for rebuild...")
            shutil.rmtree(index_path, ignore_errors=True)
            
        # Create policies directory if it doesn't exist
        policies_dir.mkdir(exist_ok=True)
        
        # Policy documents to index
        policy_ids = ["auto", "home", "health", "life"]
        
        # Collect policy content
        policies_content = []
        document_metadata = []
        
        for policy_id in policy_ids:
            try:
                content = get_policy_content(policy_id)
                policies_content.append(content)
                document_metadata.append({
                    "category": policy_id,
                    "type": "policy",
                    "filename": f"{policy_id}.md",
                })
                logger.info(f"Added {policy_id} policy to index")
            except Exception as e:
                logger.warning(f"Failed to load policy {policy_id}: {e}")
                
        if not policies_content:
            logger.error("No policy content found to index")
            return False
            
        # Create RAGPretrainedModel instance
        logger.info(f"Creating RAG index with {len(policies_content)} documents...")
        
        # Set device to CPU if CUDA is not available or causing issues
        device = "cpu"
        if torch.cuda.is_available():
            try:
                # Test CUDA functionality
                torch.cuda.empty_cache()
                device = "cuda"
                logger.info("Using CUDA for indexing")
            except Exception as cuda_e:
                logger.warning(f"CUDA available but not functional, falling back to CPU: {cuda_e}")
                device = "cpu"
        else:
            logger.info("CUDA not available, using CPU for indexing")
        
        r = RAGPretrainedModel.from_pretrained(
            "colbert-ir/colbertv2.0", 
            index_root=str(index_root)
        )
        
        # Build the index
        r.index(
            index_name="policies_index",
            collection=policies_content,
            document_ids=policy_ids,
            document_metadatas=document_metadata,
            use_faiss=False,
        )
        
        logger.info("Policies RAG index initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize policies RAG index: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Initialize the policies RAG index")
    parser.add_argument(
        "--force-rebuild", 
        action="store_true", 
        help="Force rebuild the index even if it exists"
    )
    
    args = parser.parse_args()
    
    success = init_policies_index(force_rebuild=args.force_rebuild)
    exit(0 if success else 1) 