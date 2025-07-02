#!/usr/bin/env python3
"""
Deploy Vespa application package from generated artifacts.

This script deploys a pre-generated Vespa application package to the Vespa cluster.
It first generates the package using generate_package.py, then deploys the artifacts.

Usage:
    python deploy_package.py [--config-server URL] [--query-url URL] [--force] [--artifacts-dir DIR]

Examples:
    # Local deployment (generates and deploys)
    python deploy_package.py
    
    # Kubernetes deployment
    python deploy_package.py \
        --config-server http://vespa-configserver-0.vespa-internal.my-namespace.svc.cluster.local:19071 \
        --query-url http://vespa-query-0.vespa-internal.my-namespace.svc.cluster.local:8080
        
    # Force redeploy even if schema exists
    python deploy_package.py --force
    
    # Use pre-generated artifacts
    python deploy_package.py --artifacts-dir ./my-artifacts
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from vespa.application import Vespa

from agents.policies.vespa.generate_package import generate_package_artifacts
from libraries.logger import get_console_logger

logger = get_console_logger("vespa_deployment")


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


def deploy_package_from_zip(config_server_url: str, zip_path: Path) -> tuple[bool, str]:
    """Deploy a Vespa application package from a zip file.

    Args:
        config_server_url: Full URL of the Vespa config server
        zip_path: Path to the application package zip file

    Returns:
        Tuple of (success, session_id)
    """
    logger.info(f"Deploying package from {zip_path}")

    # Read the zip file
    with open(zip_path, "rb") as f:
        zip_content = f.read()

    # Prepare the application package
    prepare_url = f"{config_server_url}/application/v2/tenant/default/session"
    headers = {"Content-Type": "application/zip"}

    response = httpx.post(
        prepare_url, content=zip_content, headers=headers, timeout=60.0
    )

    if response.status_code != 200:
        logger.error(f"Failed to prepare application: {response.status_code}")
        logger.error(f"Response: {response.text}")
        return False, ""

    session_data = response.json()
    session_id = session_data.get("session-id")

    if not session_id:
        logger.error("No session ID returned from prepare")
        return False, ""

    logger.info(f"Application prepared with session ID: {session_id}")

    # Prepare the session
    prepare_session_url = f"{config_server_url}/application/v2/tenant/default/session/{session_id}/prepared"
    response = httpx.put(prepare_session_url, timeout=60.0)

    if response.status_code != 200:
        logger.error(f"Failed to prepare session: {response.status_code}")
        logger.error(f"Response: {response.text}")
        return False, session_id

    logger.info("Session prepared successfully")

    # Activate the session
    activate_url = (
        f"{config_server_url}/application/v2/tenant/default/session/{session_id}/active"
    )
    response = httpx.put(activate_url, timeout=60.0)

    if response.status_code != 200:
        logger.error(f"Failed to activate application: {response.status_code}")
        logger.error(f"Response: {response.text}")
        return False, session_id

    logger.info("✅ Application activated successfully!")
    return True, session_id


def deploy_to_vespa(
    config_server_url: str,
    query_url: str,
    force: bool = False,
    artifacts_dir: Path = None,
    deployment_mode: str = "local",
    node_count: int = 1,
    hosts_config: Path = None,
) -> bool:
    """Deploy the enhanced application package to Vespa.

    Args:
        config_server_url: Full URL of the Vespa config server (e.g., http://localhost:19071)
        query_url: Full URL of the Vespa query endpoint (e.g., http://localhost:8080)
        force: Force deployment even if schema exists
        artifacts_dir: Directory containing pre-generated artifacts. If None, generates new ones.
        deployment_mode: 'local' or 'production'
        node_count: Number of nodes for production deployment
        hosts_config: Path to JSON file with host configurations
    """
    logger.info("Starting enhanced Vespa deployment")
    logger.info(f"Config server: {config_server_url}")
    logger.info(f"Query endpoint: {query_url}")

    # Check if schema exists
    if not force and check_schema_exists(query_url):
        logger.info("Schema already exists and is active. Skipping deployment.")
        return True

    try:
        # Generate or locate package artifacts
        if artifacts_dir and artifacts_dir.exists():
            # Use existing artifacts
            zip_path = artifacts_dir / "vespa-application.zip"
            metadata_path = artifacts_dir / "package-metadata.json"

            if not zip_path.exists():
                logger.error(f"Package zip not found at {zip_path}")
                return False

            logger.info(f"Using existing package from {artifacts_dir}")
        else:
            # Generate new artifacts
            logger.info("Generating new package artifacts...")

            # Load hosts configuration if provided
            hosts = None
            if deployment_mode == "production":
                if hosts_config and hosts_config.exists():
                    with open(hosts_config) as f:
                        hosts = json.load(f)
                    logger.info(f"Loaded hosts configuration from {hosts_config}")
                else:
                    # Generate default hosts based on environment
                    # Check if we're in Kubernetes by looking for common env vars
                    namespace = os.environ.get("KUBERNETES_NAMESPACE", "default")
                    service_name = os.environ.get("VESPA_SERVICE_NAME", "vespa-node")

                    hosts = []
                    for i in range(node_count):
                        if "KUBERNETES_SERVICE_HOST" in os.environ:
                            # Kubernetes environment
                            host_name = f"{service_name}-{i}.{service_name}-internal.{namespace}.svc.cluster.local"
                        else:
                            # Default to local Docker names with network domain
                            host_name = f"vespa-node-{i}.eggai-example-network"

                        hosts.append({"name": host_name, "alias": f"node{i}"})
                    logger.info(
                        f"Generated {len(hosts)} host configurations for {deployment_mode} environment"
                    )

            zip_path, metadata_path = generate_package_artifacts(
                artifacts_dir,
                deployment_mode=deployment_mode,
                node_count=node_count,
                hosts=hosts,
            )

        # Deploy the package
        success, session_id = deploy_package_from_zip(config_server_url, zip_path)

        if not success:
            logger.error("Deployment failed")
            return False

        # Wait a bit for the application to be ready
        logger.info("Waiting for schema to be ready...")
        time.sleep(10)  # Give more time for multi-node setup

        # Verify the schema is actually queryable
        if check_schema_exists(query_url):
            logger.info("✅ Schema verified and ready for use!")

            # Log enhanced schema details
            logger.info("Enhanced schema deployed with fields:")
            logger.info("  Core: id, title, text, category, chunk_index, source_file")
            logger.info(
                "  Metadata: page_numbers, page_range, headings, char_count, token_count"
            )
            logger.info(
                "  Relationships: document_id, previous_chunk_id, next_chunk_id, chunk_position"
            )
            logger.info("  Context: section_path")
            logger.info("  BM25 indexing enabled on: title, text")
            logger.info("  Rank profiles: default, with_position, semantic, hybrid")

            return True
        else:
            logger.warning("Schema deployment completed but verification failed")
            logger.warning(
                "The schema may still be initializing, waiting a bit more..."
            )
            time.sleep(20)  # Give extra time for multi-node coordination

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
        description="Deploy Vespa application package",
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

    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        help="Directory containing pre-generated artifacts (optional)",
    )

    parser.add_argument(
        "--deployment-mode",
        choices=["local", "production"],
        default="local",
        help="Deployment mode: local (single-node) or production (multi-node)",
    )

    parser.add_argument(
        "--node-count",
        type=int,
        default=3,
        help="Number of nodes for production deployment (default: 3)",
    )

    parser.add_argument(
        "--hosts-config",
        type=Path,
        help="JSON file with host configurations for production deployment",
    )

    args = parser.parse_args()

    print("🚀 Enhanced Vespa Package Deployment Tool")
    print("=" * 50)
    print(f"Config Server: {args.config_server}")
    print(f"Query Endpoint: {args.query_url}")
    print(f"Force: {args.force}")
    print(f"Deployment Mode: {args.deployment_mode}")
    if args.deployment_mode == "production":
        print(f"Node Count: {args.node_count}")
        if args.hosts_config:
            print(f"Hosts Config: {args.hosts_config}")
    if args.artifacts_dir:
        print(f"Artifacts Dir: {args.artifacts_dir}")
    print()

    try:
        success = deploy_to_vespa(
            config_server_url=args.config_server,
            query_url=args.query_url,
            force=args.force,
            artifacts_dir=args.artifacts_dir,
            deployment_mode=args.deployment_mode,
            node_count=args.node_count,
            hosts_config=args.hosts_config,
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
