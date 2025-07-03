"""Tests for embedding generation with configuration integration."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from agents.policies.agent.services.embeddings import (
    combine_text_for_embedding,
    generate_embedding,
    generate_embeddings_batch,
    get_embedding_model,
)


class TestEmbeddingModel:
    """Test embedding model initialization and singleton pattern."""
    
    def setup_method(self):
        """Reset global model before each test."""
        # Mock resetting the global model
        with patch("agents.policies.agent.services.embeddings._EMBEDDING_MODEL", None):
            pass
    
    @patch("agents.policies.agent.services.embeddings.settings")
    @patch("agents.policies.agent.services.embeddings.SentenceTransformer")
    def test_get_embedding_model_initialization(self, mock_transformer, mock_settings):
        """Test model initialization with settings."""
        # Setup
        mock_settings.embedding_model = "test-model"
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_transformer.return_value = mock_model
        
        # Execute
        model = get_embedding_model()
        
        # Verify
        mock_transformer.assert_called_once_with("test-model")
        assert model == mock_model
        assert model.get_sentence_embedding_dimension.called
    
    @patch("agents.policies.agent.services.embeddings.settings")
    @patch("agents.policies.agent.services.embeddings.SentenceTransformer")
    def test_get_embedding_model_singleton(self, mock_transformer, mock_settings):
        """Test that model is initialized only once."""
        # Setup
        mock_settings.embedding_model = "test-model"
        mock_model = MagicMock()
        mock_transformer.return_value = mock_model
        
        # Execute
        model1 = get_embedding_model()
        model2 = get_embedding_model()
        
        # Verify
        assert model1 is model2
        mock_transformer.assert_called_once()  # Only called once
    
    @patch("agents.policies.agent.services.embeddings.settings")
    @patch("agents.policies.agent.services.embeddings.SentenceTransformer")
    def test_get_embedding_model_initialization_error(self, mock_transformer, mock_settings):
        """Test error handling during model initialization."""
        # Setup
        mock_settings.embedding_model = "invalid-model"
        mock_transformer.side_effect = Exception("Model not found")
        
        # Execute and verify
        with pytest.raises(Exception, match="Model not found"):
            get_embedding_model()
    
    @patch("agents.policies.agent.services.embeddings.logger")
    @patch("agents.policies.agent.services.embeddings.settings")
    @patch("agents.policies.agent.services.embeddings.SentenceTransformer")
    def test_get_embedding_model_logging(self, mock_transformer, mock_settings, mock_logger):
        """Test logging during model initialization."""
        # Setup
        mock_settings.embedding_model = "all-MiniLM-L6-v2"
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_transformer.return_value = mock_model
        
        # Execute
        get_embedding_model()
        
        # Verify logging
        mock_logger.info.assert_any_call("Initializing embedding model: all-MiniLM-L6-v2")
        mock_logger.info.assert_any_call(
            "Embedding model initialized successfully. Dimension: 384"
        )


class TestGenerateEmbedding:
    """Test single text embedding generation."""
    
    def setup_method(self):
        """Reset global model before each test."""
        # Mock resetting the global model
        with patch("agents.policies.agent.services.embeddings._EMBEDDING_MODEL", None):
            pass
    
    @patch("agents.policies.agent.services.embeddings.get_embedding_model")
    def test_generate_embedding_valid_text(self, mock_get_model):
        """Test embedding generation for valid text."""
        # Setup
        mock_model = MagicMock()
        mock_embedding = np.array([0.1, 0.2, 0.3])
        mock_model.encode.return_value = mock_embedding
        mock_get_model.return_value = mock_model
        
        # Execute
        result = generate_embedding("test text")
        
        # Verify
        assert result == [0.1, 0.2, 0.3]
        mock_model.encode.assert_called_once_with("test text", convert_to_tensor=False)
    
    def test_generate_embedding_empty_text(self):
        """Test handling of empty text."""
        assert generate_embedding("") == []
        assert generate_embedding("   ") == []
        assert generate_embedding(None) == []
    
    @patch("agents.policies.agent.services.embeddings.logger")
    def test_generate_embedding_empty_text_logging(self, mock_logger):
        """Test logging for empty text."""
        generate_embedding("")
        mock_logger.warning.assert_called_with("Empty text provided for embedding generation")
    
    @patch("agents.policies.agent.services.embeddings.get_embedding_model")
    @patch("agents.policies.agent.services.embeddings.logger")
    def test_generate_embedding_error_handling(self, mock_logger, mock_get_model):
        """Test error handling during embedding generation."""
        # Setup
        mock_model = MagicMock()
        mock_model.encode.side_effect = Exception("Encoding error")
        mock_get_model.return_value = mock_model
        
        # Execute
        result = generate_embedding("test text")
        
        # Verify
        assert result == []
        mock_logger.error.assert_called_with("Error generating embedding: Encoding error")


class TestGenerateEmbeddingsBatch:
    """Test batch embedding generation."""
    
    def setup_method(self):
        """Reset global model before each test."""
        # Mock resetting the global model
        with patch("agents.policies.agent.services.embeddings._EMBEDDING_MODEL", None):
            pass
    
    @patch("agents.policies.agent.services.embeddings.get_embedding_model")
    def test_generate_embeddings_batch_valid_texts(self, mock_get_model):
        """Test batch embedding generation for valid texts."""
        # Setup
        mock_model = MagicMock()
        mock_embeddings = np.array([
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
            [0.7, 0.8, 0.9]
        ])
        mock_model.encode.return_value = mock_embeddings
        mock_get_model.return_value = mock_model
        
        # Execute
        texts = ["text1", "text2", "text3"]
        result = generate_embeddings_batch(texts)
        
        # Verify
        assert len(result) == 3
        assert result[0] == [0.1, 0.2, 0.3]
        assert result[1] == [0.4, 0.5, 0.6]
        assert result[2] == [0.7, 0.8, 0.9]
        mock_model.encode.assert_called_once_with(
            texts,
            batch_size=32,
            convert_to_tensor=False,
            show_progress_bar=False
        )
    
    def test_generate_embeddings_batch_empty_list(self):
        """Test handling of empty text list."""
        assert generate_embeddings_batch([]) == []
    
    @patch("agents.policies.agent.services.embeddings.get_embedding_model")
    def test_generate_embeddings_batch_mixed_valid_invalid(self, mock_get_model):
        """Test batch with mixed valid and invalid texts."""
        # Setup
        mock_model = MagicMock()
        # Only 2 valid texts will be encoded
        mock_embeddings = np.array([
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6]
        ])
        mock_model.encode.return_value = mock_embeddings
        mock_get_model.return_value = mock_model
        
        # Execute
        texts = ["valid1", "", "valid2", "   ", None]
        result = generate_embeddings_batch(texts)
        
        # Verify
        assert len(result) == 5
        assert result[0] == [0.1, 0.2, 0.3]  # valid1
        assert result[1] == []  # empty
        assert result[2] == [0.4, 0.5, 0.6]  # valid2
        assert result[3] == []  # whitespace
        assert result[4] == []  # None
        
        # Only valid texts should be encoded
        mock_model.encode.assert_called_once_with(
            ["valid1", "valid2"],
            batch_size=32,
            convert_to_tensor=False,
            show_progress_bar=False
        )
    
    @patch("agents.policies.agent.services.embeddings.get_embedding_model")
    def test_generate_embeddings_batch_custom_batch_size(self, mock_get_model):
        """Test custom batch size parameter."""
        # Setup
        mock_model = MagicMock()
        mock_embeddings = np.array([[0.1, 0.2, 0.3]])
        mock_model.encode.return_value = mock_embeddings
        mock_get_model.return_value = mock_model
        
        # Execute
        result = generate_embeddings_batch(["text"], batch_size=16)
        
        # Verify
        mock_model.encode.assert_called_once_with(
            ["text"],
            batch_size=16,
            convert_to_tensor=False,
            show_progress_bar=False
        )
    
    @patch("agents.policies.agent.services.embeddings.get_embedding_model")
    def test_generate_embeddings_batch_progress_bar(self, mock_get_model):
        """Test progress bar display for large batches."""
        # Setup
        mock_model = MagicMock()
        large_batch = ["text"] * 101  # More than 100
        mock_embeddings = np.array([[0.1, 0.2, 0.3]] * 101)
        mock_model.encode.return_value = mock_embeddings
        mock_get_model.return_value = mock_model
        
        # Execute
        result = generate_embeddings_batch(large_batch)
        
        # Verify progress bar enabled
        mock_model.encode.assert_called_once_with(
            large_batch,
            batch_size=32,
            convert_to_tensor=False,
            show_progress_bar=True  # Should be True for >100 texts
        )
    
    @patch("agents.policies.agent.services.embeddings.logger")
    def test_generate_embeddings_batch_all_invalid(self, mock_logger):
        """Test batch with all invalid texts."""
        texts = ["", "   ", None]
        result = generate_embeddings_batch(texts)
        
        assert result == [[], [], []]
        mock_logger.warning.assert_called_with("No valid texts to embed")
    
    @patch("agents.policies.agent.services.embeddings.get_embedding_model")
    @patch("agents.policies.agent.services.embeddings.logger")
    def test_generate_embeddings_batch_error_handling(self, mock_logger, mock_get_model):
        """Test error handling in batch generation."""
        # Setup
        mock_model = MagicMock()
        mock_model.encode.side_effect = Exception("Batch encoding error")
        mock_get_model.return_value = mock_model
        
        # Execute
        result = generate_embeddings_batch(["text1", "text2"])
        
        # Verify
        assert result == [[], []]
        mock_logger.error.assert_called_with(
            "Error generating batch embeddings: Batch encoding error"
        )


class TestCombineTextForEmbedding:
    """Test text combination for richer embeddings."""
    
    def test_combine_all_fields(self):
        """Test combination with all fields provided."""
        result = combine_text_for_embedding(
            text="Main content",
            title="Document Title",
            headings=["Section 1", "Section 2"],
            category="auto"
        )
        
        expected = "Category: auto Title: Document Title Sections: Section 1 > Section 2 Main content"
        assert result == expected
    
    def test_combine_partial_fields(self):
        """Test combination with partial fields."""
        # Only text
        result = combine_text_for_embedding(text="Main content")
        assert result == "Main content"
        
        # Text and category
        result = combine_text_for_embedding(text="Main content", category="home")
        assert result == "Category: home Main content"
        
        # Text and title
        result = combine_text_for_embedding(text="Main content", title="Title")
        assert result == "Title: Title Main content"
        
        # Text and headings
        result = combine_text_for_embedding(
            text="Main content",
            headings=["H1", "H2"]
        )
        assert result == "Sections: H1 > H2 Main content"
    
    def test_combine_empty_fields(self):
        """Test handling of empty fields."""
        result = combine_text_for_embedding(
            text="Main content",
            title="",
            headings=[],
            category=None
        )
        assert result == "Main content"
    
    def test_combine_order(self):
        """Test that fields are combined in correct order."""
        result = combine_text_for_embedding(
            text="4",
            title="2",
            headings=["3"],
            category="1"
        )
        # Order should be: category, title, headings, text
        assert result.index("1") < result.index("2")
        assert result.index("2") < result.index("3")
        assert result.index("3") < result.index("4")


class TestEmbeddingIntegration:
    """Test integration of embedding functions."""
    
    def setup_method(self):
        """Reset global model before each test."""
        # Mock resetting the global model
        with patch("agents.policies.agent.services.embeddings._EMBEDDING_MODEL", None):
            pass
    
    @patch("agents.policies.agent.services.embeddings.settings")
    @patch("agents.policies.agent.services.embeddings.SentenceTransformer")
    def test_end_to_end_embedding_generation(self, mock_transformer, mock_settings):
        """Test complete flow from settings to embedding."""
        # Setup
        mock_settings.embedding_model = "sentence-transformers/all-MiniLM-L6-v2"
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = np.array([0.1, 0.2, 0.3])
        mock_transformer.return_value = mock_model
        
        # Execute
        text = combine_text_for_embedding(
            text="Insurance policy details",
            category="auto",
            title="Auto Insurance"
        )
        embedding = generate_embedding(text)
        
        # Verify
        assert text == "Category: auto Title: Auto Insurance Insurance policy details"
        assert embedding == [0.1, 0.2, 0.3]
        mock_model.encode.assert_called_with(text, convert_to_tensor=False)
    
    @patch("agents.policies.agent.services.embeddings.settings")
    @patch("agents.policies.agent.services.embeddings.SentenceTransformer")
    def test_batch_embedding_with_combined_text(self, mock_transformer, mock_settings):
        """Test batch embedding with combined text features."""
        # Setup
        mock_settings.embedding_model = "all-MiniLM-L6-v2"
        mock_model = MagicMock()
        mock_embeddings = np.array([
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6]
        ])
        mock_model.encode.return_value = mock_embeddings
        mock_transformer.return_value = mock_model
        
        # Create combined texts
        texts = [
            combine_text_for_embedding("Policy 1", title="Auto", category="auto"),
            combine_text_for_embedding("Policy 2", title="Home", category="home")
        ]
        
        # Execute
        embeddings = generate_embeddings_batch(texts)
        
        # Verify
        assert len(embeddings) == 2
        assert embeddings[0] == [0.1, 0.2, 0.3]
        assert embeddings[1] == [0.4, 0.5, 0.6]


class TestEmbeddingModelConfiguration:
    """Test embedding model configuration with settings."""
    
    def setup_method(self):
        """Reset global model before each test."""
        # Mock resetting the global model
        with patch("agents.policies.agent.services.embeddings._EMBEDDING_MODEL", None):
            pass
    
    @patch("agents.policies.agent.services.embeddings.settings")
    @patch("agents.policies.agent.services.embeddings.SentenceTransformer")
    def test_custom_model_from_settings(self, mock_transformer, mock_settings):
        """Test loading custom model from settings."""
        # Setup
        mock_settings.embedding_model = "sentence-transformers/all-mpnet-base-v2"
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 768
        mock_transformer.return_value = mock_model
        
        # Execute
        model = get_embedding_model()
        
        # Verify
        mock_transformer.assert_called_once_with("sentence-transformers/all-mpnet-base-v2")
        assert model == mock_model
    
    @patch("agents.policies.agent.services.embeddings.settings")
    def test_settings_integration(self, mock_settings):
        """Test that settings are properly used throughout the module."""
        # Setup
        mock_settings.embedding_model = "test-model"
        
        # Import should use settings
        from agents.policies.agent.services.embeddings import (
            settings as imported_settings,
        )
        
        # Verify
        assert imported_settings == mock_settings