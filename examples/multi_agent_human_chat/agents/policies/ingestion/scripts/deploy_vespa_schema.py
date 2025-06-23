#!/usr/bin/env python3
"""
Script to deploy enhanced Vespa schema with metadata fields.

This script creates a Vespa application package with the enhanced schema
that includes page numbers, headings, relationships, and other metadata.

Usage:
    python deploy_vespa_schema.py [--host HOST] [--port PORT]

Examples:
    python deploy_vespa_schema.py
    python deploy_vespa_schema.py --host vespa-container --port 8080
"""

import argparse
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from vespa.application import Vespa
from vespa.deployment import VespaDocker
from vespa.package import ApplicationPackage, Document, Field, FieldSet, RankProfile, Schema

from libraries.logger import get_console_logger

logger = get_console_logger("vespa_deployment")


def create_policy_document_schema() -> Schema:
    """Create the enhanced policy_document schema with metadata fields."""
    return Schema(
        name="policy_document",
        document=Document(
            fields=[
                # Core fields
                Field(
                    name="id",
                    type="string",
                    indexing=["summary", "index"],
                    match=["word"],
                ),
                Field(
                    name="title", 
                    type="string", 
                    indexing=["summary", "index"],
                    match=["text"],
                    index="enable-bm25",
                ),
                Field(
                    name="text",
                    type="string",
                    indexing=["summary", "index"], 
                    match=["text"],
                    index="enable-bm25",
                ),
                Field(
                    name="category",
                    type="string",
                    indexing=["summary", "attribute"],
                ),
                Field(
                    name="chunk_index",
                    type="int",
                    indexing=["summary", "attribute"],
                ),
                Field(
                    name="source_file",
                    type="string",
                    indexing=["summary", "attribute"],
                ),
                
                # Enhanced metadata fields
                Field(
                    name="page_numbers",
                    type="array<int>",
                    indexing=["summary", "attribute"],
                ),
                Field(
                    name="page_range",
                    type="string",
                    indexing=["summary", "attribute"],
                ),
                Field(
                    name="headings",
                    type="array<string>",
                    indexing=["summary", "attribute"],
                ),
                Field(
                    name="char_count",
                    type="int",
                    indexing=["summary", "attribute"],
                ),
                Field(
                    name="token_count",
                    type="int",
                    indexing=["summary", "attribute"],
                ),
                
                # Relationship fields
                Field(
                    name="document_id",
                    type="string",
                    indexing=["summary", "attribute"],
                ),
                Field(
                    name="previous_chunk_id",
                    type="string",
                    indexing=["summary", "attribute"],
                ),
                Field(
                    name="next_chunk_id",
                    type="string",
                    indexing=["summary", "attribute"],
                ),
                Field(
                    name="chunk_position",
                    type="float",
                    indexing=["summary", "attribute"],
                ),
                
                # Additional context
                Field(
                    name="section_path",
                    type="array<string>",
                    indexing=["summary", "attribute"],
                ),
            ]
        ),
        fieldsets=[FieldSet(name="default", fields=["title", "text"])],
        rank_profiles=[
            RankProfile(
                name="default",
                first_phase="nativeRank(title, text)"
            ),
            RankProfile(
                name="with_position",
                first_phase="nativeRank(title, text) * (1.0 - 0.3 * attribute(chunk_position))"
            )
        ]
    )


def create_application_package() -> ApplicationPackage:
    """Create the complete Vespa application package with enhanced schema."""
    logger.info("Creating enhanced Vespa application package")
    
    # Create schema
    schema = create_policy_document_schema()
    
    # Create application package
    app_package = ApplicationPackage(
        name="policies",
        schema=[schema]
    )
    
    logger.info("Enhanced application package created successfully")
    return app_package


