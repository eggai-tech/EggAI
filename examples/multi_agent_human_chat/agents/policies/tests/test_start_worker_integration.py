import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from agents.policies.ingestion.start_worker import (
    main,
    trigger_initial_document_ingestion,
)


class TestTriggerInitialDocumentIngestion:
    """Test initial document ingestion functionality."""
    
    @pytest.mark.asyncio
    @patch("agents.policies.ingestion.start_worker.TemporalClient")
    @patch("agents.policies.ingestion.start_worker.settings")
    async def test_trigger_initial_ingestion_success(self, mock_settings, mock_client_class):
        """Test successful ingestion of all policy documents."""
        # Setup
        mock_settings.temporal_server_url = "localhost:7233"
        mock_settings.get_temporal_namespace.return_value = "default"
        mock_settings.temporal_task_queue = "policy-rag"
        
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        
        # Mock successful results for each policy
        mock_results = []
        for _ in ["auto", "home", "health", "life"]:
            result = MagicMock()
            result.success = True
            result.skipped = False
            result.documents_processed = 1
            result.total_documents_indexed = 5
            mock_results.append(result)
        
        mock_client.ingest_document_async.side_effect = mock_results
        
        # Mock file existence
        with patch("pathlib.Path.exists", return_value=True):
            # Execute
            await trigger_initial_document_ingestion()
        
        # Verify
        assert mock_client.ingest_document_async.call_count == 4
        
        # Verify each policy was processed
        expected_calls = []
        for policy_id in ["auto", "home", "health", "life"]:
            expected_calls.append(
                call(
                    file_path=str(Path(__file__).parent.parent / "ingestion" / "documents" / f"{policy_id}.md"),
                    category=policy_id,
                    index_name="policies_index",
                    force_rebuild=False
                )
            )
        
        mock_client.ingest_document_async.assert_has_calls(expected_calls, any_order=False)
        mock_client.close.assert_called_once()
    
    @pytest.mark.asyncio
    @patch("agents.policies.ingestion.start_worker.TemporalClient")
    @patch("agents.policies.ingestion.start_worker.settings")
    async def test_trigger_initial_ingestion_with_missing_files(self, mock_settings, mock_client_class):
        """Test ingestion when some policy files are missing."""
        # Setup
        mock_settings.temporal_server_url = "localhost:7233"
        mock_settings.get_temporal_namespace.return_value = "default"
        mock_settings.temporal_task_queue = "policy-rag"
        
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        
        # Mock file existence - only auto and home exist
        def mock_exists(self):
            return self.name in ["auto.md", "home.md"]
        
        with patch.object(Path, "exists", mock_exists):
            # Mock results for existing files
            mock_results = []
            for _ in range(2):  # Only 2 files exist
                result = MagicMock()
                result.success = True
                result.skipped = False
                result.documents_processed = 1
                result.total_documents_indexed = 5
                mock_results.append(result)
            
            mock_client.ingest_document_async.side_effect = mock_results
            
            # Execute
            await trigger_initial_document_ingestion()
        
        # Verify only 2 documents were processed
        assert mock_client.ingest_document_async.call_count == 2
    
    @pytest.mark.asyncio
    @patch("agents.policies.ingestion.start_worker.TemporalClient")
    @patch("agents.policies.ingestion.start_worker.settings")
    @patch("agents.policies.ingestion.start_worker.logger")
    async def test_trigger_initial_ingestion_with_skipped(self, mock_logger, mock_settings, mock_client_class):
        """Test ingestion when some documents are skipped."""
        # Setup
        mock_settings.temporal_server_url = "localhost:7233"
        mock_settings.get_temporal_namespace.return_value = "default"
        mock_settings.temporal_task_queue = "policy-rag"
        
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        
        # Mock results with one skipped
        result1 = MagicMock()
        result1.success = True
        result1.skipped = True
        result1.skip_reason = "Already indexed"
        result1.documents_processed = 0
        result1.total_documents_indexed = 0
        
        result2 = MagicMock()
        result2.success = True
        result2.skipped = False
        result2.documents_processed = 1
        result2.total_documents_indexed = 5
        
        mock_client.ingest_document_async.side_effect = [result1, result2]
        
        # Mock file existence for only 2 files
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.side_effect = [True, True, False, False]
            
            # Execute
            await trigger_initial_document_ingestion()
        
        # Verify skip was logged
        mock_logger.info.assert_any_call("Policy auto skipped: Already indexed")
    
    @pytest.mark.asyncio
    @patch("agents.policies.ingestion.start_worker.TemporalClient")
    @patch("agents.policies.ingestion.start_worker.settings")
    @patch("agents.policies.ingestion.start_worker.logger")
    async def test_trigger_initial_ingestion_with_failures(self, mock_logger, mock_settings, mock_client_class):
        """Test ingestion with some failures."""
        # Setup
        mock_settings.temporal_server_url = "localhost:7233"
        mock_settings.get_temporal_namespace.return_value = "default"
        mock_settings.temporal_task_queue = "policy-rag"
        
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        
        # Mock mixed results
        result1 = MagicMock()
        result1.success = False
        result1.error_message = "Processing failed"
        
        result2 = MagicMock()
        result2.success = True
        result2.skipped = False
        result2.documents_processed = 1
        result2.total_documents_indexed = 5
        
        mock_client.ingest_document_async.side_effect = [result1, result2]
        
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.side_effect = [True, True, False, False]
            
            # Execute
            await trigger_initial_document_ingestion()
        
        # Verify error was logged
        mock_logger.error.assert_any_call("Policy auto ingestion failed: Processing failed")
    
    @pytest.mark.asyncio
    @patch("agents.policies.ingestion.start_worker.TemporalClient")
    @patch("agents.policies.ingestion.start_worker.settings")
    @patch("agents.policies.ingestion.start_worker.logger")
    async def test_trigger_initial_ingestion_exception(self, mock_logger, mock_settings, mock_client_class):
        """Test handling of exceptions during ingestion."""
        # Setup
        mock_settings.temporal_server_url = "localhost:7233"
        mock_settings.get_temporal_namespace.return_value = "default"
        mock_settings.temporal_task_queue = "policy-rag"
        
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.ingest_document_async.side_effect = Exception("Connection error")
        
        with patch("pathlib.Path.exists", return_value=True):
            # Execute
            await trigger_initial_document_ingestion()
        
        # Verify error was logged
        mock_logger.error.assert_called_with(
            "Error during initial document ingestion: Connection error",
            exc_info=True
        )


