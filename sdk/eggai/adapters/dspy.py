from eggai.adapters.client import EggaiAdapterClient
from eggai.adapters.types import ExternalTool

try:
    import dspy

    def convert_tool_for_dspy(
        adapter_client: EggaiAdapterClient, tool: ExternalTool
    ) -> dspy.Tool:
        """Return a callable for the tool."""

        async def tool_func(**kwargs):
            result = await adapter_client.call_tool(tool.name, kwargs)
            if result.is_error:
                return f"Error calling tool {tool.name}: {result.data}"
            return result.data

        return dspy.Tool(
            name=tool.name,
            func=tool_func,
            desc=tool.description,
            args=tool.parameters,
        )
except ImportError:
    pass
