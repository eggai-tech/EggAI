from typing import Optional, Any

import torch
from sentence_transformers import SentenceTransformer
from torch import nn


class GatedAttentionPooling(nn.Module):
    """
    Attention Pooling layer with Sigmoid Gating.

    This layer computes attention weights for the input tensor.

    Args:
        input_dim: Dimension of the input tensor.
        hidden_dim: Dimension of the hidden layer.
        attention_heads: Number of attention heads.
        dropout: Dropout rate for the hidden layer. If None, no dropout is applied.
    """

    def __init__(
            self,
            input_dim: int = 256,
            hidden_dim: int = 128,
            attention_heads: int = 1,
            dropout: Optional[float] = None
    ):
        super(GatedAttentionPooling, self).__init__()
        self.attention_v = [
            nn.Linear(input_dim, hidden_dim),
            nn.Tanh()
        ]

        self.attention_u = [
            nn.Linear(input_dim, hidden_dim),
            nn.Sigmoid()
        ]

        if dropout is not None:
            assert 0 < dropout < 1, "Dropout must be between 0 and 1"
            self.attention_u.append(nn.Dropout(dropout))
            self.attention_v.append(nn.Dropout(dropout))

        self.attention_v = nn.Sequential(*self.attention_v)
        self.attention_u = nn.Sequential(*self.attention_u)
        self.attention_w = nn.Linear(hidden_dim, attention_heads)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Compute the attention weights for the given input x.

        Args:
            x: Input tensor of shape (N, input_dim) where is the batch size

        Returns:
            a tuple of attention weights of shape (N, attention_heads) and the input tensor of shape (N, input_dim)
        """
        # Compute the attention weights
        v = self.attention_v(x)  # N x hidden_dim
        u = self.attention_u(x)  # N x hidden_dim

        # Compute the attention scores
        A = v.mul(u)  # Element-wise multiplication
        A = self.attention_w(A)  # N x attention_heads
        # apply softmax to get attention weights
        A = nn.functional.softmax(A, dim=0)  # N x attention_heads

        return A, x


class AttentionBasedClassifier(nn.Module):
    """
    A simple neural network for classifying a chat history based on SentenceTransformer embeddings.
    The model consist of a simple feedforward neural network to project the input embeddings
    to `hidden_dim` dimensions, followed by an attention based pooling layer to aggregate the embeddings.
    Attention weights are learned and during inference can be used to investigate which input vectors
    are most important for the classification.

    Args:
        embedding_dim: Dimension of the input embeddings.
        hidden_dims: Dimensions of the hidden layers.
        n_classes: Number of classes for classification.
        dropout: Dropout rate for the hidden layers. If None, no dropout is applied.
        attention_heads: Number of attention heads.
    """

    def __init__(
            self,
            embedding_dim: int = 384,
            hidden_dims: tuple[int, int] = (256, 128),
            n_classes: int = 5,
            dropout: Optional[float] = None,
            attention_heads: int = 1
    ):
        super(AttentionBasedClassifier, self).__init__()

        # non-linear projection of the SentenceTransformer embeddings to hidden_dims
        attention_network = [
            nn.Linear(embedding_dim, hidden_dims[0]),
            nn.ReLU()
        ]

        # add dropout if specified
        if dropout is not None:
            assert 0 < dropout < 1, "Dropout must be between 0 and 1"
            attention_network.append(nn.Dropout(dropout))

        # add attention pooling
        gated_attention_pooling = GatedAttentionPooling(
            input_dim=hidden_dims[0],
            hidden_dim=hidden_dims[1],
            attention_heads=attention_heads,
            dropout=dropout
        )
        attention_network.append(gated_attention_pooling)
        self.attention_network = nn.Sequential(*attention_network)
        # add classification layer which returns the logits
        self.classification_layer = nn.Linear(hidden_dims[0] * attention_heads, n_classes)

    def forward(
            self,
            x: torch.Tensor,
            return_attention_weights: bool = False
    ) -> Any:
        """
        Forward pass through the model.

        Args:
            x: Input tensor of shape (N, embedding_dim) where N is the batch size.
            return_attention_weights: If True, return the attention weights and attention pooled representation.

        Returns:
            Returns the logits of shape (1, n_classes) if return_attention_weights is False.
            If return_attention_weights is True, returns a tuple of:
                logits (1, n_classes),
                attention_weights (attention_heads x N),
                attention_pooled_representation (attention_heads x hidden_dim)
        """
        # pass the embeddings through the attention network to get the attention weights and the hidden states
        A, h = self.attention_network(x)
        # transpose the attention weights to get the shape attention_heads x N
        A = torch.transpose(A, 1, 0)
        # compute attention pooled representation
        z = torch.mm(A, h)  # attention_heads x hidden_dim
        # convert z to 1 x (attention_heads * hidden_dim)
        z_flat = z.view(1, -1)
        # pass the output through the classification layer
        logits = self.classification_layer(z_flat)  # 1 x n_classes
        if return_attention_weights:
            # return the attention weights and the logits
            return logits, A, z
        # return the logits
        return logits


class AttentionBasedClassifierWrapper(nn.Module):
    """
    A wrapper for the AttentionBasedClassifier model containing the SentenceTransformer backbone.
    It passes the input chat history through the SentenceTransformer model to get the embeddings,
    and then passes the embeddings through the AttentionBasedClassifier model to get the final class probabilities.

    Args:
        attention_net: AttentionBasedClassifier model.
        st_model_name: Name of the SentenceTransformer model to use.
        device: Device to use for the SentenceTransformer model. If None, it will use "cuda" if available, else "cpu".

    """

    def __init__(
            self,
            attention_net: AttentionBasedClassifier,
            st_model_name: str = "all-MiniLM-L12-v2",
            device: Optional[str] = None
    ):
        super(AttentionBasedClassifierWrapper, self).__init__()
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.attention_net = attention_net.to(device)
        self.sentence_transformer = SentenceTransformer(st_model_name, device=device)
        # freeze the SentenceTransformer model, so that it does not get updated during training
        for param in self.sentence_transformer.parameters():
            param.requires_grad = False

    def forward(self, chat_history: list[str], return_attention_weights: bool = False) -> torch.Tensor:
        """
        Forward pass through the model.

        Args:
            chat_history: List of chat messages. Each message is a string.
            return_attention_weights: If True, return the attention weights and attention pooled representation.

        Returns:
            logits tensor of shape (1, n_classes)
            If return_attention_weights is True, returns a tuple of:
                logits (1, n_classes),
                attention_weights (attention_heads x N),
                attention_pooled_representation (attention_heads x hidden_dim)
        """
        # get the SentenceTransformer embeddings
        x = self.sentence_transformer.encode(chat_history, convert_to_tensor=True, show_progress_bar=False)
        # pass the embeddings through the attention network
        return self.attention_net(x, return_attention_weights)

    def predict_probab(self, chat_history: list[str], return_logits: bool = False) -> Any:
        """
        Predict the class probabilities for the given chat history.

        Args:
            chat_history: List of chat messages. Each message is a string.
            return_logits: If True, return logits, the attention weights and attention pooled representation.

        Returns:
            Class probabilities tensor of shape (1, n_classes)
            If return_logits is True, returns a tuple of:
                probs (1, n_classes),
                logits (1, n_classes),
                attention_weights (attention_heads x N),
                attention_pooled_representation (attention_heads x hidden_dim)
        """
        with torch.no_grad():
            outputs = self.forward(chat_history, return_attention_weights=return_logits)
            if return_logits:
                logits, attention_weights, attention_pooled_representation = outputs
            else:
                logits = outputs
            probs = nn.functional.softmax(logits, dim=1)

        if return_logits:
            return probs, logits, attention_weights, attention_pooled_representation
        return probs
