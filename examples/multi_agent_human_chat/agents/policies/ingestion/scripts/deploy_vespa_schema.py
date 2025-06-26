#!/usr/bin/env python3
"""
Script to deploy enhanced Vespa schema with metadata fields.

This script creates a Vespa application package with the enhanced schema
that includes page numbers, headings, relationships, and other metadata.

Usage:
    python deploy_vespa_schema.py [--config-server URL] [--query-url URL] [--force]

Examples:
    # Local deployment
    python deploy_vespa_schema.py
    
    # Kubernetes deployment
    python deploy_vespa_schema.py \
        --config-server http://vespa-configserver-0.vespa-internal.tomcode-shared.svc.cluster.local:19071 \
        --query-url http://vespa-query-0.vespa-internal.tomcode-shared.svc.cluster.local:8080
        
    # Force redeploy even if schema exists
    python deploy_vespa_schema.py --force
"""

import argparse
import sys
import tempfile
import zipfile
from pathlib import Path

import httpx

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from vespa.application import Vespa
from vespa.package import (
    ApplicationPackage,
    Document,
    Field,
    FieldSet,
    RankProfile,
    Schema,
    Validation,
    ValidationID,
)

from libraries.logger import get_console_logger

logger = get_console_logger("vespa_deployment")


def create_validation_overrides() -> Validation:
    """Create validation override to allow content cluster removal.

    Returns:
        Validation object for content cluster removal
    """
    # Set override until tomorrow for immediate deployment needs
    from datetime import datetime, timedelta

    future_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    validation = Validation(
        validation_id=ValidationID.contentClusterRemoval,
        until=future_date,
        comment="Allow content cluster removal during schema updates",
    )

    logger.info(
        f"Created validation override allowing content-cluster-removal until {future_date} (tomorrow)"
    )
    return validation


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
                # Embedding for vector search
                Field(
                    name="embedding",
                    type="tensor<float>(x[384])",  # Using all-MiniLM-L6-v2 which outputs 384 dimensions
                    indexing=["attribute", "index"],
                    attribute=["distance-metric: angular"],
                ),
            ]
        ),
        fieldsets=[FieldSet(name="default", fields=["title", "text"])],
        rank_profiles=[
            RankProfile(name="default", first_phase="nativeRank(title, text)"),
            RankProfile(
                name="with_position",
                first_phase="nativeRank(title, text) * (1.0 - 0.3 * attribute(chunk_position))",
            ),
            RankProfile(
                name="semantic",
                first_phase="closeness(field, embedding)",
                inputs=[("query(query_embedding)", "tensor<float>(x[384])")],
            ),
            RankProfile(
                name="hybrid",
                first_phase="(1.0 - query(alpha)) * nativeRank(title, text) + query(alpha) * closeness(field, embedding)",
                inputs=[
                    ("query(alpha)", "double", "0.7"),
                    ("query(query_embedding)", "tensor<float>(x[384])"),
                ],
            ),
        ],
    )


def create_application_package() -> ApplicationPackage:
    """Create the complete Vespa application package with enhanced schema."""
    logger.info("Creating enhanced Vespa application package")

    # Create schema
    schema = create_policy_document_schema()

    # Create validation override
    validation = create_validation_overrides()

    # Create application package with validation override
    app_package = ApplicationPackage(
        name="policies", schema=[schema], validations=[validation]
    )

    logger.info("Enhanced application package created successfully")
    return app_package


def check_schema_exists(query_url: str) -> bool:
    """Check if the policy_document schema is already deployed.

    Args:
        query_url: Full URL of the Vespa query endpoint (e.g., http://localhost:8080)
    """
    try:
        app = Vespa(url=query_url)

        # Try to query the schema to see if it exists
        response = app.query(yql="select * from policy_document where true limit 1")

        if response.is_successful():
            logger.info("✅ Schema already deployed and functional")
            return True
        else:
            logger.info(
                "Schema not found or not functional, proceeding with deployment"
            )
            return False

    except Exception as e:
        logger.info(f"Unable to check existing schema: {e}, proceeding with deployment")
        return False