def check_schema_exists(host: str = "localhost", port: int = 8080) -> bool:
    """Check if the policy_document schema is already deployed."""
    try:
        vespa_url = f"http://{host}:{port}"
        app = Vespa(url=vespa_url)
        
        # Try to query the schema to see if it exists
        response = app.query(yql="select * from policy_document where true limit 1")
        
        if response.is_successful():
            logger.info("✅ Schema already deployed and functional")
            return True
        else:
            logger.info("Schema not found or not functional, proceeding with deployment")
            return False
            
    except Exception as e:
        logger.info(f"Unable to check existing schema: {e}, proceeding with deployment")
        return False


def deploy_to_vespa(host: str = "localhost", port: int = 8080, force: bool = False) -> bool:
    """Deploy the enhanced application package to Vespa."""
    logger.info(f"Starting enhanced Vespa deployment to {host}:{port}")
    
    # Check if schema already exists
    if check_schema_exists(host, port) and not force:
        logger.warning("⚠️  Schema already exists. Attempting to update the schema...")
        logger.info("Note: Schema updates in Vespa require compatible changes or container restart.")
    
    try:
        # Create application package
        app_package = create_application_package()
        
        # Deploy using simplified approach to existing container
        logger.info("Deploying enhanced application package to existing container")
        
        try:
            # First try: Connect to existing container by name
            vespa_container = VespaDocker.from_container_name_or_id("vespa-container")
            vespa_connection = vespa_container.deploy(application_package=app_package)
        except Exception as e:
            logger.warning(f"Container name deployment failed: {e}")
            logger.info("Trying simplified VespaDocker approach...")
            
            # Fallback: Use basic VespaDocker (will create new container)
            vespa_container = VespaDocker()
            vespa_connection = vespa_container.deploy(application_package=app_package)
        
        if vespa_connection is None:
            logger.error("Deployment failed - vespa_connection is None")
            return False
        
        # Verify deployment
        logger.info("Verifying enhanced deployment...")
        vespa_url = f"http://{host}:{port}"
        verification_app = Vespa(url=vespa_url)
        
        try:
            # Test basic connectivity and schema
            response = verification_app.query(yql="select * from policy_document where true limit 1")
            if response.is_successful():
                logger.info("✅ Enhanced deployment successful! Schema is ready for use.")
                logger.info(f"Application available at: {vespa_url}")
                
                # Log enhanced schema details
                logger.info("Enhanced schema deployed with fields:")
                logger.info("  Core: id, title, text, category, chunk_index, source_file")
                logger.info("  Metadata: page_numbers, page_range, headings, char_count, token_count")
                logger.info("  Relationships: document_id, previous_chunk_id, next_chunk_id, chunk_position")
                logger.info("  Context: section_path")
                logger.info("BM25 indexing enabled on: title, text")
                logger.info("Rank profiles: default, with_position")
                
                return True
            else:
                logger.error(f"Deployment verification failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Deployment verification error: {e}")
            return False
            
    except Exception as e:
        logger.error(f"Deployment failed: {e}", exc_info=True)
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Deploy enhanced Vespa schema with metadata support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    
    parser.add_argument(
        "--host",
        default="localhost",
        help="Vespa host (default: localhost)",
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Vespa port (default: 8080)",
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force deployment even if schema exists",
    )
    
    args = parser.parse_args()
    
    print("🚀 Enhanced Vespa Schema Deployment Tool")
    print("=" * 50)
    print(f"Target: {args.host}:{args.port}")
    print()
    
    try:
        success = deploy_to_vespa(args.host, args.port, args.force)
        
        if success:
            print()
            print("🎉 Enhanced deployment completed successfully!")
            print(f"   Vespa is ready at: http://{args.host}:{args.port}")
            print("   Schema: policy_document (enhanced)")
            print("   Core fields: id, title, text, category, chunk_index, source_file")
            print("   Metadata fields: page numbers, headings, citations, relationships")
            print()
            print("   Next steps:")
            print("   1. Re-index your documents to populate the new metadata fields")
            print("   2. Use the enhanced search API to get page citations")
            sys.exit(0)
        else:
            print()
            print("❌ Deployment failed or skipped!")
            print("   Check the logs above for details.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("Deployment cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()