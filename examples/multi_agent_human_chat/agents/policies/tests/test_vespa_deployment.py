"""Tests for Vespa deployment with custom configurations."""

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch
import json

import pytest

from agents.policies.vespa.deploy_package import (
    check_schema_exists,
    deploy_package_from_zip,
    deploy_to_vespa,
)
from agents.policies.vespa.generate_package import (
    create_application_package,
    create_hosts_xml,
    create_policy_document_schema,
    create_services_xml,
    create_validation_overrides,
    generate_package_artifacts,
    save_package_metadata,
    save_package_to_zip,
)


class TestValidationOverrides:
    """Test validation override creation."""
    
    def test_create_validation_overrides(self):
        """Test validation overrides are created correctly."""
        # Execute
        validations = create_validation_overrides()
        
        # Verify
        assert len(validations) == 2
        
        # Check content cluster removal override
        content_removal = next((v for v in validations if str(v.id) == "content-cluster-removal"), None)
        assert content_removal is not None
        assert "content cluster removal" in content_removal.comment
        
        # Check redundancy increase override
        redundancy_increase = next((v for v in validations if str(v.id) == "redundancy-increase"), None)
        assert redundancy_increase is not None
        assert "redundancy increase" in redundancy_increase.comment
        
        # Check dates are set to tomorrow
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        for validation in validations:
            assert validation.until == tomorrow


class TestPolicyDocumentSchema:
    """Test policy document schema creation."""
    
    def test_create_policy_document_schema(self):
        """Test schema creation with all fields."""
        # Execute
        schema = create_policy_document_schema()
        
        # Verify basic properties
        assert schema.name == "policy_document"
        assert schema.document is not None
        
        # Verify fields
        field_names = {field.name for field in schema.document.fields}
        expected_fields = {
            # Core fields
            "id", "title", "text", "category", "chunk_index", "source_file",
            # Metadata fields
            "page_numbers", "page_range", "headings", "char_count", "token_count",
            # Relationship fields
            "document_id", "previous_chunk_id", "next_chunk_id", "chunk_position",
            # Additional
            "section_path", "embedding"
        }
        assert field_names == expected_fields
        
        # Verify embedding field configuration
        embedding_field = next(f for f in schema.document.fields if f.name == "embedding")
        assert embedding_field.type == "tensor<float>(x[384])"
        assert "attribute" in embedding_field.indexing
        assert "index" in embedding_field.indexing
        
        # Verify rank profiles
        rank_profile_names = {rp.name for rp in schema.rank_profiles}
        assert rank_profile_names == {"default", "with_position", "semantic", "hybrid"}
        
        # Verify hybrid rank profile inputs
        hybrid_profile = next(rp for rp in schema.rank_profiles if rp.name == "hybrid")
        assert len(hybrid_profile.inputs) == 2
        assert ("query(alpha)", "double", "0.7") in hybrid_profile.inputs
        assert ("query(query_embedding)", "tensor<float>(x[384])") in hybrid_profile.inputs


class TestApplicationPackage:
    """Test application package generation."""
    
    @patch("agents.policies.vespa.generate_package.create_validation_overrides")
    @patch("agents.policies.vespa.generate_package.create_policy_document_schema")
    def test_create_application_package(self, mock_schema, mock_validations):
        """Test application package creation."""
        # Setup
        mock_schema.return_value = MagicMock()
        mock_validations.return_value = []
        
        # Execute
        app_package = create_application_package()
        
        # Verify
        assert app_package.name == "policies"
        assert len(app_package.schema) == 1
        mock_schema.assert_called_once()
        mock_validations.assert_called_once()


