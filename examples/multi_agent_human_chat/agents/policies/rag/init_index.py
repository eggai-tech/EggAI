#!/usr/bin/env python3
"""
Simple script to initialize the Policy RAG index without Temporal dependencies.
This is useful for testing environments where we need to ensure the index is created.
"""

import os

# Set environment variables BEFORE any other imports for CI GPU environment
if os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS'):
    # For GPU runners, ensure proper CUDA environment
    # Clear the torch extensions cache to force recompilation
    os.environ['TORCH_EXTENSIONS_DIR'] = '/tmp/torch_extensions_clean'
    os.environ['COLBERT_LOAD_TORCH_EXTENSION_VERBOSE'] = 'True'  # Enable verbose for debugging
    
    # Force complete rebuild of extensions
    os.environ['TORCH_EXTENSION_RECOMPILE'] = '1'
    os.environ['TORCH_EXTENSION_FORCE_REBUILD'] = '1'
    
    # Ensure CUDA libraries are properly linked
    cuda_lib_paths = [
        '/usr/local/cuda/lib64',
        '/usr/local/cuda/lib',
        '/opt/cuda/lib64',
        '/usr/lib/x86_64-linux-gnu'
    ]
    current_ld_path = os.environ.get('LD_LIBRARY_PATH', '')
    os.environ['LD_LIBRARY_PATH'] = current_ld_path + ':' + ':'.join(cuda_lib_paths)
    
    # Additional environment variables for shared library loading
    os.environ['LIBRARY_PATH'] = os.environ.get('LIBRARY_PATH', '') + ':' + ':'.join(cuda_lib_paths)
    
    # Additional torch compilation flags for CI stability
    os.environ['TORCH_COMPILE_DEBUG'] = '1'
    os.environ['CUDA_LAUNCH_BLOCKING'] = '1'
    os.environ['TORCH_USE_CUDA_DSA'] = '1'
    
    # Ensure proper C++ compiler flags
    os.environ['CXXFLAGS'] = os.environ.get('CXXFLAGS', '') + ' -fPIC'
    os.environ['LDFLAGS'] = os.environ.get('LDFLAGS', '') + ' -Wl,-rpath,' + ':'.join(cuda_lib_paths)
    
    # Try to disable problematic extensions if they keep failing
    import shutil
    # Clean any existing extension cache
    if os.path.exists('/tmp/torch_extensions_clean'):
        shutil.rmtree('/tmp/torch_extensions_clean')
    if os.path.exists('/home/runner/.cache/torch_extensions'):
        try:
            shutil.rmtree('/home/runner/.cache/torch_extensions')
        except (OSError, PermissionError):
            pass

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
        
        # Log CI environment detection (environment variables already set at import time)
        if os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS'):
            logger.info("CI GPU environment detected, ensuring proper CUDA environment setup")
        
        # Check if faiss is available for indexing
        import importlib.util
        faiss_available = importlib.util.find_spec("faiss") is not None
        if faiss_available:
            logger.info("FAISS library is available")
        else:
            logger.warning("FAISS library not available, will use PLAID fallback")
        
        # Set device to CPU if CUDA is not available or causing issues
        device = "cpu"
        if torch.cuda.is_available():
            try:
                # Test CUDA functionality
                torch.cuda.empty_cache()
                # In CI environments, still prefer CPU to avoid compilation issues
                if os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS'):
                    logger.info("CI environment detected, using CPU for indexing")
                    device = "cpu"
                else:
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
        
        # Try different indexing approaches for better CI compatibility
        indexing_success = False
        
        # Choose indexing method based on environment and availability
        if faiss_available and not (os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS')):
            # Use FAISS in local environments where it's available
            try:
                logger.info("Attempting to build index with FAISS...")
                r.index(
                    index_name="policies_index",
                    collection=policies_content,
                    document_ids=policy_ids,
                    document_metadatas=document_metadata,
                    use_faiss=True,
                )
                indexing_success = True
                logger.info("Successfully built index with FAISS")
            except Exception as faiss_e:
                logger.warning(f"FAISS indexing failed: {faiss_e}")
        
        # If FAISS failed or not available, try PLAID
        if not indexing_success:
            try:
                logger.info("Attempting to build index with PLAID (no FAISS)...")
                r.index(
                    index_name="policies_index",
                    collection=policies_content,
                    document_ids=policy_ids,
                    document_metadatas=document_metadata,
                    use_faiss=False,
                )
                indexing_success = True
                logger.info("Successfully built index with PLAID")
            except Exception as plaid_e:
                logger.error(f"PLAID indexing failed: {plaid_e}")
                # Check if this is the specific torch extension error
                error_str = str(plaid_e)
                if "decompress_residuals_cpp.so" in error_str or "torch_extensions" in error_str:
                    logger.warning("Torch extension loading error detected - this may be due to CUDA environment issues in CI")
                    logger.info("This could be caused by CUDA version mismatches or missing CUDA development libraries")
                    
                    # In CI environments, try one more time with extensions completely disabled
                    if os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS'):
                        logger.info("Attempting fallback: trying to disable torch extensions completely...")
                        try:
                            # Set aggressive environment variables to disable extensions
                            os.environ['COLBERT_DISABLE_TORCH_EXTENSIONS'] = '1'
                            os.environ['TORCH_EXTENSION_DISABLE'] = '1'
                            os.environ['CUDA_VISIBLE_DEVICES'] = ''
                            
                            # Try to create a new RAG instance with disabled extensions
                            r_fallback = RAGPretrainedModel.from_pretrained(
                                "colbert-ir/colbertv2.0", 
                                index_root=str(index_root)
                            )
                            r_fallback.index(
                                index_name="policies_index",
                                collection=policies_content,
                                document_ids=policy_ids,
                                document_metadatas=document_metadata,
                                use_faiss=False,
                            )
                            indexing_success = True
                            logger.info("Successfully built index with torch extensions disabled")
                        except Exception as fallback_e:
                            logger.warning(f"Fallback attempt also failed: {fallback_e}")
                
                # In CI environments, don't fail the build - let tests use empty retrieval
                if not indexing_success and (os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS')):
                    logger.warning("Index creation failed in CI GPU environment, tests will continue with empty retrieval")
                    logger.info("Consider checking CUDA installation and torch extension compatibility")
                    return False
                elif not indexing_success:
                    raise Exception(f"Index creation failed: {plaid_e}")
        
        if not indexing_success:
            return False
        
        logger.info("Policies RAG index initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize policies RAG index: {e}", exc_info=True)
        return False


# Alias for backward compatibility
init_index = init_policies_index

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