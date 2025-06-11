import asyncio
import uuid
from typing import List, Union

from eggai import Agent, Channel
from eggai.transport import KafkaTransport, eggai_set_default_transport

from agents.policies.types import ChatMessage, ModelConfig
from libraries.channels import channels, clear_channels
from libraries.logger import get_console_logger
from libraries.tracing import (
    TracedMessage,
    create_tracer,
    format_span_as_traceparent,
    init_telemetry,
    traced_handler,
)
from libraries.tracing.otel import safe_set_attribute

policy_documentation_agent = Agent(name="PolicyDocumentationAgent")
logger = get_console_logger("policy_documentation_agent.orchestrator")
agents_channel = Channel(channels.agents)
human_channel = Channel(channels.human)
human_stream_channel = Channel(channels.human_stream)
internal_channel = Channel(channels.internal)
tracer = create_tracer("policy_documentation_agent")


def get_conversation_string(chat_messages: List[ChatMessage]) -> str:
    """Format chat messages into a conversation string."""
    with tracer.start_as_current_span("get_conversation_string") as span:
        safe_set_attribute(
            span, "chat_messages_count", len(chat_messages) if chat_messages else 0
        )

        if not chat_messages:
            safe_set_attribute(span, "empty_messages", True)
            return ""

        conversation_parts = []
        for chat in chat_messages:
            if "content" not in chat:
                safe_set_attribute(span, "invalid_message", True)
                logger.warning("Message missing content field")
                continue

            role = chat.get("role", "User")
            conversation_parts.append(f"{role}: {chat['content']}")

        conversation = "\n".join(conversation_parts) + "\n"
        safe_set_attribute(span, "conversation_length", len(conversation))
        return conversation


