"""Tool status provider for MCP streaming notifications."""

from dspy.streaming import StatusMessageProvider


class MCPToolStatusProvider(StatusMessageProvider):
    """Provides tool call notifications for streaming."""
    
    def _prettify_value(self, value, max_length=80):
        """Prettify and format a value for display."""
        if value is None:
            return ""
        
        # Handle empty arrays/lists
        if isinstance(value, (list, tuple)) and len(value) == 0:
            return ""
        
        # Convert to string and clean up
        str_value = str(value).replace('\n', ' ').replace('\r', ' ')
        
        # Limit length
        if len(str_value) > max_length:
            str_value = str_value[:max_length-3] + "..."
        
        return str_value
    
    def tool_start_status_message(self, instance, inputs):
        args_parts = []
        
        if "kwargs" in inputs and inputs["kwargs"]:
            for k, v in inputs["kwargs"].items():
                prettified = self._prettify_value(v)
                if prettified:  # Only show non-empty values
                    args_parts.append(f"{k}={prettified}")
        elif "args" in inputs and inputs["args"]:
            for arg in inputs["args"]:
                prettified = self._prettify_value(arg)
                if prettified:  # Only show non-empty values
                    args_parts.append(prettified)
        
        if args_parts:
            args_str = f"({', '.join(args_parts)})"
        else:
            args_str = ""
        
        return f"🔧 Calling {instance.name}{args_str}..."
    
    def tool_end_status_message(self, outputs):
        prettified = self._prettify_value(outputs)
        if prettified:
            return f"🔧 {prettified}"
        else:
            return "🔧 Completed"