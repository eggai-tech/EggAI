"""
Policy documents data loaded from markdown files.
This module prevents circular imports by being a standalone data module.
"""

import os
from typing import Any, Dict, List

from agents.policies.rag.config import RAGConfig


def extract_sections_from_content(content: str) -> List[str]:
    """Extract section numbers from markdown content."""
    import re
    
    # Look for section headers in various formats
    patterns = [
        r'^#{1,4}\s*\*\*(\d+(?:\.\d+)?)\.',  # Format: #### **1. or #### **2.1.
        r'^#{1,4}\s*(\d+(?:\.\d+)?)\.',        # Format: #### 1. or #### 2.1.
        r'^#{1,4}\s*.*?\s*\((\d+(?:\.\d+)?)\)'  # Format: # Title (1) or # Title (2.1)
    ]
    
    sections = set()
    for pattern in patterns:
        matches = re.findall(pattern, content, re.MULTILINE)
        sections.update(matches)
    
    # Sort sections naturally (1, 2, 2.1, 2.2, 3, etc.)
    def natural_sort_key(s):
        parts = s.split('.')
        return [int(p) if p.isdigit() else p for p in parts]
    
    return sorted(list(sections), key=natural_sort_key)


def load_policy_documents() -> List[Dict[str, Any]]:
    """Load policy documents from markdown files."""
    documents = []
    current_dir = os.path.dirname(__file__)
    policies_dir = os.path.join(current_dir, "policies")
    
    # Get policy metadata from configuration
    policy_info = RAGConfig.POLICY_METADATA
    
    for category, info in policy_info.items():
        policy_path = os.path.join(policies_dir, f"{category}.md")
        if os.path.exists(policy_path):
            with open(policy_path, "r") as f:
                content = f.read()
                
                # Dynamically extract sections from content
                sections = extract_sections_from_content(content)
                
                documents.append({
                    "id": info["id"],
                    "category": category,
                    "title": info["title"],
                    "content": content,
                    "metadata": {
                        "sections": sections
                    }
                })
    
    return documents


# Load documents once at module level
POLICY_DOCUMENTS = load_policy_documents()