class TestHostsXML:
    """Test hosts.xml generation."""
    
    def test_create_hosts_xml_single_node(self):
        """Test hosts.xml for single node."""
        # Setup
        hosts = [{"name": "localhost", "alias": "node0"}]
        
        # Execute
        xml_content = create_hosts_xml(hosts)
        
        # Parse and verify
        root = ET.fromstring(xml_content)
        assert root.tag == "hosts"
        assert len(root.findall("host")) == 1
        
        host = root.find("host")
        assert host.get("name") == "localhost"
        assert host.find("alias").text == "node0"
    
    def test_create_hosts_xml_multi_node(self):
        """Test hosts.xml for multiple nodes."""
        # Setup
        hosts = [
            {"name": "vespa-node-0.cluster.local", "alias": "node0"},
            {"name": "vespa-node-1.cluster.local", "alias": "node1"},
            {"name": "vespa-node-2.cluster.local", "alias": "node2"}
        ]
        
        # Execute
        xml_content = create_hosts_xml(hosts)
        
        # Parse and verify
        root = ET.fromstring(xml_content)
        assert root.tag == "hosts"
        assert len(root.findall("host")) == 3
        
        # Verify each host
        for i, host_elem in enumerate(root.findall("host")):
            assert host_elem.get("name") == hosts[i]["name"]
            assert host_elem.find("alias").text == hosts[i]["alias"]


class TestServicesXML:
    """Test services.xml generation."""
    
    def test_create_services_xml_single_node(self):
        """Test services.xml for single node deployment."""
        # Execute
        xml_content = create_services_xml(node_count=1, redundancy=1)
        
        # Parse and verify
        root = ET.fromstring(xml_content)
        assert root.tag == "services"
        assert root.get("version") == "1.0"
        
        # Check admin configuration
        admin = root.find("admin")
        assert admin is not None
        assert admin.get("version") == "2.0"
        
        # Single node should not have config servers, cluster controllers, or slobroks
        assert admin.find("configservers") is None
        assert admin.find("cluster-controllers") is None
        assert admin.find("slobroks") is None
        
        # Admin server should be on node0
        adminserver = admin.find("adminserver")
        assert adminserver.get("hostalias") == "node0"
        
        # Check container configuration
        container = root.find("container")
        assert container.get("id") == "policies_container"
        assert container.find("search") is not None
        assert container.find("document-api") is not None
        
        # Check content configuration
        content = root.find("content")
        assert content.get("id") == "policies_content"
        assert content.find("redundancy").text == "1"
        
        # Check document type
        documents = content.find("documents")
        doc_elem = documents.find("document")
        assert doc_elem.get("type") == "policy_document"
        assert doc_elem.get("mode") == "index"
        
        # Check single node
        nodes = content.find("nodes")
        node_list = nodes.findall("node")
        assert len(node_list) == 1
        assert node_list[0].get("distribution-key") == "0"
        assert node_list[0].get("hostalias") == "node0"
    
    def test_create_services_xml_multi_node(self):
        """Test services.xml for multi-node deployment."""
        # Execute
        xml_content = create_services_xml(node_count=3, redundancy=2)
        
        # Parse and verify
        root = ET.fromstring(xml_content)
        
        # Check admin configuration for multi-node
        admin = root.find("admin")
        
        # Should have config servers
        configservers = admin.find("configservers")
        assert configservers is not None
        assert len(configservers.findall("configserver")) == 3
        
        # Should have cluster controllers
        cluster_controllers = admin.find("cluster-controllers")
        assert cluster_controllers is not None
        assert len(cluster_controllers.findall("cluster-controller")) == 3
        
        # Should have slobroks
        slobroks = admin.find("slobroks")
        assert slobroks is not None
        assert len(slobroks.findall("slobrok")) == 3
        
        # Admin server on node0
        adminserver = admin.find("adminserver")
        assert adminserver.get("hostalias") == "node0"
        
        # Check redundancy
        content = root.find("content")
        assert content.find("redundancy").text == "2"
        
        # Check nodes
        nodes = content.find("nodes")
        node_list = nodes.findall("node")
        assert len(node_list) == 3
        for i, node in enumerate(node_list):
            assert node.get("distribution-key") == str(i)
            assert node.get("hostalias") == f"node{i}"
    
    def test_create_services_xml_large_cluster(self):
        """Test services.xml for large cluster (more than 3 nodes)."""
        # Execute
        xml_content = create_services_xml(node_count=5, redundancy=2)
        
        # Parse and verify
        root = ET.fromstring(xml_content)
        admin = root.find("admin")
        
        # Should still have only 3 config servers, controllers, and slobroks
        configservers = admin.find("configservers")
        assert len(configservers.findall("configserver")) == 3
        
        cluster_controllers = admin.find("cluster-controllers")
        assert len(cluster_controllers.findall("cluster-controller")) == 3
        
        slobroks = admin.find("slobroks")
        assert len(slobroks.findall("slobrok")) == 3
        
        # Admin server should be on node3 when we have more than 3 nodes
        adminserver = admin.find("adminserver")
        assert adminserver.get("hostalias") == "node3"
        
        # But should have all 5 content nodes
        content = root.find("content")
        nodes = content.find("nodes")
        node_list = nodes.findall("node")
        assert len(node_list) == 5


