"""A2A Agent Executor for EggAI handlers."""

import json
import logging
from typing import TYPE_CHECKING, Dict, Any

from ..schemas import BaseMessage

if TYPE_CHECKING:
    from ..agent import Agent

try:
    from a2a.server.agent_execution.agent_executor import AgentExecutor
    from a2a.server.agent_execution.context import RequestContext
    from a2a.server.events.event_queue import EventQueue
except ImportError:
    raise ImportError(
        "EggAI A2A integration requires the a2a-sdk package. "
        "Please install it with: pip install a2a-sdk"
    )

logger = logging.getLogger(__name__)


class EggAIAgentExecutor(AgentExecutor):
    """A2A Agent Executor that calls EggAI handlers directly."""
    
    def __init__(self, agent: "Agent"):
        super().__init__()
        self.agent = agent
    
    async def execute(self, request_context: RequestContext, event_queue: EventQueue):
        """Execute A2A request by calling EggAI handler directly."""
        try:
            # Extract skill name from request
            skill_name = self._extract_skill_name(request_context)
            logger.info(f"Executing A2A skill: {skill_name}")
            
            if skill_name not in self._a2a_handlers:
                error_msg = f"Unknown skill: {skill_name}. Available skills: {list(self.agent._a2a_handlers.keys())}"
                logger.error(error_msg)
                await event_queue.new_agent_text_message(error_msg)
                return
            
            # Get handler and extract message data
            handler = self.agent._a2a_handlers[skill_name]
            message_data = self._extract_message_data(request_context)
            
            # Convert dict data to Pydantic model if we have the data type
            if hasattr(self.agent, '_a2a_data_types') and skill_name in self.agent._a2a_data_types:
                data_type = self.agent._a2a_data_types[skill_name]
                if data_type and hasattr(data_type, 'model_validate'):
                    try:
                        message_data = data_type.model_validate(message_data)
                        logger.debug(f"Converted dict to {data_type.__name__}: {message_data}")
                    except Exception as e:
                        logger.warning(f"Failed to convert data to {data_type.__name__}: {e}")
                        # Keep as dict if conversion fails
            
            # Create EggAI message format
            eggai_message = BaseMessage(
                source="a2a-client",
                type=f"{skill_name}.request",
                data=message_data
            )
            
            logger.debug(f"Calling handler with message: {eggai_message}")
            
            # Call handler directly (no Kafka!)
            result = await handler(eggai_message)
            
            # Convert result to A2A response
            if result is not None:
                # If result is a Pydantic model, convert to dict
                if hasattr(result, 'model_dump'):
                    result_dict = result.model_dump()
                    await self._send_agent_response(event_queue, result_dict)
                elif hasattr(result, 'dict'):
                    result_dict = result.dict()
                    await self._send_agent_response(event_queue, result_dict)
                else:
                    await self._send_agent_response(event_queue, {"result": str(result)})
            else:
                await self._send_agent_response(event_queue, {"status": "completed"})
                
        except Exception as e:
            error_msg = f"Error executing skill '{skill_name}': {str(e)}"
            logger.exception(error_msg)
            await self._send_agent_response(event_queue, {"error": error_msg})
    
    async def cancel(self, request_context: RequestContext, event_queue: EventQueue):
        """Cancel execution (not supported for direct calls)."""
        error_msg = "Cancellation not supported for direct handler calls"
        logger.warning(error_msg)
        await self._send_agent_response(event_queue, {"error": error_msg})
    
    def _extract_skill_name(self, request_context: RequestContext) -> str:
        """Extract skill name from A2A request context."""
        # The skill name should be available in the request context
        if hasattr(request_context, 'skill_id') and request_context.skill_id:
            return request_context.skill_id
        elif hasattr(request_context, 'skill') and request_context.skill:
            return request_context.skill
        
        # Check message metadata for skill
        if hasattr(request_context, 'message') and request_context.message:
            message = request_context.message
            if hasattr(message, 'metadata') and message.metadata:
                if 'skill' in message.metadata:
                    return message.metadata['skill']
        
        # Fallback to first available skill
        available_skills = list(self.agent._a2a_handlers.keys())
        if available_skills:
            logger.warning(f"No skill specified, using first available: {available_skills[0]}")
            return available_skills[0]
        else:
            raise ValueError("No skill specified and no skills available")
    
    def _extract_message_data(self, request_context: RequestContext) -> Dict[str, Any]:
        """Extract and parse message data from A2A request."""
        try:
            # Parse A2A message content into dict
            message_content = request_context.message
            
            if not message_content:
                return {}
            
            # Handle new A2A message structure with parts
            if hasattr(message_content, 'parts') and message_content.parts:
                for part in message_content.parts:
                    if hasattr(part, 'root'):
                        root = part.root
                        if hasattr(root, 'kind'):
                            if root.kind == "text" and hasattr(root, 'text'):
                                # Try to parse JSON from text
                                try:
                                    return json.loads(root.text)
                                except (json.JSONDecodeError, ValueError):
                                    return {"text": root.text}
                            elif root.kind == "data" and hasattr(root, 'data'):
                                return root.data if root.data else {}
                            elif root.kind == "file":
                                return {"file_ref": getattr(root, 'file_uri', None)}
            
            # Handle legacy content structure  
            elif hasattr(message_content, 'content') and message_content.content:
                for part in message_content.content:
                    if hasattr(part, 'type'):
                        if part.type == "text":
                            # Try to parse JSON from text
                            try:
                                return json.loads(part.text)
                            except (json.JSONDecodeError, ValueError):
                                return {"text": part.text}
                        elif part.type == "data":
                            return part.data if part.data else {}
                        elif part.type == "file":
                            return {"file_ref": getattr(part, 'file_uri', None)}
            
            # Fallback: try to convert message directly
            if hasattr(message_content, 'dict'):
                return message_content.dict()
            elif hasattr(message_content, 'model_dump'):
                return message_content.model_dump()
            else:
                return {"message": str(message_content)}
            
        except Exception as e:
            logger.exception(f"Error extracting message data: {e}")
            return {"error": f"Failed to parse message: {str(e)}"}
    
    async def _send_agent_response(self, event_queue: EventQueue, data: dict):
        """Send agent response through event queue."""
        try:
            from a2a.types import Message, Part, DataPart, Role
            from uuid import uuid4
            
            # Create A2A message with response data
            response_message = Message(
                messageId=str(uuid4()),
                role=Role.agent,
                parts=[Part(root=DataPart(data=data))]
            )
            
            # Enqueue the message as an event
            await event_queue.enqueue_event(response_message)
            logger.debug(f"Sent agent response: {data}")
            
        except Exception as e:
            logger.exception(f"Failed to send agent response: {e}")
            # Fallback: try to send as simple event
            try:
                await event_queue.enqueue_event({"text": json.dumps(data)})
            except:
                logger.error("Failed to send any response to event queue")