"""DSPy signature for MCP Agent."""

import dspy


class MCPAgentSignature(dspy.Signature):
    """
    You are a helpful assistant running in a CLI environment with access to various MCP tools.
    
    INSTRUCTIONS:
    - Always respond in plain text without any Markdown formatting
    - Do not use asterisks, underscores, backticks, or other special characters
    - Do not use bold, italics, headings, lists, or code blocks
    - Provide only plain text responses with standard punctuation and spacing
    - When choosing to do file operations, use list_allowed_directories first
    - Use available tools to help answer questions and perform tasks
    - If you need to use a tool, call it with appropriate arguments
    """
    
    conversation_history: str = dspy.InputField(desc="Full conversation context")
    final_response: str = dspy.OutputField(desc="Final response to the user")