class TestMainFunction:
    """Test main worker startup function."""
    
    @pytest.mark.asyncio
    @patch("agents.policies.ingestion.start_worker.trigger_initial_document_ingestion")
    @patch("agents.policies.ingestion.start_worker.deploy_to_vespa")
    @patch("agents.policies.ingestion.start_worker.run_policy_documentation_worker")
    @patch("agents.policies.ingestion.start_worker.init_telemetry")
    @patch("agents.policies.ingestion.start_worker.settings")
    async def test_main_successful_startup(self, mock_settings, mock_init_telemetry, 
                                         mock_run_worker, mock_deploy_vespa, mock_trigger_ingestion):
        """Test successful worker startup and initialization."""
        # Setup
        mock_settings.app_name = "test_worker"
        mock_settings.otel_endpoint = "http://otel:4318"
        mock_settings.temporal_server_url = "localhost:7233"
        mock_settings.get_temporal_namespace.return_value = "default"
        mock_settings.temporal_task_queue = "policy-rag"
        mock_settings.vespa_config_url = "http://vespa:19071"
        mock_settings.vespa_query_url = "http://vespa:8080"
        mock_settings.vespa_artifacts_dir = None
        mock_settings.vespa_deployment_mode = "local"
        mock_settings.vespa_node_count = 1
        mock_settings.vespa_hosts_config = None
        mock_settings.vespa_services_xml = None
        mock_settings.vespa_app_name = "policies"
        
        # Mock worker
        mock_worker = AsyncMock()
        mock_run_worker.return_value = mock_worker
        
        # Mock successful Vespa deployment
        mock_deploy_vespa.return_value = True
        
        # Mock shutdown event
        shutdown_event = asyncio.Event()
        
        with patch("asyncio.Event", return_value=shutdown_event):
            # Create a task to set the shutdown event after a short delay
            async def trigger_shutdown():
                await asyncio.sleep(0.1)
                shutdown_event.set()
            
            # Start the shutdown trigger
            shutdown_task = asyncio.create_task(trigger_shutdown())
            
            # Execute
            await main()
            
            # Clean up
            await shutdown_task
        
        # Verify initialization
        mock_init_telemetry.assert_called_once_with(
            app_name="test_worker",
            endpoint="http://otel:4318"
        )
        
        # Verify worker started
        mock_run_worker.assert_called_once()
        
        # Verify Vespa deployment
        mock_deploy_vespa.assert_called_once_with(
            config_server_url="http://vespa:19071",
            query_url="http://vespa:8080",
            force=True,
            artifacts_dir=None,
            deployment_mode="local",
            node_count=1,
            hosts_config=None,
            services_xml=None,
            app_name="policies"
        )
        
        # Verify document ingestion
        mock_trigger_ingestion.assert_called_once()
        
        # Verify worker shutdown
        mock_worker.shutdown.assert_called_once()
    
    @pytest.mark.asyncio
    @patch("agents.policies.ingestion.start_worker.sys.exit")
    @patch("agents.policies.ingestion.start_worker.deploy_to_vespa")
    @patch("agents.policies.ingestion.start_worker.run_policy_documentation_worker")
    @patch("agents.policies.ingestion.start_worker.init_telemetry")
    @patch("agents.policies.ingestion.start_worker.settings")
    @patch("agents.policies.ingestion.start_worker.logger")
    async def test_main_vespa_deployment_failure(self, mock_logger, mock_settings, 
                                                mock_init_telemetry, mock_run_worker, 
                                                mock_deploy_vespa, mock_exit):
        """Test handling of Vespa deployment failure."""
        # Setup
        mock_settings.app_name = "test_worker"
        mock_settings.otel_endpoint = "http://otel:4318"
        mock_settings.temporal_server_url = "localhost:7233"
        mock_settings.get_temporal_namespace.return_value = "default"
        mock_settings.temporal_task_queue = "policy-rag"
        mock_settings.vespa_config_url = "http://vespa:19071"
        mock_settings.vespa_query_url = "http://vespa:8080"
        mock_settings.vespa_artifacts_dir = None
        mock_settings.vespa_deployment_mode = "local"
        mock_settings.vespa_node_count = 1
        mock_settings.vespa_hosts_config = None
        mock_settings.vespa_services_xml = None
        mock_settings.vespa_app_name = "policies"
        
        # Mock worker
        mock_worker = AsyncMock()
        mock_run_worker.return_value = mock_worker
        
        # Mock failed Vespa deployment
        mock_deploy_vespa.return_value = False
        
        # Execute
        await main()
        
        # Verify error handling
        mock_logger.error.assert_any_call(
            "Vespa schema deployment failed - cannot proceed with document ingestion"
        )
        mock_logger.error.assert_any_call(
            "Please check Vespa container status and try again"
        )
        mock_exit.assert_called_once_with(1)
    
    @pytest.mark.asyncio
    @patch("agents.policies.ingestion.start_worker.sys.exit")
    @patch("agents.policies.ingestion.start_worker.run_policy_documentation_worker")
    @patch("agents.policies.ingestion.start_worker.init_telemetry")
    @patch("agents.policies.ingestion.start_worker.settings")
    @patch("agents.policies.ingestion.start_worker.logger")
    async def test_main_worker_startup_failure(self, mock_logger, mock_settings, 
                                              mock_init_telemetry, mock_run_worker, mock_exit):
        """Test handling of worker startup failure."""
        # Setup
        mock_settings.app_name = "test_worker"
        mock_settings.otel_endpoint = "http://otel:4318"
        mock_settings.temporal_server_url = "localhost:7233"
        mock_settings.get_temporal_namespace.return_value = "default"
        mock_settings.temporal_task_queue = "policy-rag"
        
        # Mock worker startup failure
        mock_run_worker.side_effect = Exception("Worker startup failed")
        
        # Execute
        await main()
        
        # Verify error handling
        mock_logger.error.assert_called_with(
            "Error running Policy Documentation worker: Worker startup failed",
            exc_info=True
        )
        mock_exit.assert_called_once_with(1)
    
    @pytest.mark.asyncio
    @patch("agents.policies.ingestion.start_worker.trigger_initial_document_ingestion")
    @patch("agents.policies.ingestion.start_worker.deploy_to_vespa")
    @patch("agents.policies.ingestion.start_worker.run_policy_documentation_worker")
    @patch("agents.policies.ingestion.start_worker.init_telemetry")
    @patch("agents.policies.ingestion.start_worker.settings")
    async def test_main_keyboard_interrupt(self, mock_settings, mock_init_telemetry, 
                                          mock_run_worker, mock_deploy_vespa, mock_trigger_ingestion):
        """Test handling of keyboard interrupt."""
        # Setup
        mock_settings.app_name = "test_worker"
        mock_settings.otel_endpoint = "http://otel:4318"
        mock_settings.temporal_server_url = "localhost:7233"
        mock_settings.get_temporal_namespace.return_value = "default"
        mock_settings.temporal_task_queue = "policy-rag"
        mock_settings.vespa_config_url = "http://vespa:19071"
        mock_settings.vespa_query_url = "http://vespa:8080"
        mock_settings.vespa_artifacts_dir = None
        mock_settings.vespa_deployment_mode = "local"
        mock_settings.vespa_node_count = 1
        mock_settings.vespa_hosts_config = None
        mock_settings.vespa_services_xml = None
        mock_settings.vespa_app_name = "policies"
        
        # Mock worker
        mock_worker = AsyncMock()
        mock_run_worker.return_value = mock_worker
        
        # Mock successful Vespa deployment
        mock_deploy_vespa.return_value = True
        
        # Mock shutdown event that raises KeyboardInterrupt
        shutdown_event = AsyncMock()
        shutdown_event.wait.side_effect = KeyboardInterrupt()
        
        with patch("asyncio.Event", return_value=shutdown_event):
            # Execute
            await main()
        
        # Verify worker shutdown was called
        mock_worker.shutdown.assert_called_once()