async def process_documentation_request(
    conversation_string: str,
    connection_id: str,
    message_id: str,
    timeout_seconds: float = None,
    streaming: bool = True,
) -> None:
    """Process a policy documentation request using RAG components."""
    config = ModelConfig(timeout_seconds=timeout_seconds or 30.0)
    request_id = str(uuid.uuid4())

    with tracer.start_as_current_span("process_documentation_request") as span:
        child_traceparent, child_tracestate = format_span_as_traceparent(span)
        safe_set_attribute(span, "connection_id", connection_id)
        safe_set_attribute(span, "message_id", message_id)
        safe_set_attribute(span, "request_id", request_id)
        safe_set_attribute(span, "conversation_length", len(conversation_string))
        safe_set_attribute(span, "streaming", streaming)

        if not conversation_string or len(conversation_string.strip()) < 5:
            safe_set_attribute(span, "error", "Empty or too short conversation")
            span.set_status(1, "Invalid input")
            raise ValueError("Conversation history is too short to process")

        # Extract the last user message as the query
        lines = conversation_string.strip().split("\n")
        query = ""
        for line in reversed(lines):
            if line.startswith("User:"):
                query = line[5:].strip()
                break

        if not query:
            query = conversation_string.strip()

        logger.info(f"Processing documentation request for query: '{query[:100]}...'")

        if streaming:
            # Start the stream
            await human_stream_channel.publish(
                TracedMessage(
                    type="agent_message_stream_start",
                    source="PolicyDocumentationAgent",
                    data={
                        "message_id": message_id,
                        "connection_id": connection_id,
                    },
                    traceparent=child_traceparent,
                    tracestate=child_tracestate,
                )
            )
            logger.info(f"Stream started for message {message_id}")

        try:
            # Step 1: Retrieval
            logger.info("Step 1: Requesting document retrieval")
            await internal_channel.publish(
                TracedMessage(
                    type="retrieval_request",
                    source="PolicyDocumentationAgent",
                    data={
                        "request_id": request_id,
                        "query": query,
                        "category": None,  # Could be extracted from conversation if needed
                    },
                    traceparent=child_traceparent,
                    tracestate=child_tracestate,
                )
            )

            # Wait for retrieval response
            retrieval_response = await wait_for_response(
                "retrieval_response", request_id, timeout_seconds=30.0
            )

            if "error" in retrieval_response.data:
                logger.error(f"Retrieval error: {retrieval_response.data['error']}")
                raise Exception(f"Retrieval failed: {retrieval_response.data['error']}")

            documents = retrieval_response.data.get("documents", [])
            logger.info(f"Retrieved {len(documents)} documents")

            # Step 2: Augmentation
            logger.info("Step 2: Requesting context augmentation")
            await internal_channel.publish(
                TracedMessage(
                    type="augmentation_request",
                    source="PolicyDocumentationAgent",
                    data={
                        "request_id": request_id,
                        "query": query,
                        "documents": documents,
                        "conversation_history": conversation_string,
                        "max_context_length": 4000,
                    },
                    traceparent=child_traceparent,
                    tracestate=child_tracestate,
                )
            )

            # Wait for augmentation response
            augmentation_response = await wait_for_response(
                "augmentation_response", request_id, timeout_seconds=30.0
            )

            if "error" in augmentation_response.data:
                logger.error(
                    f"Augmentation error: {augmentation_response.data['error']}"
                )
                raise Exception(
                    f"Augmentation failed: {augmentation_response.data['error']}"
                )

            augmented_context = augmentation_response.data.get("augmented_context", "")
            logger.info(f"Augmented context length: {len(augmented_context)}")

            # Step 3: Generation
            logger.info("Step 3: Requesting response generation")
            await internal_channel.publish(
                TracedMessage(
                    type="generation_request",
                    source="PolicyDocumentationAgent",
                    data={
                        "request_id": request_id,
                        "augmented_context": augmented_context,
                        "streaming": streaming,
                        "config": {
                            "timeout_seconds": config.timeout_seconds,
                            "truncation_length": config.truncation_length,
                        },
                    },
                    traceparent=child_traceparent,
                    tracestate=child_tracestate,
                )
            )

            if streaming:
                # Handle streaming generation
                await handle_streaming_generation(
                    request_id,
                    message_id,
                    connection_id,
                    child_traceparent,
                    child_tracestate,
                )
            else:
                # Wait for generation response
                generation_response = await wait_for_response(
                    "generation_response", request_id, timeout_seconds=60.0
                )

                if "error" in generation_response.data:
                    logger.error(
                        f"Generation error: {generation_response.data['error']}"
                    )
                    raise Exception(
                        f"Generation failed: {generation_response.data['error']}"
                    )

                response = generation_response.data.get("response", "")
                logger.info(f"Generated response length: {len(response)}")
                logger.info(f"FINAL RESPONSE: {response}")

                # Send final response
                await human_channel.publish(
                    TracedMessage(
                        type="agent_message",
                        source="PolicyDocumentationAgent",
                        data={
                            "message": response,
                            "connection_id": connection_id,
                            "agent": "PolicyDocumentationAgent",
                        },
                        traceparent=child_traceparent,
                        tracestate=child_tracestate,
                    )
                )

        except Exception as e:
            logger.error(f"Error in documentation processing: {e}", exc_info=True)
            error_message = "I apologize, but I encountered an error while processing your request. Please try again."

            if streaming:
                await human_stream_channel.publish(
                    TracedMessage(
                        type="agent_message_stream_end",
                        source="PolicyDocumentationAgent",
                        data={
                            "message_id": message_id,
                            "message": error_message,
                            "agent": "PolicyDocumentationAgent",
                            "connection_id": connection_id,
                        },
                        traceparent=child_traceparent,
                        tracestate=child_tracestate,
                    )
                )
            else:
                await human_channel.publish(
                    TracedMessage(
                        type="agent_message",
                        source="PolicyDocumentationAgent",
                        data={
                            "message": error_message,
                            "connection_id": connection_id,
                            "agent": "PolicyDocumentationAgent",
                        },
                        traceparent=child_traceparent,
                        tracestate=child_tracestate,
                    )
                )


