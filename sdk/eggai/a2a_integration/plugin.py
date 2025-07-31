"""A2A Plugin for EggAI Agent - Handles all A2A-related functionality."""

import logging
from typing import TYPE_CHECKING, Dict, Any, Callable, Optional, Type

if TYPE_CHECKING:
    from ..agent import Agent
    from ..transport.base import Transport

logger = logging.getLogger(__name__)


class A2APlugin:
    """Plugin that adds A2A capabilities to EggAI agents."""
    
    def __init__(self):
        """Initialize empty A2A plugin."""
        self.agent = None
        self.config = None
        self.skills: Dict[str, Any] = {}  # AgentSkill objects
        self.handlers: Dict[str, Callable] = {}  # Handler functions
        self.data_types: Dict[str, Type] = {}  # Data types for conversion
    
    def init(self, agent: "Agent", name: str, transport: Optional["Transport"] = None, **kwargs):
        """Initialize A2A plugin with agent parameters."""
        self.agent = agent
        
        # Extract A2A config from kwargs
        if "a2a_config" in kwargs:
            self.config = kwargs["a2a_config"]
    
    def subscribe(self, channel_name: str, handler: Callable, **kwargs):
        """Handle A2A-specific subscription logic."""
        if "a2a_capability" in kwargs:
            a2a_capability = kwargs['a2a_capability']
            if not isinstance(a2a_capability, str):
                raise ValueError("a2a_capability must be a string representing the skill name")
            data_type = kwargs.get('data_type', None)
            if data_type is None:
                raise ValueError("data_type must be provided for A2A skills")
            self.register_skill(a2a_capability, handler, data_type)
        
    def register_skill(self, skill_name: str, handler: Callable, data_type: Optional[Type]):
        """Register handler as A2A skill."""
        try:
            from a2a.types import AgentSkill
        except ImportError:
            logger.warning("a2a-sdk not installed, A2A skill registration skipped")
            return
        
        # Extract input schema from data_type
        input_schema = {}
        if data_type and hasattr(data_type, 'model_json_schema'):
            try:
                input_schema = data_type.model_json_schema()
            except Exception as e:
                logger.warning(f"Failed to extract input schema from {data_type}: {e}")
        
        # Extract output schema from return type annotation
        output_schema = {}
        if hasattr(handler, '__annotations__') and 'return' in handler.__annotations__:
            return_type = handler.__annotations__['return']
            if hasattr(return_type, 'model_json_schema'):
                try:
                    output_schema = return_type.model_json_schema()
                except Exception as e:
                    logger.warning(f"Failed to extract output schema from {return_type}: {e}")
        
        # Create A2A skill from handler
        skill = AgentSkill(
            id=skill_name,
            name=skill_name,
            description=handler.__doc__ or f"Handler: {skill_name}",
            tags=[skill_name],  # Required field
            input_modes=["data"] if input_schema else ["text"],
            output_modes=["data"] if output_schema else ["text"]
        )
        
        # Store skill, handler, and data type
        self.skills[skill_name] = skill
        self.handlers[skill_name] = handler
        self.data_types[skill_name] = data_type
        
        logger.info(f"Registered A2A skill: {skill_name}")

    def create_agent_card(self):
        """Create agent card from discovered A2A skills."""
        try:
            from a2a.types import AgentCard
        except ImportError:
            raise ImportError("a2a-sdk is required for A2A functionality")
        
        from a2a.types import AgentCapabilities
        
        return AgentCard(
            name=self.config.agent_name,
            description=self.config.description,
            version=self.config.version,
            url=self.config.base_url,
            skills=list(self.skills.values()),
            capabilities=AgentCapabilities(),  # Required field with default capabilities
            default_input_modes=["data", "text"],  # Default modes supported
            default_output_modes=["data", "text"], # Default modes supported
            security_schemes={}  # Empty dict for now, can be enhanced later
        )

    async def start_server(self, host: str = "0.0.0.0", port: int = 8080):
        """Start A2A HTTP server with direct handler execution."""
        if not self.config:
            raise ValueError("A2A config required for A2A server.")
        
        if not self.skills:
            logger.warning("No A2A skills registered. Make sure to use a2a_capability parameter in @agent.subscribe()")
        
        # Create agent card from discovered skills
        agent_card = self.create_agent_card()
        logger.info(f"Created agent card with {len(self.skills)} skills: {list(self.skills.keys())}")
        
        # Start A2A server
        await self._start_a2a_server(agent_card, host, port)

    async def _start_a2a_server(self, agent_card, host: str, port: int):
        """Start A2A HTTP server with EggAI agent executor."""
        try:
            # Import A2A dependencies
            from a2a.server.request_handlers.default_request_handler import DefaultRequestHandler
            from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
            from a2a.server.apps.jsonrpc.starlette_app import A2AStarletteApplication
            import uvicorn
            from .executor import EggAIAgentExecutor
        except ImportError as e:
            raise ImportError(f"A2A dependencies not available: {e}. Install with: pip install a2a-sdk uvicorn")
        
        # Create EggAI agent executor
        executor = EggAIAgentExecutor(self.agent)
        
        # Create request handler with executor and task store
        request_handler = DefaultRequestHandler(
            agent_executor=executor,
            task_store=InMemoryTaskStore()
        )
        
        # Create A2A server application
        server = A2AStarletteApplication(
            agent_card=agent_card,
            http_handler=request_handler
        )
        
        logger.info(f"Starting A2A server on {host}:{port}")
        
        # Run server
        config = uvicorn.Config(server.build(), host=host, port=port, log_level="info")
        uvicorn_server = uvicorn.Server(config)
        await uvicorn_server.serve()