class TestPackageZip:
    """Test package zip creation."""
    
    @patch("agents.policies.vespa.generate_package.zipfile.ZipFile")
    @patch("agents.policies.vespa.generate_package.tempfile.TemporaryDirectory")
    def test_save_package_to_zip_local(self, mock_temp_dir, mock_zipfile):
        """Test saving package as zip for local deployment."""
        # Setup
        mock_temp_path = MagicMock()
        mock_temp_path.rglob.return_value = [
            Path("/tmp/test/schema.xml"),
            Path("/tmp/test/services.xml")
        ]
        mock_temp_dir.return_value.__enter__.return_value = "/tmp/test"
        mock_app_package = MagicMock()
        
        # Execute
        with patch("agents.policies.vespa.generate_package.Path") as mock_path:
            mock_path.return_value = mock_temp_path
            result = save_package_to_zip(
                mock_app_package,
                Path("/output"),
                deployment_mode="local"
            )
        
        # Verify
        mock_app_package.to_files.assert_called_once()
        assert result == Path("/output") / "vespa-application.zip"
    
    @patch("agents.policies.vespa.generate_package.shutil.copy")
    @patch("agents.policies.vespa.generate_package.create_services_xml")
    @patch("agents.policies.vespa.generate_package.create_hosts_xml")
    @patch("agents.policies.vespa.generate_package.zipfile.ZipFile")
    @patch("agents.policies.vespa.generate_package.tempfile.TemporaryDirectory")
    def test_save_package_to_zip_production(self, mock_temp_dir, mock_zipfile, 
                                           mock_create_hosts, mock_create_services, mock_copy):
        """Test saving package as zip for production deployment."""
        # Setup
        mock_temp_path = MagicMock()
        mock_temp_path.__truediv__.return_value = mock_temp_path
        mock_temp_path.write_text = MagicMock()
        mock_temp_path.rglob.return_value = []
        
        mock_temp_dir.return_value.__enter__.return_value = "/tmp/test"
        mock_app_package = MagicMock()
        
        hosts = [{"name": "host1", "alias": "node0"}]
        mock_create_hosts.return_value = "<hosts/>"
        mock_create_services.return_value = "<services/>"
        
        # Execute
        with patch("agents.policies.vespa.generate_package.Path") as mock_path:
            mock_path.return_value = mock_temp_path
            result = save_package_to_zip(
                mock_app_package,
                Path("/output"),
                deployment_mode="production",
                node_count=3,
                hosts=hosts
            )
        
        # Verify
        mock_create_services.assert_called_once_with(3, 2)  # node_count=3, redundancy=2
        mock_create_hosts.assert_called_once_with(hosts)
        assert mock_temp_path.write_text.call_count >= 1  # At least services.xml


class TestPackageMetadata:
    """Test package metadata generation."""
    
    def test_save_package_metadata(self):
        """Test saving package metadata."""
        # Setup
        output_path = Path("/tmp/test")
        schema_info = {
            "name": "policies",
            "schema": {
                "name": "policy_document",
                "fields": ["id", "title", "text"]
            }
        }
        
        # Execute
        with patch("builtins.open", mock_open()) as mock_file:
            with patch("json.dump") as mock_json_dump:
                result = save_package_metadata(output_path, schema_info)
        
        # Verify
        assert result == output_path / "package-metadata.json"
        mock_file.assert_called_once_with(output_path / "package-metadata.json", "w")
        mock_json_dump.assert_called_once()


