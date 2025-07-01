#!/usr/bin/env python3
"""
Generate Vespa application package for policies.

This module contains functions to create the Vespa schema and application package
with all necessary configurations for the policies search system.

Usage:
    python generate_package.py [--output-dir DIR]
"""

import argparse
import json
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from xml.dom import minidom

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

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

logger = get_console_logger("vespa_package_generator")


def create_validation_overrides() -> Validation:
    """Create validation override to allow content cluster removal.

    Returns:
        Validation object for content cluster removal
    """
    # Set override until tomorrow for immediate deployment needs
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


def create_hosts_xml(hosts: List[Dict[str, str]]) -> str:
    """Create hosts.xml content for multi-node deployment.
    
    Args:
        hosts: List of host configurations, each with 'name' and 'alias' keys
        
    Returns:
        Formatted XML string for hosts.xml
    """
    root = ET.Element('hosts')
    
    for host in hosts:
        host_elem = ET.SubElement(root, 'host', name=host['name'])
        ET.SubElement(host_elem, 'alias').text = host['alias']
    
    # Pretty print the XML
    rough_string = ET.tostring(root, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="    ")


def create_services_xml(node_count: int = 1, redundancy: int = 1) -> str:
    """Create services.xml content with configurable nodes.
    
    Args:
        node_count: Number of nodes in the cluster
        redundancy: Data redundancy factor
        
    Returns:
        Formatted XML string for services.xml
    """
    root = ET.Element('services', version='1.0')
    
    # Admin cluster (required for multi-node)
    if node_count > 1:
        admin = ET.SubElement(root, 'admin', version='2.0')
        adminserver = ET.SubElement(admin, 'adminserver', hostalias='node0')
    
    # Container cluster
    container = ET.SubElement(root, 'container', id='policies_container', version='1.0')
    ET.SubElement(container, 'search')
    ET.SubElement(container, 'document-api')
    ET.SubElement(container, 'document-processing')
    
    # Add nodes to container if multi-node
    if node_count > 1:
        nodes = ET.SubElement(container, 'nodes')
        for i in range(node_count):
            ET.SubElement(nodes, 'node', hostalias=f'node{i}')
    
    # Content cluster
    content = ET.SubElement(root, 'content', id='policies_content', version='1.0')
    ET.SubElement(content, 'redundancy').text = str(redundancy)
    
    # Documents
    documents = ET.SubElement(content, 'documents')
    ET.SubElement(documents, 'document', type='policy_document', mode='index')
    
    # Content nodes
    nodes = ET.SubElement(content, 'nodes')
    for i in range(node_count):
        ET.SubElement(nodes, 'node', **{'distribution-key': str(i), 'hostalias': f'node{i}'})
    
    # Pretty print the XML
    rough_string = ET.tostring(root, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="    ")


def save_package_to_zip(app_package: ApplicationPackage, output_path: Path, 
                       deployment_mode: str = 'local', node_count: int = 1,
                       hosts: Optional[List[Dict[str, str]]] = None) -> Path:
    """Save the application package as a zip file with deployment configurations.
    
    Args:
        app_package: The Vespa application package
        output_path: Path where to save the zip file
        deployment_mode: 'local' or 'production'
        node_count: Number of nodes (for production mode)
        hosts: Host configurations (for production mode)
        
    Returns:
        Path to the created zip file
    """
    # Create a temporary directory to save the application package
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Save the application package to files
        logger.info("Saving application package to temporary directory")
        app_package.to_files(temp_path)
        
        # For production deployment, customize services.xml and add hosts.xml
        if deployment_mode == 'production':
            # Calculate redundancy based on node count
            redundancy = min(node_count, 2)  # Max redundancy of 2 for small clusters
            
            # Override services.xml with multi-node configuration
            services_xml = create_services_xml(node_count, redundancy)
            services_path = temp_path / 'services.xml'
            services_path.write_text(services_xml)
            logger.info(f"Created custom services.xml for {node_count} nodes with redundancy {redundancy}")
            
            # Create hosts.xml if hosts are provided
            if hosts:
                hosts_xml = create_hosts_xml(hosts)
                hosts_path = temp_path / 'hosts.xml'
                hosts_path.write_text(hosts_xml)
                logger.info(f"Created hosts.xml with {len(hosts)} host definitions")
        
        # Create a zip file of the application package
        zip_path = output_path / "vespa-application.zip"
        logger.info(f"Creating zip file at {zip_path}")
        
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file_path in temp_path.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(temp_path)
                    zipf.write(file_path, arcname)
        
        logger.info(f"Application package saved to {zip_path}")
        return zip_path


