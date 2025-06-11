from typing import AsyncIterable, Optional, Union

import dspy
from dspy import Prediction
from dspy.streaming import StreamResponse
from eggai import Agent, Channel

from agents.policies.types import ModelConfig
from libraries.channels import channels
from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.logger import get_console_logger
from libraries.tracing import TracedMessage, create_tracer, traced_handler
from libraries.tracing.dspy import TracedChainOfThought, traced_dspy_function

generation_agent = Agent(name="GenerationAgent")
logger = get_console_logger("policy_documentation_agent.generation")
tracer = create_tracer("policy_documentation_agent", "generation")
internal_channel = Channel(channels.internal)


class PolicyDocumentationSignature(dspy.Signature):
    """
    You are an expert policy documentation assistant. Your role is to provide accurate,
    helpful responses based on the provided policy information and conversation context.

    RESPONSIBILITIES:
    - Generate clear, accurate responses based on policy documents
    - Maintain a professional and helpful tone
    - Cite specific policy sections when relevant
    - Clearly state when information is not available
    - Stay focused on the user's specific question

    RESPONSE GUIDELINES:
    - Use only the information provided in the policy context
    - If information is missing, clearly state this limitation
    - Include policy section citations when possible (e.g., "see section 3.1")
    - Be specific and actionable in your responses
    - Maintain consistency with policy language and terminology

    CRITICAL REQUIREMENTS:
    - Never make up or assume policy details not in the provided context
    - Always acknowledge the source of your information
    - If multiple policies are relevant, distinguish between them clearly
    - Use professional, insurance industry appropriate language
    """

    augmented_context: str = dspy.InputField(
        desc="Policy context with relevant documents and conversation history"
    )

    response: str = dspy.OutputField(
        desc="Generated response based on policy documentation"
    )


# Initialize the generation model with tracing
generation_model = TracedChainOfThought(
    PolicyDocumentationSignature, name="policy_documentation_generation", tracer=tracer
)


@traced_dspy_function(name="generate_response")
def generate_response(
    augmented_context: str, config: Optional[ModelConfig] = None
) -> str:
    """Generate a response based on augmented policy context."""
    config = config or ModelConfig()

    if not augmented_context or len(augmented_context.strip()) < 10:
        logger.warning("Insufficient context for response generation")
        return "I apologize, but I don't have enough information to provide a helpful response. Please provide more details about your policy question."

    try:
        logger.info(f"Generating response for context length: {len(augmented_context)}")
        result = generation_model(augmented_context=augmented_context)

        if hasattr(result, "response") and result.response:
            logger.info(f"Generated response length: {len(result.response)}")
            return result.response.strip()
        else:
            logger.warning("Model returned empty response")
            return "I apologize, but I wasn't able to generate a response based on the available information. Please try rephrasing your question."

    except Exception as e:
        logger.error(f"Error generating response: {e}", exc_info=True)
        return "I apologize, but I encountered an error while processing your request. Please try again."


@traced_dspy_function(name="generate_streaming_response")
def generate_streaming_response(
    augmented_context: str, config: Optional[ModelConfig] = None
) -> AsyncIterable[Union[StreamResponse, Prediction]]:
    """Generate a streaming response based on augmented policy context."""
    config = config or ModelConfig()

    if not augmented_context or len(augmented_context.strip()) < 10:
        logger.warning("Insufficient context for streaming response generation")

        # For streaming, we need to handle this differently
        # Return a simple async generator that yields the error message
        async def error_stream():
            yield StreamResponse(
                chunk="I apologize, but I don't have enough information to provide a helpful response."
            )
            yield Prediction(
                response="I apologize, but I don't have enough information to provide a helpful response."
            )

        return error_stream()

    logger.info(
        f"Generating streaming response for context length: {len(augmented_context)}"
    )

    # Create a streaming version of the generation model
    return dspy.streamify(
        generation_model,
        stream_listeners=[
            dspy.streaming.StreamListener(signature_field_name="response"),
        ],
        include_final_prediction_in_output_stream=True,
        is_async_program=False,
        async_streaming=True,
    )(augmented_context=augmented_context)