class TestSettingsIntegration:
    """Test integration with configuration settings."""
    
    @pytest.mark.asyncio
    @patch("agents.policies.ingestion.start_worker.trigger_initial_document_ingestion")
    @patch("agents.policies.ingestion.start_worker.deploy_to_vespa")
    @patch("agents.policies.ingestion.start_worker.run_policy_documentation_worker")
    @patch("agents.policies.ingestion.start_worker.init_telemetry")
    @patch("agents.policies.ingestion.start_worker.settings")
    async def test_main_uses_custom_settings(self, mock_settings, mock_init_telemetry, 
                                           mock_run_worker, mock_deploy_vespa, mock_trigger_ingestion):
        """Test that main function uses custom settings properly."""
        # Setup custom settings
        mock_settings.app_name = "custom_worker"
        mock_settings.otel_endpoint = "http://custom-otel:4318"
        mock_settings.temporal_server_url = "custom-temporal:7233"
        mock_settings.get_temporal_namespace.return_value = "custom-namespace"
        mock_settings.temporal_task_queue = "custom-queue"
        mock_settings.vespa_config_url = "http://custom-vespa:19071"
        mock_settings.vespa_query_url = "http://custom-vespa:8080"
        mock_settings.vespa_artifacts_dir = Path("/custom/artifacts")
        mock_settings.vespa_deployment_mode = "production"
        mock_settings.vespa_node_count = 3
        mock_settings.vespa_hosts_config = Path("/custom/hosts.json")
        mock_settings.vespa_services_xml = Path("/custom/services.xml")
        mock_settings.vespa_app_name = "policies"
        
        # Mock worker
        mock_worker = AsyncMock()
        mock_run_worker.return_value = mock_worker
        
        # Mock successful Vespa deployment
        mock_deploy_vespa.return_value = True
        
        # Mock shutdown event
        shutdown_event = asyncio.Event()
        
        with patch("asyncio.Event", return_value=shutdown_event):
            # Create a task to set the shutdown event after a short delay
            async def trigger_shutdown():
                await asyncio.sleep(0.1)
                shutdown_event.set()
            
            # Start the shutdown trigger
            shutdown_task = asyncio.create_task(trigger_shutdown())
            
            # Execute
            await main()
            
            # Clean up
            await shutdown_task
        
        # Verify custom settings were used
        mock_init_telemetry.assert_called_once_with(
            app_name="custom_worker",
            endpoint="http://custom-otel:4318"
        )
        
        mock_deploy_vespa.assert_called_once_with(
            config_server_url="http://custom-vespa:19071",
            query_url="http://custom-vespa:8080",
            force=True,
            artifacts_dir=Path("/custom/artifacts"),
            deployment_mode="production",
            node_count=3,
            hosts_config=Path("/custom/hosts.json"),
            services_xml=Path("/custom/services.xml"),
            app_name="policies"
        )
    
    @pytest.mark.asyncio
    @patch("agents.policies.ingestion.start_worker.TemporalClient")
    @patch("agents.policies.ingestion.start_worker.settings")
    async def test_trigger_ingestion_uses_settings(self, mock_settings, mock_client_class):
        """Test that trigger_initial_document_ingestion uses settings."""
        # Setup
        mock_settings.temporal_server_url = "custom:7233"
        mock_settings.get_temporal_namespace.return_value = "custom-ns"
        mock_settings.temporal_task_queue = "custom-queue"
        
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        
        # Mock file doesn't exist to avoid actual processing
        with patch("pathlib.Path.exists", return_value=False):
            # Execute
            await trigger_initial_document_ingestion()
        
        # Verify client was created with settings
        mock_client_class.assert_called_once_with(
            temporal_server_url="custom:7233",
            temporal_namespace="custom-ns",
            temporal_task_queue="custom-queue"
        )