"""Vespa document schemas and data models."""

from typing import Any, Dict

from pydantic import BaseModel, Field


class PolicyDocument(BaseModel):
    """Document model for policy documents in Vespa."""
    
    id: str = Field(..., description="Unique document identifier")
    title: str = Field(..., description="Document title")
    text: str = Field(..., description="Document content")
    category: str = Field(..., description="Policy category (auto, home, life, health)")
    chunk_index: int = Field(..., description="Chunk index within the document")
    source_file: str = Field(..., description="Original source file name")
    
    def to_vespa_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for Vespa indexing."""
        return {
            "id": self.id,
            "title": self.title,
            "text": self.text,
            "category": self.category,
            "chunk_index": self.chunk_index,
            "source_file": self.source_file
        }