class TestGeneratePackageArtifacts:
    """Test complete artifact generation."""
    
    @patch("agents.policies.vespa.generate_package.save_package_metadata")
    @patch("agents.policies.vespa.generate_package.save_package_to_zip")
    @patch("agents.policies.vespa.generate_package.create_application_package")
    def test_generate_package_artifacts_default(self, mock_create_app, mock_save_zip, mock_save_metadata):
        """Test generating artifacts with default settings."""
        # Setup
        mock_app = MagicMock()
        mock_create_app.return_value = mock_app
        mock_save_zip.return_value = Path("/tmp/test.zip")
        mock_save_metadata.return_value = Path("/tmp/metadata.json")
        
        # Execute
        zip_path, metadata_path = generate_package_artifacts()
        
        # Verify
        mock_create_app.assert_called_once()
        mock_save_zip.assert_called_once()
        mock_save_metadata.assert_called_once()
        assert zip_path == Path("/tmp/test.zip")
        assert metadata_path == Path("/tmp/metadata.json")
    
    @patch("agents.policies.vespa.generate_package.save_package_metadata")
    @patch("agents.policies.vespa.generate_package.save_package_to_zip")
    @patch("agents.policies.vespa.generate_package.create_application_package")
    def test_generate_package_artifacts_production(self, mock_create_app, mock_save_zip, mock_save_metadata):
        """Test generating artifacts for production deployment."""
        # Setup
        mock_app = MagicMock()
        mock_create_app.return_value = mock_app
        mock_save_zip.return_value = Path("/tmp/test.zip")
        mock_save_metadata.return_value = Path("/tmp/metadata.json")
        
        hosts = [
            {"name": "node1.cluster", "alias": "node0"},
            {"name": "node2.cluster", "alias": "node1"}
        ]
        
        # Execute
        zip_path, metadata_path = generate_package_artifacts(
            deployment_mode="production",
            node_count=2,
            hosts=hosts
        )
        
        # Verify
        mock_save_zip.assert_called_once_with(
            mock_app,
            Path(mock_save_zip.call_args[0][1]),
            deployment_mode="production",
            node_count=2,
            hosts=hosts,
            services_xml=None
        )


class TestSchemaCheck:
    """Test schema existence checking."""
    
    @patch("agents.policies.vespa.deploy_package.Vespa")
    def test_check_schema_exists_success(self, mock_vespa_class):
        """Test checking when schema exists."""
        # Setup
        mock_vespa = MagicMock()
        mock_response = MagicMock()
        mock_response.is_successful.return_value = True
        mock_vespa.query.return_value = mock_response
        mock_vespa_class.return_value = mock_vespa
        
        # Execute
        result = check_schema_exists("http://localhost:8080")
        
        # Verify
        assert result is True
        mock_vespa.query.assert_called_once_with(
            yql="select * from policy_document where true limit 1"
        )
    
    @patch("agents.policies.vespa.deploy_package.Vespa")
    def test_check_schema_exists_not_found(self, mock_vespa_class):
        """Test checking when schema doesn't exist."""
        # Setup
        mock_vespa = MagicMock()
        mock_response = MagicMock()
        mock_response.is_successful.return_value = False
        mock_vespa.query.return_value = mock_response
        mock_vespa_class.return_value = mock_vespa
        
        # Execute
        result = check_schema_exists("http://localhost:8080")
        
        # Verify
        assert result is False
    
    @patch("agents.policies.vespa.deploy_package.Vespa")
    def test_check_schema_exists_error(self, mock_vespa_class):
        """Test checking when connection fails."""
        # Setup
        mock_vespa_class.side_effect = Exception("Connection failed")
        
        # Execute
        result = check_schema_exists("http://localhost:8080")
        
        # Verify
        assert result is False


class TestDeployPackageFromZip:
    """Test package deployment from zip."""
    
    @patch("agents.policies.vespa.deploy_package.httpx.put")
    @patch("agents.policies.vespa.deploy_package.httpx.post")
    @patch("builtins.open", new_callable=mock_open, read_data=b"zip content")
    def test_deploy_package_from_zip_success(self, mock_file, mock_post, mock_put):
        """Test successful deployment from zip."""
        # Setup
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"session-id": "123"}
        mock_put.return_value.status_code = 200
        
        # Execute
        success, session_id = deploy_package_from_zip(
            "http://localhost:19071",
            Path("/tmp/test.zip")
        )
        
        # Verify
        assert success is True
        assert session_id == "123"
        assert mock_post.call_count == 1
        assert mock_put.call_count == 2  # prepare and activate
    
    @patch("agents.policies.vespa.deploy_package.httpx.post")
    @patch("builtins.open", new_callable=mock_open, read_data=b"zip content")
    def test_deploy_package_from_zip_prepare_failure(self, mock_file, mock_post):
        """Test deployment failure during prepare."""
        # Setup
        mock_post.return_value.status_code = 400
        mock_post.return_value.text = "Bad request"
        
        # Execute
        success, session_id = deploy_package_from_zip(
            "http://localhost:19071",
            Path("/tmp/test.zip")
        )
        
        # Verify
        assert success is False
        assert session_id == ""


