"""Knowledge Base Agent - A modular RAG-based system for policy information retrieval."""

from agents.knowledge_base_agent.agent import policy_documentation_agent
from agents.knowledge_base_agent.components.augmenting_agent import (
    augmenting_agent,
)
from agents.knowledge_base_agent.components.generation_agent import (
    generation_agent,
)
from agents.knowledge_base_agent.components.retrieval_agent import retrieval_agent
from agents.knowledge_base_agent.config import settings
from agents.knowledge_base_agent.types import (
    ChatMessage,
    ComponentStatus,
    DocumentationRequestType,
    ModelConfig,
    PolicyCategory,
    RetrievedDocument,
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
