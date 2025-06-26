"""Vespa document schemas and data models."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PolicyDocument(BaseModel):
    """Enhanced document model for policy documents in Vespa."""

    # Core fields
    id: str = Field(..., description="Unique document identifier")
    title: str = Field(..., description="Document title")
    text: str = Field(..., description="Document content")
    category: str = Field(..., description="Policy category (auto, home, life, health)")
    chunk_index: int = Field(..., description="Chunk index within the document")
    source_file: str = Field(..., description="Original source file name")

    # Enhanced metadata fields
    page_numbers: List[int] = Field(
        default_factory=list, description="List of page numbers this chunk spans"
    )
    page_range: Optional[str] = Field(
        None, description="Page range as string (e.g., '1-3')"
    )
    headings: List[str] = Field(
        default_factory=list, description="Section headings hierarchy"
    )
    char_count: int = Field(0, description="Character count of the chunk")
    token_count: int = Field(0, description="Token count of the chunk")

    # Relationship fields
    document_id: str = Field(..., description="Parent document identifier")
    previous_chunk_id: Optional[str] = Field(
        None, description="ID of the previous chunk"
    )
    next_chunk_id: Optional[str] = Field(None, description="ID of the next chunk")
    chunk_position: float = Field(
        0.0, description="Relative position in document (0.0-1.0)"
    )

    # Additional context
    section_path: List[str] = Field(
        default_factory=list, description="Path of sections/subsections"
    )

    # Vector embedding for semantic search
    embedding: Optional[List[float]] = Field(None, description="Text embedding vector")

    def to_vespa_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for Vespa indexing."""
        data = {
            "id": self.id,
            "title": self.title,
            "text": self.text,
            "category": self.category,
            "chunk_index": self.chunk_index,
            "source_file": self.source_file,
            "page_numbers": self.page_numbers,
            "page_range": self.page_range,
            "headings": self.headings,
            "char_count": self.char_count,
            "token_count": self.token_count,
            "document_id": self.document_id,
            "previous_chunk_id": self.previous_chunk_id,
            "next_chunk_id": self.next_chunk_id,
            "chunk_position": self.chunk_position,
            "section_path": self.section_path,
        }

        # Convert embedding to Vespa tensor format if present
        if self.embedding:
            data["embedding"] = {
                "cells": [
                    {"address": {"x": str(i)}, "value": float(v)}
                    for i, v in enumerate(self.embedding)
                ]
            }

        return data