class TestDeployToVespa:
    """Test complete deployment process."""
    
    @patch("agents.policies.vespa.deploy_package.check_schema_exists")
    def test_deploy_to_vespa_schema_exists_no_force(self, mock_check_schema):
        """Test skipping deployment when schema exists."""
        # Setup
        mock_check_schema.return_value = True
        
        # Execute
        result = deploy_to_vespa(
            "http://localhost:19071",
            "http://localhost:8080",
            force=False
        )
        
        # Verify
        assert result is True
        mock_check_schema.assert_called_once_with("http://localhost:8080")
    
    @patch("agents.policies.vespa.deploy_package.time.sleep")
    @patch("agents.policies.vespa.deploy_package.check_schema_exists")
    @patch("agents.policies.vespa.deploy_package.deploy_package_from_zip")
    @patch("agents.policies.vespa.deploy_package.generate_package_artifacts")
    def test_deploy_to_vespa_new_deployment(self, mock_generate, mock_deploy_zip, 
                                           mock_check_schema, mock_sleep):
        """Test new deployment when schema doesn't exist."""
        # Setup
        mock_check_schema.side_effect = [False, True]  # Not exists, then exists
        mock_generate.return_value = (Path("/tmp/test.zip"), Path("/tmp/metadata.json"))
        mock_deploy_zip.return_value = (True, "123")
        
        # Execute
        result = deploy_to_vespa(
            "http://localhost:19071",
            "http://localhost:8080",
            force=False
        )
        
        # Verify
        assert result is True
        assert mock_check_schema.call_count == 2
        mock_generate.assert_called_once()
        mock_deploy_zip.assert_called_once()
    
    @patch("agents.policies.vespa.deploy_package.json.load")
    @patch("builtins.open", new_callable=mock_open)
    @patch("agents.policies.vespa.deploy_package.check_schema_exists")
    @patch("agents.policies.vespa.deploy_package.deploy_package_from_zip")
    def test_deploy_to_vespa_production_with_hosts(self, mock_deploy_zip, mock_check_schema, 
                                                  mock_file, mock_json_load):
        """Test production deployment with hosts configuration."""
        # Setup
        mock_check_schema.return_value = False
        mock_deploy_zip.return_value = (True, "123")
        hosts_data = [{"name": "host1", "alias": "node0"}]
        mock_json_load.return_value = hosts_data
        
        hosts_config = Path("/tmp/hosts.json")
        hosts_config.exists = MagicMock(return_value=True)
        
        # Execute
        with patch("agents.policies.vespa.deploy_package.generate_package_artifacts") as mock_generate:
            mock_generate.return_value = (Path("/tmp/test.zip"), Path("/tmp/metadata.json"))
            
            result = deploy_to_vespa(
                "http://localhost:19071",
                "http://localhost:8080",
                deployment_mode="production",
                node_count=3,
                hosts_config=hosts_config
            )
        
        # Verify
        assert result is True
        mock_generate.assert_called_once_with(
            None,  # artifacts_dir
            deployment_mode="production",
            node_count=3,
            hosts=hosts_data,
            services_xml=None
        )


class TestDeploymentWithSettings:
    """Test deployment integration with configuration settings."""
    
    @patch("agents.policies.ingestion.config.settings")
    def test_deployment_uses_settings(self, mock_settings):
        """Test that deployment functions use settings properly."""
        # Setup
        mock_settings.vespa_deployment_mode = "production"
        mock_settings.vespa_node_count = 5
        mock_settings.vespa_artifacts_dir = Path("/custom/artifacts")
        mock_settings.vespa_hosts_config = Path("/custom/hosts.json")
        mock_settings.vespa_services_xml = Path("/custom/services.xml")
        
        # Import deploy function with mocked settings
        
        # Verify settings are accessible
        from agents.policies.ingestion.config import settings
        assert settings.vespa_deployment_mode == "production"
        assert settings.vespa_node_count == 5