def save_package_metadata(output_path: Path, schema_info: dict) -> Path:
    """Save package metadata as JSON for reference.
    
    Args:
        output_path: Directory where to save the metadata
        schema_info: Dictionary containing schema information
        
    Returns:
        Path to the metadata file
    """
    metadata_path = output_path / "package-metadata.json"
    
    with open(metadata_path, "w") as f:
        json.dump(schema_info, f, indent=2)
    
    logger.info(f"Package metadata saved to {metadata_path}")
    return metadata_path


def generate_package_artifacts(output_dir: Optional[Path] = None, 
                             deployment_mode: str = 'local',
                             node_count: int = 1,
                             hosts: Optional[List[Dict[str, str]]] = None) -> tuple[Path, Path]:
    """Generate Vespa package artifacts.
    
    Args:
        output_dir: Directory where to save artifacts. If None, uses default location.
        deployment_mode: 'local' or 'production'
        node_count: Number of nodes for production deployment
        hosts: Host configurations for production deployment
        
    Returns:
        Tuple of (zip_path, metadata_path)
    """
    if output_dir is None:
        output_dir = Path(__file__).parent / "artifacts"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create the application package
    app_package = create_application_package()
    
    # Save as zip file with deployment configurations
    zip_path = save_package_to_zip(app_package, output_dir, deployment_mode, node_count, hosts)
    
    # Create metadata
    schema_info = {
        "name": "policies",
        "generated_at": datetime.now().isoformat(),
        "deployment": {
            "mode": deployment_mode,
            "node_count": node_count,
            "hosts": hosts or []
        },
        "schema": {
            "name": "policy_document",
            "fields": {
                "core": ["id", "title", "text", "category", "chunk_index", "source_file"],
                "metadata": ["page_numbers", "page_range", "headings", "char_count", "token_count"],
                "relationships": ["document_id", "previous_chunk_id", "next_chunk_id", "chunk_position"],
                "context": ["section_path"],
                "vector": ["embedding (384 dimensions)"]
            },
            "rank_profiles": ["default", "with_position", "semantic", "hybrid"],
            "indexing": {
                "bm25_enabled": ["title", "text"],
                "vector_search": "embedding field with angular distance metric"
            }
        }
    }
    
    # Save metadata
    metadata_path = save_package_metadata(output_dir, schema_info)
    
    return zip_path, metadata_path


def main():
    """Main entry point for package generation."""
    parser = argparse.ArgumentParser(
        description="Generate Vespa application package for policies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory to save package artifacts (default: ./artifacts)",
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
    
    # Load hosts configuration if provided
    hosts = None
    if args.deployment_mode == 'production' and args.hosts_config:
        if args.hosts_config.exists():
            with open(args.hosts_config) as f:
                hosts = json.load(f)
        else:
            # Generate default hosts for the given node count
            hosts = []
            for i in range(args.node_count):
                hosts.append({
                    'name': f'vespa-node-{i}.vespa-internal.svc.cluster.local',
                    'alias': f'node{i}'
                })
            logger.info(f"Generated default host configuration for {args.node_count} nodes")

    print("🚀 Vespa Package Generator")
    print("=" * 50)
    
    try:
        zip_path, metadata_path = generate_package_artifacts(
            args.output_dir,
            deployment_mode=args.deployment_mode,
            node_count=args.node_count,
            hosts=hosts
        )
        
        print()
        print("🎉 Package generation completed successfully!")
        print(f"   Package ZIP: {zip_path}")
        print(f"   Metadata: {metadata_path}")
        print(f"   Deployment mode: {args.deployment_mode}")
        if args.deployment_mode == 'production':
            print(f"   Node count: {args.node_count}")
            print(f"   Redundancy: {min(args.node_count, 2)}")
        print()
        print("   Schema details:")
        print("   - Name: policy_document")
        print("   - Core fields: id, title, text, category, chunk_index, source_file")
        print("   - Metadata fields: page numbers, headings, char/token counts")
        print("   - Relationship tracking: previous/next chunks, document associations")
        print("   - Vector search: 384-dimensional embeddings")
        print("   - Rank profiles: default, with_position, semantic, hybrid")
        
    except Exception as e:
        logger.error(f"Failed to generate package: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()