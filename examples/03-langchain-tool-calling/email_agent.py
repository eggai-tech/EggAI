from eggai import Agent
from typing import Dict, List
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-3.5-turbo-0125")

agent = Agent("EmailAgent")

@tool
def count_emails(last_n_days: int) -> int:
    """Multiply two integers together."""
    return last_n_days * 2

tools = [count_emails]
llm_with_tools = llm.bind_tools(tools)

def call_tools(msg: AIMessage) -> List[Dict]:
    """Simple sequential tool calling helper."""
    tool_map = {tool.name: tool for tool in tools}
    tool_calls = msg.tool_calls.copy()
    for tool_call in tool_calls:
        tool_call["output"] = tool_map[tool_call["name"]].invoke(tool_call["args"])
    return tool_calls


chain = llm_with_tools | call_tools

@agent.subscribe(filter_func=lambda event: event["event_name"] == "email_prompt_requested")
async def send_email(message):
    prompt = message.get("payload", {}).get("prompt")
    result = chain.invoke(prompt)
    print(f"[EMAIL AGENT Result]: {result}")