#!/usr/bin/env python3

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


from agents.policies.vespa.generate_package import generate_package_artifacts
from libraries.observability.logger import get_console_logger

logger = get_console_logger("vespa_deployment")


def check_schema_exists(config_server_url: str, query_url: str, expected_generation: int = None) -> bool:
    """Check if schema is deployed with correct generation."""
    try:
        app_status_url = f"{config_server_url}/application/v2/tenant/default/application/default/environment/prod/region/default/instance/default"
        response = httpx.get(app_status_url, timeout=10.0)
        
        if response.status_code != 200:
            return False
            
        generation = response.json().get("generation", 0)
        if generation == 0:
            return False
        
        if expected_generation is not None and generation < expected_generation:
            return False
        
        # Check schema accessibility
        policy_doc_url = f"{query_url}/document/v1/policies/policy_document/docid/test?cluster=policies_content"
        response = httpx.get(policy_doc_url, timeout=10.0)
        
        if response.status_code in [404, 200]:
            logger.info(f"Schema ready (generation {generation})")
            return True
        return False

    except Exception:
        return False


def deploy_package_from_zip(config_server_url: str, zip_path: Path) -> tuple[bool, str]:
    """Deploy Vespa package via config server."""
    with open(zip_path, "rb") as f:
        zip_content = f.read()

    # Prepare application
    prepare_url = f"{config_server_url}/application/v2/tenant/default/session"
    response = httpx.post(prepare_url, content=zip_content, headers={"Content-Type": "application/zip"}, timeout=60.0)
    
    if response.status_code != 200:
        logger.error(f"Prepare failed: {response.status_code} - {response.text}")
        return False, ""

    session_id = response.json().get("session-id")
    if not session_id:
        logger.error("No session ID returned")
        return False, ""

    # Prepare session
    prepare_session_url = f"{config_server_url}/application/v2/tenant/default/session/{session_id}/prepared"
    response = httpx.put(prepare_session_url, timeout=60.0)
    if response.status_code != 200:
        logger.error(f"Session prepare failed: {response.status_code} - {response.text}")
        return False, session_id

    # Activate session
    activate_url = f"{config_server_url}/application/v2/tenant/default/session/{session_id}/active"
    response = httpx.put(activate_url, timeout=60.0)
    if response.status_code != 200:
        logger.error(f"Activation failed: {response.status_code} - {response.text}")
        return False, session_id

    logger.info(f"Deployed successfully (session {session_id})")
    return True, session_id


def deploy_to_vespa(
    config_server_url: str,
    query_url: str,
    force: bool = False,
    artifacts_dir: Path = None,
    deployment_mode: str = "local",
    node_count: int = 1,
    hosts_config: Path = None,
    services_xml: Path = None,
    app_name: str = "policies",
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
        services_xml: Path to XML file with services configurations
        app_name: Name of the application to deploy
    """
    logger.info(f"Deploying to {config_server_url}")

    # Get current generation
    try:
        response = httpx.get(f"{config_server_url}/application/v2/tenant/default/application/default/environment/prod/region/default/instance/default", timeout=10.0)
        pre_deployment_generation = response.json().get("generation", 0) if response.status_code == 200 else 0
    except Exception as _:
        pre_deployment_generation = 0

    # Check if schema exists
    if not force and check_schema_exists(config_server_url, query_url):
        logger.info("Schema already deployed, skipping")
        return True

    try:
        # Get package artifacts
        if artifacts_dir and artifacts_dir.exists():
            zip_path = artifacts_dir / "vespa-application.zip"
            if not zip_path.exists():
                logger.error(f"Package not found: {zip_path}")
                return False
        else:
            # Generate hosts for production mode
            hosts = None
            if deployment_mode == "production":
                if hosts_config and hosts_config.exists():
                    with open(hosts_config) as f:
                        hosts = json.load(f)
                else:
                    namespace = os.environ.get("KUBERNETES_NAMESPACE", "default")
                    service_name = os.environ.get("VESPA_SERVICE_NAME", "vespa-node")
                    hosts = []
                    for i in range(node_count):
                        if "KUBERNETES_SERVICE_HOST" in os.environ:
                            host_name = f"{service_name}-{i}.{service_name}-internal.{namespace}.svc.cluster.local"
                        else:
                            host_name = f"vespa-node-{i}.eggai-example-network"
                        hosts.append({"name": host_name, "alias": f"node{i}"})

            zip_path, _ = generate_package_artifacts(
                artifacts_dir, deployment_mode=deployment_mode, node_count=node_count,
                hosts=hosts, services_xml=services_xml, app_name=app_name
            )

        # Deploy package
        success, session_id = deploy_package_from_zip(config_server_url, zip_path)
        if not success:
            return False

        # Verify deployment with retry
        expected_generation = pre_deployment_generation + 1
        logger.info(f"Waiting for schema to be ready (generation {expected_generation})...")
        for attempt in range(1, 21):
            logger.info(f"Verification attempt {attempt}/20...")
            if check_schema_exists(config_server_url, query_url, expected_generation):
                logger.info("✅ Deployment verified successfully")
                return True
            
            if attempt < 20:
                logger.info(f"Schema not ready yet, waiting 5 seconds... (attempt {attempt}/20)")
                time.sleep(5)
            else:
                # Final check: verify generation increased AND config server shows convergence
                try:
                    response = httpx.get(f"{config_server_url}/application/v2/tenant/default/application/default/environment/prod/region/default/instance/default", timeout=10.0)
                    if response.status_code == 200:
                        app_data = response.json()
                        current_gen = app_data.get("generation", 0)
                        
                        # Only consider successful if generation increased AND we have model versions
                        if current_gen >= expected_generation and app_data.get("modelVersions"):
                            # Try to check service convergence as additional validation
                            try:
                                conv_response = httpx.get(f"{config_server_url}/application/v2/tenant/default/application/default/environment/prod/region/default/instance/default/serviceconverge", timeout=10.0)
                                if conv_response.status_code == 200:
                                    conv_data = conv_response.json()
                                    if conv_data.get("converged", False):
                                        logger.info(f"✅ Deployment successful (generation {current_gen}, converged)")
                                        return True
                                    else:
                                        logger.warning(f"Generation {current_gen} deployed but services not converged yet")
                            except Exception as _:
                                pass
                            
                            logger.warning(f"Generation {current_gen} deployed but full verification failed - may need manual check")
                            return False
                except Exception as _:
                    pass
                logger.error("Deployment verification failed after 100 seconds")
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

    parser.add_argument(
        "--services-xml",
        type=Path,
        help="XML file with services configurations for production deployment",
    )

    args = parser.parse_args()

    logger.info(f"Vespa deployment: {args.deployment_mode} mode")

    try:
        success = deploy_to_vespa(
            config_server_url=args.config_server,
            query_url=args.query_url,
            force=args.force,
            artifacts_dir=args.artifacts_dir,
            deployment_mode=args.deployment_mode,
            node_count=args.node_count,
            hosts_config=args.hosts_config,
            services_xml=args.services_xml,
        )

        if success:
            logger.info("Deployment completed successfully")
            sys.exit(0)
        else:
            logger.error("Deployment failed")
            sys.exit(1)

    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