def deploy_to_vespa(
    config_server_url: str, query_url: str, force: bool = False
) -> bool:
    """Deploy the enhanced application package to Vespa using the Deploy API.

    Args:
        config_server_url: Full URL of the Vespa config server (e.g., http://localhost:19071)
        query_url: Full URL of the Vespa query endpoint (e.g., http://localhost:8080)
        force: Force deployment even if schema exists
    """
    logger.info("Starting enhanced Vespa deployment")
    logger.info(f"Config server: {config_server_url}")
    logger.info(f"Query endpoint: {query_url}")

    # Check if schema exists
    if not force and check_schema_exists(query_url):
        logger.info("Schema already exists and is active. Skipping deployment.")
        return True

    try:
        # Create application package
        app_package = create_application_package()

        # Create a temporary directory to save the application package
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Save the application package to files
            # The validation overrides are automatically included by the ApplicationPackage
            logger.info("Saving application package to temporary directory")
            app_package.to_files(temp_path)

            # Create a zip file of the application package
            zip_path = temp_path / "application.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for file_path in temp_path.rglob("*"):
                    if file_path.is_file() and file_path != zip_path:
                        arcname = file_path.relative_to(temp_path)
                        zipf.write(file_path, arcname)

            # Deploy using Vespa's Deploy API
            logger.info(
                f"Deploying application package to Vespa config server at {config_server_url}"
            )

            # Prepare the application package
            prepare_url = f"{config_server_url}/application/v2/tenant/default/session"

            with open(zip_path, "rb") as f:
                zip_content = f.read()

            # Create session and upload application
            headers = {"Content-Type": "application/zip"}
            response = httpx.post(
                prepare_url, content=zip_content, headers=headers, timeout=60.0
            )

            if response.status_code != 200:
                logger.error(f"Failed to prepare application: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return False

            session_data = response.json()
            session_id = session_data.get("session-id")

            if not session_id:
                logger.error("No session ID returned from prepare")
                return False

            logger.info(f"Application prepared with session ID: {session_id}")

            # Prepare the session
            prepare_session_url = f"{config_server_url}/application/v2/tenant/default/session/{session_id}/prepared"
            response = httpx.put(prepare_session_url, timeout=60.0)

            if response.status_code != 200:
                logger.error(f"Failed to prepare session: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return False

            logger.info("Session prepared successfully")

            # Activate the session
            activate_url = f"{config_server_url}/application/v2/tenant/default/session/{session_id}/active"
            response = httpx.put(activate_url, timeout=60.0)

            if response.status_code != 200:
                logger.error(f"Failed to activate application: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return False

            logger.info("✅ Application activated successfully!")

            # Wait a bit for the application to be ready
            logger.info("Waiting for schema to be ready...")
            import time

            time.sleep(3)

            # Verify the schema is actually queryable
            if check_schema_exists(query_url):
                logger.info("✅ Schema verified and ready for use!")

                # Log enhanced schema details
                logger.info("Enhanced schema deployed with fields:")
                logger.info(
                    "  Core: id, title, text, category, chunk_index, source_file"
                )
                logger.info(
                    "  Metadata: page_numbers, page_range, headings, char_count, token_count"
                )
                logger.info(
                    "  Relationships: document_id, previous_chunk_id, next_chunk_id, chunk_position"
                )
                logger.info("  Context: section_path")
                logger.info("BM25 indexing enabled on: title, text")
                logger.info("Rank profiles: default, with_position, semantic, hybrid")

                return True
            else:
                logger.warning("Schema deployment completed but verification failed")
                logger.warning(
                    "The schema may still be initializing, waiting a bit more..."
                )
                time.sleep(5)

                # Try one more time
                if check_schema_exists(query_url):
                    logger.info("✅ Schema verified on second attempt!")
                    return True
                else:
                    logger.error("Schema verification failed after deployment")
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
        "--config-server",
        default="http://localhost:19071",
        help="Vespa config server URL (default: http://localhost:19071)",
    )

    parser.add_argument(
        "--query-url",
        default="http://localhost:8080",
        help="Vespa query endpoint URL (default: http://localhost:8080)",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force deployment even if schema exists",
    )

    args = parser.parse_args()

    print("🚀 Enhanced Vespa Schema Deployment Tool")
    print("=" * 50)
    print(f"Config Server: {args.config_server}")
    print(f"Query Endpoint: {args.query_url}")
    print(f"Force: {args.force}")
    print()

    try:
        success = deploy_to_vespa(
            config_server_url=args.config_server,
            query_url=args.query_url,
            force=args.force,
        )

        if success:
            print()
            print("🎉 Enhanced deployment completed successfully!")
            print(f"   Config Server: {args.config_server}")
            print(f"   Query Endpoint: {args.query_url}")
            print("   Schema: policy_document (enhanced)")
            print("   Core fields: id, title, text, category, chunk_index, source_file")
            print(
                "   Metadata fields: page numbers, headings, citations, relationships"
            )
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
