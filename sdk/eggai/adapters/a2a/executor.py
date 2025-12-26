"""A2A Agent Executor for EggAI handlers."""

import json
import logging
from typing import TYPE_CHECKING, Any

from eggai.schemas import BaseMessage

if TYPE_CHECKING:
    from eggai.agent import Agent

from a2a.server.agent_execution.agent_executor import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue

logger = logging.getLogger(__name__)


class EggAIAgentExecutor(AgentExecutor):
    """A2A Agent Executor that calls EggAI handlers directly."""

    def __init__(self, agent: "Agent"):
        super().__init__()
        self.agent = agent
        # Get A2A plugin instance
        self.a2a_plugin = agent.plugins["a2a"]["_instance"]

    async def execute(self, request_context: RequestContext, event_queue: EventQueue):
        """Execute A2A request by calling EggAI handler directly."""
        try:
            # Extract skill name from request
            skill_name = self._extract_skill_name(request_context)
            logger.info(f"Executing A2A skill: {skill_name}")

            if skill_name not in self.a2a_plugin.handlers:
                error_msg = f"Unknown skill: {skill_name}. Available skills: {list(self.a2a_plugin.handlers.keys())}"
                logger.error(error_msg)
                await event_queue.enqueue_event({"text": error_msg})
                return

            # Get handler and extract message data
            handler = self.a2a_plugin.handlers[skill_name]
            message_data = self._extract_message_data(request_context)

            # Create proper BaseMessage with validated data
            validated_data = message_data
            if skill_name in self.a2a_plugin.data_types:
                data_type = self.a2a_plugin.data_types[skill_name]
                if (
                    data_type
                    and hasattr(data_type, "__args__")
                    and len(data_type.__args__) > 0
                ):
                    # Extract inner type from BaseMessage[T] and validate the raw data
                    inner_type = data_type.__args__[0]
                    if hasattr(inner_type, "model_validate"):
                        try:
                            validated_data = inner_type.model_validate(message_data)
                            logger.debug(
                                f"Validated data as {inner_type.__name__}: {validated_data}"
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to validate data as {inner_type.__name__}: {e}"
                            )
                            # Keep as dict if validation fails

            # Create the proper BaseMessage structure that the handler expects
            if skill_name in self.a2a_plugin.data_types:
                data_type = self.a2a_plugin.data_types[skill_name]
                # Create instance of the specific BaseMessage subclass
                eggai_message = data_type(
                    source="a2a-client",
                    type=f"{skill_name}.request",
                    data=validated_data,
                )
            else:
                # Fallback to generic BaseMessage
                eggai_message = BaseMessage(
                    source="a2a-client",
                    type=f"{skill_name}.request",
                    data=validated_data,
                )

            logger.debug(f"Calling handler with message: {eggai_message}")

            # Call handler
            result = await handler(eggai_message)

            # Convert result to A2A response
            if result is not None:
                # If result is a Pydantic model, convert to dict
                if hasattr(result, "model_dump"):
                    result_dict = result.model_dump()
                    await self._send_agent_response(event_queue, result_dict)
                elif hasattr(result, "dict"):
                    result_dict = result.dict()
                    await self._send_agent_response(event_queue, result_dict)
                else:
                    await self._send_agent_response(
                        event_queue, {"result": str(result)}
                    )
            else:
                await self._send_agent_response(event_queue, {"status": "completed"})

        except Exception as e:
            skill_name = (
                locals()["skill_name"] if "skill_name" in locals() else "unknown"
            )
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
        # Check request context metadata (primary location)
        if request_context.metadata and "skill_id" in request_context.metadata:
            return request_context.metadata["skill_id"]

        # Check task metadata for skill information
        if request_context.current_task and request_context.current_task.metadata:
            if "skill_id" in request_context.current_task.metadata:
                return request_context.current_task.metadata["skill_id"]

        # If we have only one skill, use it (common case)
        available_skills = list(self.a2a_plugin.handlers.keys())
        if len(available_skills) == 1:
            return available_skills[0]

        raise ValueError(
            f"Could not determine skill ID from request context. Available skills: {available_skills}"
        )

    def _extract_message_data(self, request_context: RequestContext) -> dict[str, Any]:
        """Extract and parse message data from A2A request."""
        try:
            # Parse A2A message content into dict
            message_content = request_context.message

            if not message_content:
                return {}

            # Handle new A2A message structure with parts
            if hasattr(message_content, "parts") and message_content.parts:
                for part in message_content.parts:
                    if hasattr(part, "root"):
                        root = part.root
                        if hasattr(root, "kind"):
                            if root.kind == "text" and hasattr(root, "text"):
                                # Try to parse JSON from text
                                try:
                                    return json.loads(root.text)
                                except (json.JSONDecodeError, ValueError):
                                    return {"text": root.text}
                            elif root.kind == "data" and hasattr(root, "data"):
                                return root.data if root.data else {}
                            elif root.kind == "file":
                                return {"file_ref": getattr(root, "file_uri", None)}

            # Handle legacy content structure
            elif hasattr(message_content, "content") and message_content.content:
                for part in message_content.content:
                    if hasattr(part, "type"):
                        if part.type == "text":
                            # Try to parse JSON from text
                            try:
                                return json.loads(part.text)
                            except (json.JSONDecodeError, ValueError):
                                return {"text": part.text}
                        elif part.type == "data":
                            return part.data if part.data else {}
                        elif part.type == "file":
                            return {"file_ref": getattr(part, "file_uri", None)}

            # Fallback: try to convert message directly
            if hasattr(message_content, "dict"):
                return message_content.dict()
            elif hasattr(message_content, "model_dump"):
                return message_content.model_dump()
            else:
                return {"message": str(message_content)}

        except (AttributeError, TypeError, ValueError) as e:
            logger.exception(f"Error extracting message data: {e}")
            return {"error": f"Failed to parse message: {str(e)}"}

    async def _send_agent_response(self, event_queue: EventQueue, data: dict):
        """Send agent response through event queue."""
        try:
            from uuid import uuid4

            from a2a.types import DataPart, Message, Part, Role

            # Create A2A message with response data
            response_message = Message(
                message_id=str(uuid4()),
                role=Role.agent,
                parts=[Part(root=DataPart(data=data))],
            )

            # Enqueue the message as an event
            await event_queue.enqueue_event(response_message)
            logger.debug(f"Sent agent response: {data}")

        except ImportError as e:
            logger.error(f"A2A types not available: {e}")
            raise
        except (ValueError, TypeError) as e:
            logger.exception(f"Failed to create A2A message from data: {e}")
            # Fallback: try to send as simple event
            try:
                await event_queue.enqueue_event({"text": json.dumps(data)})
            except (json.JSONEncodeError, TypeError) as json_err:
                logger.error(f"Failed to serialize response data: {json_err}")
                raise
