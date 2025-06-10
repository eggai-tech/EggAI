"""Policy Documentation Agent - A modular RAG-based system for policy information retrieval."""

from agents.policy_documentation_agent.agent import policy_documentation_agent
from agents.policy_documentation_agent.components.retrieval_agent import retrieval_agent
from agents.policy_documentation_agent.components.augmenting_agent import augmenting_agent
from agents.policy_documentation_agent.components.generation_agent import generation_agent
from agents.policy_documentation_agent.config import settings
from agents.policy_documentation_agent.types import (
    PolicyCategory,
    DocumentationRequestType,
    ComponentStatus,
    ChatMessage,
    RetrievedDocument,
    ModelConfig,
)

__version__ = "1.0.0"

__all__ = [
    "policy_documentation_agent",
    "retrieval_agent", 
    "augmenting_agent",
    "generation_agent",
    "settings",
    "PolicyCategory",
    "DocumentationRequestType", 
    "ComponentStatus",
    "ChatMessage",
    "RetrievedDocument",
    "ModelConfig",
]