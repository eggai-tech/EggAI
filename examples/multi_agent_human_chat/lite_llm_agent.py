import inspect
import json
from typing import Optional, Callable

import litellm

from sdk.eggai import Agent

def function_to_json_schema(func: Callable) -> dict:
    parameters = {"type": "object", "properties": {}, "required": []}
    sig = inspect.signature(func)
    name = func.__name__
    docstring = (inspect.getdoc(func) or "").split('\n')
    description = " ".join([line for line in docstring if line.strip() and not line.lstrip().startswith(':')])

    for param in sig.parameters.values():
        if param.name == "self":
            continue
        if param.default == inspect.Parameter.empty:
            parameters["required"].append(param.name)
        parameters["properties"][param.name] = {
            "type": "string",
            "description": param.name,
        }
        if len(docstring) > 0:
            for line in docstring:
                if line.startswith(f":param {param.name}:"):
                    parameters["properties"][param.name]["description"] = line.split(":param ")[1]
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }

class LiteLlmAgent(Agent):
    def __init__(self, name: str, model: Optional[str] = None, system_message: Optional[str] = None, **kwargs):
        super().__init__(name)
        self.model = model
        self.system_message = system_message
        self.tools = []
        self.tools_map = {}
        self.local_kwargs = kwargs

    async def completion(self, **kwargs):
        model = kwargs.pop("model", self.model)
        messages = kwargs.pop("messages", [])
        if self.system_message:
            messages = [{"role": "system", "content": self.system_message}, *messages]

        tools = kwargs.pop("tools", [])
        if len(self.tools) > 0:
            tools.extend(self.tools)
        if len(tools) > 0:
            kwargs["tools"] = tools

        final_params = {**self.local_kwargs, **kwargs, "model": model, "messages": messages}
        response = await litellm.acompletion(**final_params)
        tool_calls = response.choices[0].message.tool_calls
        if tool_calls:
            messages.append(response.choices[0].message)
            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                function_to_call = self.tools_map.get(tool_name)
                tool_args = json.loads(tool_call.function.arguments)
                if inspect.iscoroutinefunction(function_to_call):
                    function_response = await function_to_call(**tool_args)
                else:
                    function_response = function_to_call(**tool_args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": json.dumps(function_response)
                })
            final_params = {**self.local_kwargs,  **kwargs, "model": model, "messages": messages}
            response = await litellm.acompletion(**final_params)
            return response

        return response

    def tool(self, name: str = None, description: str = None):
        def decorator(func: Callable):
            json_schema = function_to_json_schema(func)
            if name is not None:
                json_schema["function"]["name"] = name

            if description is not None:
                json_schema["function"]["description"] = description

            self.tools.append(json_schema)
            self.tools_map[json_schema["function"]["name"]] = func
            return func

        return decorator