async def handle_streaming_generation(
    request_id: str,
    message_id: str,
    connection_id: str,
    traceparent: str,
    tracestate: str,
) -> None:
    """Handle streaming generation responses."""
    chunk_count = 0
    final_response = ""

    # Wait for stream start
    await wait_for_response("generation_stream_start", request_id, timeout_seconds=30.0)

    while True:
        try:
            # Wait for either stream chunk or stream end
            response = await wait_for_response(
                ["generation_stream_chunk", "generation_stream_end"],
                request_id,
                timeout_seconds=60.0,
            )

            if response.data.get("type") == "generation_stream_chunk":
                chunk_count += 1
                chunk = response.data.get("chunk", "")

                await human_stream_channel.publish(
                    TracedMessage(
                        type="agent_message_stream_chunk",
                        source="PolicyDocumentationAgent",
                        data={
                            "message_chunk": chunk,
                            "message_id": message_id,
                            "chunk_index": chunk_count,
                            "connection_id": connection_id,
                        },
                        traceparent=traceparent,
                        tracestate=tracestate,
                    )
                )

            elif response.data.get("type") == "generation_stream_end":
                final_response = response.data.get("response", "")

                await human_stream_channel.publish(
                    TracedMessage(
                        type="agent_message_stream_end",
                        source="PolicyDocumentationAgent",
                        data={
                            "message_id": message_id,
                            "message": final_response,
                            "agent": "PolicyDocumentationAgent",
                            "connection_id": connection_id,
                        },
                        traceparent=traceparent,
                        tracestate=tracestate,
                    )
                )
                logger.info(f"Stream ended for message {message_id}")
                break

        except asyncio.TimeoutError:
            logger.error("Timeout waiting for generation stream")
            break
        except Exception as e:
            logger.error(f"Error in streaming generation: {e}", exc_info=True)
            break


# Global dictionary to store pending response futures
_pending_responses = {}

@policy_documentation_agent.subscribe(
    channel=internal_channel,
    auto_offset_reset="latest",
    group_id="policy_documentation_response_handler",
    filter_by_message=lambda msg: msg.get("type") in ["retrieval_response", "augmentation_response", "generation_response"],
)
async def handle_internal_responses(msg: TracedMessage) -> None:
    """Handle responses from sub-agents."""
    request_id = msg.data.get("request_id")
    if request_id and request_id in _pending_responses:
        future = _pending_responses[request_id]
        if not future.done():
            logger.info(f"Received response {msg.type} for request_id {request_id}")
            future.set_result(msg)


async def wait_for_response(
    response_type: Union[str, List[str]], request_id: str, timeout_seconds: float = 30.0
) -> TracedMessage:
    """Wait for a specific response type with the given request_id."""
    response_types = (
        response_type if isinstance(response_type, list) else [response_type]
    )
    
    logger.info(f"Waiting for response types {response_types} with request_id {request_id}")
    
    # Create a future to wait for the response
    response_future = asyncio.Future()
    _pending_responses[request_id] = response_future
    
    try:
        # Wait for the response with timeout
        response = await asyncio.wait_for(response_future, timeout=timeout_seconds)
        
        # Validate response type
        if response.type not in response_types:
            logger.warning(f"Received unexpected response type {response.type}, expected {response_types}")
            # Continue waiting for the correct response type
            return await wait_for_response(response_type, request_id, timeout_seconds)
        
        logger.info(f"Successfully received response for request_id {request_id}")
        return response
    except asyncio.TimeoutError:
        logger.error(f"Timeout waiting for {response_types} with request_id {request_id}")
        raise asyncio.TimeoutError(f"Timeout waiting for response types {response_types}")
    finally:
        # Clean up the pending response
        _pending_responses.pop(request_id, None)