class DocumentMetadata(BaseModel):
    """Document-level metadata for tracking whole documents."""

    id: str = Field(..., description="Unique document identifier")
    file_path: str = Field(..., description="Full path to the source file")
    file_name: str = Field(..., description="Original file name")
    category: str = Field(..., description="Policy category")

    # Document statistics
    total_pages: int = Field(0, description="Total number of pages")
    total_chunks: int = Field(0, description="Total number of chunks")
    total_characters: int = Field(0, description="Total character count")
    total_tokens: int = Field(0, description="Total token count")

    # Metadata
    document_type: str = Field("pdf", description="Document type (pdf, docx, etc.)")
    file_size: int = Field(0, description="File size in bytes")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Ingestion timestamp"
    )
    last_modified: Optional[datetime] = Field(
        None, description="Document last modified time"
    )

    # Document structure
    outline: List[Dict[str, Any]] = Field(
        default_factory=list, description="Document outline/TOC"
    )
    key_sections: List[str] = Field(
        default_factory=list, description="Important section identifiers"
    )

    def to_vespa_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for Vespa indexing."""
        return {
            "id": self.id,
            "file_path": self.file_path,
            "file_name": self.file_name,
            "category": self.category,
            "total_pages": self.total_pages,
            "total_chunks": self.total_chunks,
            "total_characters": self.total_characters,
            "total_tokens": self.total_tokens,
            "document_type": self.document_type,
            "file_size": self.file_size,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_modified": self.last_modified.isoformat()
            if self.last_modified
            else None,
            "outline": self.outline,
            "key_sections": self.key_sections,
        }


def create_vespa_schema_definition() -> Dict[str, Any]:
    """Create Vespa schema definition for the enhanced policy documents."""
    return {
        "schema": "policy_document",
        "document": {
            "fields": [
                # Core fields
                {"name": "id", "type": "string", "indexing": "summary | attribute"},
                {"name": "title", "type": "string", "indexing": "index | summary"},
                {"name": "text", "type": "string", "indexing": "index | summary"},
                {
                    "name": "category",
                    "type": "string",
                    "indexing": "attribute | summary",
                },
                {
                    "name": "chunk_index",
                    "type": "int",
                    "indexing": "attribute | summary",
                },
                {
                    "name": "source_file",
                    "type": "string",
                    "indexing": "attribute | summary",
                },
                # Enhanced metadata fields
                {
                    "name": "page_numbers",
                    "type": "array<int>",
                    "indexing": "attribute | summary",
                },
                {
                    "name": "page_range",
                    "type": "string",
                    "indexing": "attribute | summary",
                },
                {
                    "name": "headings",
                    "type": "array<string>",
                    "indexing": "attribute | summary",
                },
                {
                    "name": "char_count",
                    "type": "int",
                    "indexing": "attribute | summary",
                },
                {
                    "name": "token_count",
                    "type": "int",
                    "indexing": "attribute | summary",
                },
                # Relationship fields
                {
                    "name": "document_id",
                    "type": "string",
                    "indexing": "attribute | summary",
                },
                {
                    "name": "previous_chunk_id",
                    "type": "string",
                    "indexing": "attribute | summary",
                },
                {
                    "name": "next_chunk_id",
                    "type": "string",
                    "indexing": "attribute | summary",
                },
                {
                    "name": "chunk_position",
                    "type": "float",
                    "indexing": "attribute | summary",
                },
                # Additional context
                {
                    "name": "section_path",
                    "type": "array<string>",
                    "indexing": "attribute | summary",
                },
                {
                    "name": "importance_score",
                    "type": "float",
                    "indexing": "attribute | summary",
                },
            ]
        },
        "fieldsets": {"default": ["title", "text"]},
        "rank-profiles": {
            "default": {
                "first-phase": {
                    "expression": "nativeRank(title, text) + 0.1 * attribute(importance_score)"
                }
            },
            "with_position": {
                "first-phase": {
                    "expression": "nativeRank(title, text) * (1.0 - 0.3 * attribute(chunk_position))"
                }
            },
        },
    }


def create_document_metadata_schema() -> Dict[str, Any]:
    """Create Vespa schema for document-level metadata."""
    return {
        "schema": "document_metadata",
        "document": {
            "fields": [
                {"name": "id", "type": "string", "indexing": "summary | attribute"},
                {
                    "name": "file_path",
                    "type": "string",
                    "indexing": "attribute | summary",
                },
                {"name": "file_name", "type": "string", "indexing": "index | summary"},
                {
                    "name": "category",
                    "type": "string",
                    "indexing": "attribute | summary",
                },
                {
                    "name": "total_pages",
                    "type": "int",
                    "indexing": "attribute | summary",
                },
                {
                    "name": "total_chunks",
                    "type": "int",
                    "indexing": "attribute | summary",
                },
                {
                    "name": "total_characters",
                    "type": "long",
                    "indexing": "attribute | summary",
                },
                {
                    "name": "total_tokens",
                    "type": "long",
                    "indexing": "attribute | summary",
                },
                {
                    "name": "document_type",
                    "type": "string",
                    "indexing": "attribute | summary",
                },
                {
                    "name": "file_size",
                    "type": "long",
                    "indexing": "attribute | summary",
                },
                {
                    "name": "created_at",
                    "type": "string",
                    "indexing": "attribute | summary",
                },
                {
                    "name": "last_modified",
                    "type": "string",
                    "indexing": "attribute | summary",
                },
                {
                    "name": "outline",
                    "type": "string",
                    "indexing": "summary",
                },  # Store as JSON string
                {
                    "name": "key_sections",
                    "type": "array<string>",
                    "indexing": "attribute | summary",
                },
            ]
        },
    }
