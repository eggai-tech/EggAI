"""Real DSPy ReAct agent with external tools integration."""

import asyncio
import logging
import os
from typing import List, Optional

import dspy
import dotenv
from eggai import Agent, Channel
from eggai.schemas import Message
from eggai.transport import KafkaTransport, eggai_set_default_transport

from react_signature import ExternalToolsSignature
from create_dspy_tools import create_dspy_tools

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from agent_integration import setup_external_tools, get_cached_tools
# FileSystem MCP adapter will be started separately

logger = logging.getLogger(__name__)

dotenv.load_dotenv()
eggai_set_default_transport(lambda: KafkaTransport())


class ReactAgentWithExternalTools:
    """DSPy ReAct agent integrated with external tools via adapters."""
    
    def __init__(self, agent_name: str = "ReactAgent"):
        self.agent_name = agent_name
        # Use fixed agent name for stable consumer groups
        self.agent = Agent(agent_name)
        self.user_channel = Channel("user.input") 
        self.response_channel = Channel("agent.response")
        
        # Initialize DSPy
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable required")
            
        dspy.configure(
            lm=dspy.LM(
                model="openai/gpt-4o-mini",
                api_key=api_key,
                max_tokens=1000,
                temperature=0.1
            )
        )
        
        self.react_module = None
        self.conversation_history = []
        
    async def setup_external_tools(self, adapter_names: List[str]):
        """Set up external tools integration."""
        logger.info("Setting up external tools...")
        
        # FileSystem adapter should be started externally
        logger.info(f"Discovering tools from adapters: {adapter_names}")
        
        # Discover tools using standalone function
        external_tools = await setup_external_tools(adapter_names, source_id=self.agent_name)
        
        logger.info(f"📋 Discovered {len(external_tools)} external tools:")
        for tool in external_tools:
            logger.info(f"  🔧 {tool.name}: {tool.description}")
            logger.info(f"     Adapter: {tool.adapter_name}")
            logger.info(f"     Parameters: {tool.parameters}")
        
        dspy_tools = create_dspy_tools(external_tools)
        
        # Create ReAct module with tools
        self.react_module = dspy.ReAct(
            signature=ExternalToolsSignature,
            tools=dspy_tools,
            max_iters=5
        )
        
        logger.info(f"ReAct agent initialized with {len(dspy_tools)} external tools")
        
    def add_to_conversation(self, role: str, content: str):
        """Add message to conversation history."""
        self.conversation_history.append(f"{role}: {content}")
        
        # Keep last 10 messages to avoid token limits
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]
    
    async def process_user_input(self, user_input: str) -> str:
        """Process user input using ReAct with external tools."""
        if not self.react_module:
            return "Error: ReAct module not initialized. Please set up external tools first."
        
        self.add_to_conversation("User", user_input)
        history_str = "\n".join(self.conversation_history)
        
        try:
            logger.info(f"Processing user input with ReAct: {user_input}")
            
            # Use ReAct to process the input
            result = self.react_module(
                conversation_history=history_str,
                user_input=user_input
            )
            
            response = result.final_response
            self.add_to_conversation("Assistant", response)
            
            logger.info(f"ReAct generated response: {response[:100]}...")
            return response
            
        except Exception as e:
            error_msg = f"Error processing request: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    async def start(self):
        """Start the ReAct agent."""
        logger.info("Starting ReAct agent with external tools...")
        
        # FIRST set up external tools (which adds tool response subscriptions)
        await self.setup_external_tools(["FileSystem"])
        
        # THEN set up user message handlers
        @self.agent.subscribe(self.user_channel)
        async def handle_user_input(msg: Message):
            user_input = msg.data.get("input", "")
            
            if not user_input.strip():
                return
                
            # Process with ReAct
            response = await self.process_user_input(user_input)
            
            # Send response
            response_msg = Message(
                type="agent_response",
                source=self.agent_name,
                data={"response": response}
            )
            await self.response_channel.publish(response_msg)
        
        # FINALLY start agent (after ALL subscriptions are set up)
        await self.agent.start()
        logger.info("✅ ReactAgent started")
        
        logger.info("ReAct agent ready!")
        
    async def stop(self):
        """Stop the agent."""
        await self.agent.stop()
        logger.info("ReAct agent stopped")