@policy_documentation_agent.subscribe(
    channel=agents_channel,
    filter_by_message=lambda msg: msg.get("type") == "documentation_request",
    auto_offset_reset="latest",
    group_id="policy_documentation_agent_group",
)
@traced_handler("handle_documentation_request")
async def handle_documentation_request(msg: TracedMessage) -> None:
    """Handle incoming documentation request messages from the agents channel."""
    try:
        chat_messages: List[ChatMessage] = msg.data.get("chat_messages", [])
        connection_id: str = msg.data.get("connection_id", "unknown")
        streaming: bool = msg.data.get("streaming", True)

        if not chat_messages:
            logger.warning(f"Empty chat history for connection: {connection_id}")
            error_message = (
                "I apologize, but I didn't receive any message content to process."
            )

            if streaming:
                await human_stream_channel.publish(
                    TracedMessage(
                        type="agent_message_stream_start",
                        source="PolicyDocumentationAgent",
                        data={
                            "message_id": str(msg.id),
                            "connection_id": connection_id,
                        },
                        traceparent=msg.traceparent,
                        tracestate=msg.tracestate,
                    )
                )
                await human_stream_channel.publish(
                    TracedMessage(
                        type="agent_message_stream_end",
                        source="PolicyDocumentationAgent",
                        data={
                            "message_id": str(msg.id),
                            "message": error_message,
                            "agent": "PolicyDocumentationAgent",
                            "connection_id": connection_id,
                        },
                        traceparent=msg.traceparent,
                        tracestate=msg.tracestate,
                    )
                )
            else:
                await human_channel.publish(
                    TracedMessage(
                        type="agent_message",
                        source="PolicyDocumentationAgent",
                        data={
                            "message": error_message,
                            "connection_id": connection_id,
                            "agent": "PolicyDocumentationAgent",
                        },
                        traceparent=msg.traceparent,
                        tracestate=msg.tracestate,
                    )
                )
            return

        conversation_string = get_conversation_string(chat_messages)
        logger.info(f"Processing documentation request for connection {connection_id}")

        await process_documentation_request(
            conversation_string,
            connection_id,
            str(msg.id),
            timeout_seconds=30.0,
            streaming=streaming,
        )

    except Exception as e:
        logger.error(f"Error in PolicyDocumentationAgent: {e}", exc_info=True)
        error_message = "I apologize, but I'm having trouble processing your request right now. Please try again."

        await human_channel.publish(
            TracedMessage(
                type="agent_message",
                source="PolicyDocumentationAgent",
                data={
                    "message": error_message,
                    "connection_id": locals().get("connection_id", "unknown"),
                    "agent": "PolicyDocumentationAgent",
                },
                traceparent=msg.traceparent if "msg" in locals() else None,
                tracestate=msg.tracestate if "msg" in locals() else None,
            )
        )


@policy_documentation_agent.subscribe(channel=agents_channel)
@traced_handler("handle_others")
async def handle_other_messages(msg: TracedMessage) -> None:
    """Handle non-documentation messages received on the agent channel."""
    logger.debug("Received non-documentation message: %s", msg)


if __name__ == "__main__":

    async def run():
        from agents.policies.config import settings
        from agents.policy_documentation_agent.components.augmenting_agent import (
            augmenting_agent,
        )
        from agents.policy_documentation_agent.components.generation_agent import (
            generation_agent,
        )

        # Import sub-agents
        from agents.policy_documentation_agent.components.retrieval_agent import (
            retrieval_agent,
        )
        from libraries.dspy_set_language_model import dspy_set_language_model

        eggai_set_default_transport(lambda: KafkaTransport())

        init_telemetry("TestPolicyDocumentationAgent")
        dspy_set_language_model(settings)

        await clear_channels()

        logger.info("Starting all sub-agents...")
        
        # Start all agents concurrently
        agent_tasks = []
        
        # Start retrieval agent
        logger.info("Starting retrieval agent...")
        agent_tasks.append(asyncio.create_task(retrieval_agent.start()))
        
        # Start augmenting agent  
        logger.info("Starting augmenting agent...")
        agent_tasks.append(asyncio.create_task(augmenting_agent.start()))
        
        # Start generation agent
        logger.info("Starting generation agent...")
        agent_tasks.append(asyncio.create_task(generation_agent.start()))
        
        # Start main policy documentation agent
        logger.info("Starting main policy documentation agent...")
        agent_tasks.append(asyncio.create_task(policy_documentation_agent.start()))
        
        # Wait a moment for agents to initialize
        await asyncio.sleep(2)
        
        logger.info("All agents started successfully!")

        # Test the system with a documentation request
        logger.info("Testing integrated system with real sub-agents...")

        test_message = TracedMessage(
            type="documentation_request",
            source="TestClient",
            data={
                "chat_messages": [
                    {
                        "role": "User",
                        "content": "I need information about fire damage coverage.",
                    },
                    {
                        "role": "PolicyDocumentationAgent",
                        "content": "I can help you with information about fire damage coverage. Let me search our policy documents.",
                    },
                    {"role": "User", "content": "Is it covered under auto insurance?"},
                ],
                "connection_id": "test_connection",
                "streaming": False,
            },
        )

        await handle_documentation_request(test_message)
        
        # Stop all agents
        logger.info("Stopping all agents...")
        for task in agent_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        logger.info("Test completed!")

    asyncio.run(run())
