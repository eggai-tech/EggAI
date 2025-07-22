"""Main MCP agent implementation with DSPy streaming."""

import asyncio
import os
import warnings

import aioconsole
import dotenv
import dspy
from dspy import Prediction
from dspy.streaming import StreamResponse, StatusMessage
from eggai import Agent, Channel
from eggai.schemas import Message
from eggai.transport import KafkaTransport, eggai_set_default_transport
from mcp import StdioServerParameters

from .mcp_manager import MCPManager
from .signature import MCPAgentSignature
from .status_provider import MCPToolStatusProvider

dotenv.load_dotenv()
eggai_set_default_transport(lambda: KafkaTransport())


async def run_mcp_agent():
    """Self-contained MCP agent with DSPy ReAct integration."""
    
    dspy.configure(lm=dspy.LM(model="openai/gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY"), cache=False))
    
    mcp_manager = MCPManager()
    servers = [
        ("FileSystem", StdioServerParameters(command="npx", args=["-y", "@modelcontextprotocol/server-filesystem", "sandbox"]))
    ]
    
    await mcp_manager.initialize(servers)
    
    react = dspy.ReAct(MCPAgentSignature, tools=mcp_manager.get_tools(), max_iters=5)
    
    agent = Agent("MCPAgent")
    user_channel = Channel("user.input")
    assistant_channel = Channel("assistant.output")
    conversation_history = []
    
    @agent.subscribe(user_channel)
    async def handle_user_input(msg: Message):
        user_input = msg.data.get("input", "")
        
        if not user_input or not user_input.strip():
            return
            
        conversation_history.append(f"User: {user_input}")
        history_str = "\n".join(conversation_history)
        
        try:
            response_queue = asyncio.Queue()
            
            async def process_streaming():
                """Process DSPy streaming in isolated background task."""
                try:
                    stream = dspy.streamify(
                        react,
                        stream_listeners=[dspy.streaming.StreamListener(signature_field_name="final_response")],
                        include_final_prediction_in_output_stream=True,
                        is_async_program=True,
                        async_streaming=True,
                        status_message_provider=MCPToolStatusProvider(),
                    )(conversation_history=history_str)
                    
                    async for chunk in stream:
                        await response_queue.put(chunk)
                    await response_queue.put(None)  # Signal completion
                except Exception as e:
                    await response_queue.put(e)
            
            stream_task = asyncio.create_task(process_streaming())
            
            first_token = True
            full_response = ""
            
            while True:
                chunk = await response_queue.get()
                
                if chunk is None:
                    break
                elif isinstance(chunk, Exception):
                    raise chunk
                elif isinstance(chunk, StreamResponse):
                    token_msg = Message(
                        type="assistant_token",
                        source="mcp_agent",
                        data={"token": chunk.chunk, "is_first": first_token}
                    )
                    first_token = False
                    await assistant_channel.publish(token_msg)
                    full_response += chunk.chunk
                    
                elif isinstance(chunk, StatusMessage):
                    status_msg = Message(
                        type="tool_notification", 
                        source="mcp_agent",
                        data={"message": chunk.message}
                    )
                    await assistant_channel.publish(status_msg)
                    
                elif isinstance(chunk, Prediction):
                    if hasattr(chunk, 'final_response'):
                        full_response = chunk.final_response
                    break
            
            await stream_task
            
            end_msg = Message(type="assistant_end", source="mcp_agent", data={})
            await assistant_channel.publish(end_msg)
            
            if full_response:
                conversation_history.append(f"Assistant: {full_response}")
                
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        except Exception:
            error_msg = "I'm sorry, I encountered an error while processing your request."
            error_token = Message(
                type="assistant_token",
                source="mcp_agent",
                data={"token": error_msg, "is_first": True}
            )
            await assistant_channel.publish(error_token)
            
            error_end = Message(type="assistant_end", source="mcp_agent", data={})
            await assistant_channel.publish(error_end)

    try:
        await agent.start()
        await asyncio.Future()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await mcp_manager.cleanup()


if __name__ == "__main__":
    asyncio.run(run_mcp_agent())