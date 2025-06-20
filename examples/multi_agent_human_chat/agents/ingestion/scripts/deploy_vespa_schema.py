#!/usr/bin/env python3
"""
Script to deploy Vespa schema using pyvespa programmatic deployment.

This script creates a Vespa application package from the existing schema
and deploys it to a VespaDocker instance without requiring vespa-cli
or pre-built Docker images.

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
from vespa.package import ApplicationPackage, Document, Field, FieldSet, Schema

from libraries.logger import get_console_logger

logger = get_console_logger("vespa_deployment")


def create_policy_document_schema() -> Schema:
    """Create the policy_document schema programmatically."""
    return Schema(
        name="policy_document",
        document=Document(
            fields=[
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
            ]
        ),
        fieldsets=[FieldSet(name="default", fields=["title", "text"])],
    )


def create_application_package() -> ApplicationPackage:
    """Create the complete Vespa application package."""
    logger.info("Creating Vespa application package")
    
    # Create schema
    schema = create_policy_document_schema()
    
    # Create application package - pyvespa will handle the XML configuration
    app_package = ApplicationPackage(
        name="policies",
        schema=[schema]
    )
    
    logger.info("Application package created successfully")
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


def deploy_to_vespa(host: str = "localhost", port: int = 8080) -> bool:
    """Deploy the application package to Vespa using simplified deployment."""
    logger.info(f"Starting Vespa deployment to {host}:{port}")
    
    # Check if schema already exists
    if check_schema_exists(host, port):
        logger.info("Schema already deployed, skipping deployment")
        return True
    
    try:
        # Create application package
        app_package = create_application_package()
        
        # Deploy using simplified approach to existing container
        logger.info("Deploying application package to existing container")
        
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
        logger.info("Verifying deployment...")
        vespa_url = f"http://{host}:{port}"
        verification_app = Vespa(url=vespa_url)
        
        try:
            # Test basic connectivity and schema
            response = verification_app.query(yql="select * from policy_document where true limit 1")
            if response.is_successful():
                logger.info("✅ Deployment successful! Schema is ready for use.")
                logger.info(f"Application available at: {vespa_url}")
                
                # Log schema details
                logger.info("Schema deployed with fields: id, title, text, category, chunk_index, source_file")
                logger.info("BM25 indexing enabled on: title, text")
                
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
        description="Deploy Vespa schema using pyvespa",
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
    
    args = parser.parse_args()
    
    print("🚀 Vespa Schema Deployment Tool")
    print("=" * 50)
    print(f"Target: {args.host}:{args.port}")
    print()
    
    try:
        success = deploy_to_vespa(args.host, args.port)
        
        if success:
            print()
            print("🎉 Deployment completed successfully!")
            print(f"   Vespa is ready at: http://{args.host}:{args.port}")
            print("   Schema: policy_document")
            print("   Fields: id, title, text, category, chunk_index, source_file")
            sys.exit(0)
        else:
            print()
            print("❌ Deployment failed!")
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