@generation_agent.subscribe(
    channel=internal_channel,
    filter_by_message=lambda msg: msg.get("type") == "generation_request",
    auto_offset_reset="latest",
    group_id="generation_agent_group",
)
@traced_handler("handle_generation_request")
async def handle_generation_request(msg: TracedMessage) -> None:
    """Handle generation requests from other components."""
    try:
        augmented_context = msg.data.get("augmented_context", "")
        request_id = msg.data.get("request_id", "")
        streaming = msg.data.get("streaming", False)
        config_data = msg.data.get("config", {})

        # Create config from data
        config = ModelConfig(
            timeout_seconds=config_data.get("timeout_seconds", 30.0),
            truncation_length=config_data.get("truncation_length", 8000),
        )

        if not augmented_context:
            logger.warning("Empty context in generation request")
            await internal_channel.publish(
                TracedMessage(
                    type="generation_response",
                    source="GenerationAgent",
                    data={
                        "request_id": request_id,
                        "response": "",
                        "error": "Empty context provided",
                    },
                    traceparent=msg.traceparent,
                    tracestate=msg.tracestate,
                )
            )
            return

        logger.info(f"Processing generation request: {request_id}")

        if streaming:
            # Handle streaming response
            await internal_channel.publish(
                TracedMessage(
                    type="generation_stream_start",
                    source="GenerationAgent",
                    data={
                        "request_id": request_id,
                    },
                    traceparent=msg.traceparent,
                    tracestate=msg.tracestate,
                )
            )

            chunks = generate_streaming_response(augmented_context, config)
            chunk_count = 0
            final_response = ""

            try:
                async for chunk in chunks:
                    if isinstance(chunk, StreamResponse):
                        chunk_count += 1
                        await internal_channel.publish(
                            TracedMessage(
                                type="generation_stream_chunk",
                                source="GenerationAgent",
                                data={
                                    "request_id": request_id,
                                    "chunk": chunk.chunk,
                                    "chunk_index": chunk_count,
                                },
                                traceparent=msg.traceparent,
                                tracestate=msg.tracestate,
                            )
                        )
                    elif isinstance(chunk, Prediction):
                        final_response = (
                            chunk.response if hasattr(chunk, "response") else ""
                        )

                await internal_channel.publish(
                    TracedMessage(
                        type="generation_stream_end",
                        source="GenerationAgent",
                        data={
                            "request_id": request_id,
                            "response": final_response,
                        },
                        traceparent=msg.traceparent,
                        tracestate=msg.tracestate,
                    )
                )

            except Exception as e:
                logger.error(f"Error in streaming generation: {e}", exc_info=True)
                await internal_channel.publish(
                    TracedMessage(
                        type="generation_stream_end",
                        source="GenerationAgent",
                        data={
                            "request_id": request_id,
                            "response": "I apologize, but I encountered an error while generating the response.",
                            "error": str(e),
                        },
                        traceparent=msg.traceparent,
                        tracestate=msg.tracestate,
                    )
                )
        else:
            # Handle non-streaming response
            response = generate_response(augmented_context, config)

            await internal_channel.publish(
                TracedMessage(
                    type="generation_response",
                    source="GenerationAgent",
                    data={
                        "request_id": request_id,
                        "response": response,
                    },
                    traceparent=msg.traceparent,
                    tracestate=msg.tracestate,
                )
            )

        logger.info(f"Completed generation request: {request_id}")

    except Exception as e:
        logger.error(f"Error in generation agent: {e}", exc_info=True)
        await internal_channel.publish(
            TracedMessage(
                type="generation_response",
                source="GenerationAgent",
                data={
                    "request_id": msg.data.get("request_id", ""),
                    "response": "",
                    "error": str(e),
                },
                traceparent=msg.traceparent if "msg" in locals() else None,
                tracestate=msg.tracestate if "msg" in locals() else None,
            )
        )


if __name__ == "__main__":
    import asyncio

    from agents.policies.config import settings

    async def run():
        dspy_set_language_model(settings)

        logger.info("Running generation agent as script")

        test_context = """Query: Is fire damage covered?
Relevant Policy Information:

--- Policy AUTO (Relevance: 0.950) ---
Fire damage is covered under comprehensive insurance with a $500 deductible.

--- Policy HOME (Relevance: 0.870) ---
Home insurance covers fire damage with full replacement cost coverage.

Instructions:
- Use only the information provided in the policy documents above
- If the information is not available in the provided policies, clearly state this
- Be specific and cite which policy section your answer comes from when possible
- Maintain a helpful and professional tone"""

        result = generate_response(test_context)
        logger.info(f"Generated result: {result}")

    asyncio.run(run())
