import inspect
import json
from typing import Optional, Callable

import litellm

from eggai import Agent

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
    def __init__(self, name: str, model: Optional[str] = None, system_message: Optional[str] = None):
        super().__init__(name)
        self.model = model
        self.system_message = system_message
        self.tools = []
        self.tools_map = {}

    async def completion(self, **kwargs):
        model = kwargs.pop("model", self.model)
        if model is None:
            raise ValueError("Model is required for completion.")

        messages = kwargs.pop("messages", [])
        if self.system_message:
            messages = [{"role": "system", "content": self.system_message}, *messages]

        tools = kwargs.pop("tools", [])
        if len(tools) > 0:
            self.tools.extend(tools)
        if len(self.tools) > 0:
            kwargs["tools"] = self.tools

        response = await litellm.acompletion(**{**kwargs, "model": model, "messages": messages})
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
            response = await litellm.acompletion(**{**kwargs, "model": model, "messages": messages})
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


if __name__ == "__main__":
    import dotenv
    import random
    import asyncio

    agent = LiteLlmAgent("LlmAgent", model="openai/gpt-3.5-turbo")

    @agent.tool()
    async def get_current_weather(location, unit="Celsius"):
        """
        Get the current weather in a given location.

        :param location: The city and state, e.g. San Francisco, CA
        :param unit: The unit of temperature, either Celsius or Fahrenheit

        :return: The current weather in the given location
        """
        print("[TOOL CALL] get_current_weather", location, unit)
        random_temperature = random.randint(-20, 40)

        if unit == "Fahrenheit":
            temp_random_in_fahrenheit = (random_temperature * 9 / 5) + 32
            return {"location": location, "temperature": temp_random_in_fahrenheit, "unit": "Fahrenheit"}

        return {"location": location, "temperature": random_temperature, "unit": "Celsius"}

    async def main():
        message = "What is the current weather in San Francisco and in Paris? All in celsius please"
        completion = await agent.completion(messages=[{"role": "user", "content": message}])
        print(completion.choices[0].message.content)

    dotenv.load_dotenv()
    asyncio.run(main())
