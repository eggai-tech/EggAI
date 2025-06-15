"""Configuration for the RAG (Retrieval Augmented Generation) system."""

from typing import Any, Dict


class RAGConfig:
    """Configuration constants for the RAG system."""
    
    # Temporal Configuration
    TEMPORAL_ADDRESS = "localhost:7233"
    TEMPORAL_NAMESPACE = "default"
    TASK_QUEUE = "policy-rag"
    WORKFLOW_ID_PREFIX = "policy-rag-workflow"
    
    # Workflow Configuration
    ACTIVITY_TIMEOUT_SECONDS = 30
    RETRY_MAX_ATTEMPTS = 3
    
    # Text Processing Configuration
    MAX_PROMPT_TOKENS = 4000
    CHARS_PER_TOKEN_ESTIMATE = 4
    TRUNCATION_BUFFER_CHARS = 100
    SECTION_PREVIEW_CHARS = 500
    MAX_CONTEXT_CHARS = 14000  # 3500 * 4
    
    # Document Retrieval Configuration
    MAX_SECTIONS_PER_DOCUMENT = 3
    MAX_DOCUMENTS_PER_QUERY = 2
    MIN_WORD_LENGTH_FOR_MATCHING = 3
    
    # Scoring Configuration
    CATEGORY_MATCH_BASE_SCORE = 5
    POLICY_NUMBER_MATCH_SCORE = 10
    WORD_MATCH_SCORE = 2
    MIN_CATEGORY_SCORE = 1
    
    # Policy Metadata (could be moved to a database or external config)
    POLICY_METADATA: Dict[str, Dict[str, Any]] = {
        "health": {
            "id": "health-001",
            "title": "Health Insurance Policy"
        },
        "auto": {
            "id": "auto-001",
            "title": "Auto Insurance Policy"
        },
        "home": {
            "id": "home-001",
            "title": "Home Insurance Policy"
        },
        "life": {
            "id": "life-001",
            "title": "Life Insurance Policy"
        }
    }
    
    # Error Messages
    ERROR_MESSAGES = {
        "generic": "I apologize, but I encountered an error while processing your question. Could you please rephrase your question or try asking about a specific aspect of your policy?",
        "no_documents": "I couldn't find specific information about that in the policy documents. Could you please provide more details about what aspect of your policy you'd like to know about?",
        "retrieval_failed": "I'm having trouble accessing the policy documents right now. Please try again in a moment."
    }
    
    # Prompt Templates
    GENERATION_PROMPT_TEMPLATE = """
Please answer the following insurance question based on the provided policy information:

Question: {query}

Policy Information:
{context}

Instructions:
1. Provide a detailed answer using only the information provided above
2. When referencing policy information, cite the relevant section (e.g., "According to Section 3.2...")
3. Be concise and accurate
4. Do not invent or hallucinate any policy details not present in the provided information
5. If the information is not available in the policy details, acknowledge this and ask for clarification about what specific information they need

Your Answer:
"""