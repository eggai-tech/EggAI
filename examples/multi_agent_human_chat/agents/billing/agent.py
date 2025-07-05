import asyncio
from typing import List

from dspy import Prediction
from dspy.streaming import StreamResponse
from eggai import Agent, Channel

from libraries.channels import channels, clear_channels
from libraries.logger import get_console_logger
from libraries.tracing import TracedMessage, create_tracer, traced_handler
from libraries.tracing.init_metrics import init_token_metrics

from .config import MESSAGE_TYPE_BILLING_REQUEST, settings
from .types import ChatMessage
from .utils import get_conversation_string, process_billing_request

billing_agent = Agent(name="Billing")
logger = get_console_logger("billing_agent.handler")
agents_channel = Channel(channels.agents)
human_channel = Channel(channels.human)
human_stream_channel = Channel(channels.human_stream)
tracer = create_tracer("billing_agent")

init_token_metrics(
    port=settings.prometheus_metrics_port, application_name=settings.app_name
)

@billing_agent.subscribe(
    channel=agents_channel,
    filter_by_message=lambda msg: msg.get("type") == MESSAGE_TYPE_BILLING_REQUEST,
    auto_offset_reset="latest",
    group_id="billing_agent_group",
)
@traced_handler("handle_billing_request")
async def handle_billing_request(msg: TracedMessage) -> None:
    """Handle incoming billing request messages from the agents channel."""
    try:
        chat_messages: List[ChatMessage] = msg.data.get("chat_messages", [])
        connection_id: str = msg.data.get("connection_id", "unknown")

        if not chat_messages:
            logger.warning(f"Empty chat history for connection: {connection_id}")
            await human_channel.publish(
                TracedMessage(
                    type="agent_message",
                    source="Billing",
                    data={
                    "message": "I apologize, but I didn't receive any message content to process.",  # noqa: E501
                        "connection_id": connection_id,
                        "agent": "Billing",
                    },
                    traceparent=msg.traceparent,
                    tracestate=msg.tracestate,
                )
            )
            return

        conversation_string = get_conversation_string(chat_messages)
        logger.info(f"Processing billing request for connection {connection_id}")

        await process_billing_request(
            conversation_string,
            connection_id,
            str(msg.id),
            human_stream_channel,
            timeout_seconds=30.0,
        )

    except Exception as e:
        logger.error(f"Error in BillingAgent: {e}", exc_info=True)
        await human_channel.publish(
            TracedMessage(
                type="agent_message",
                source="BillingAgent",
                data={
                    "message": "I apologize, but I'm having trouble processing your request right now. Please try again.",  # noqa: E501
                    "connection_id": locals().get("connection_id", "unknown"),
                    "agent": "BillingAgent",
                },
                traceparent=msg.traceparent if "msg" in locals() else None,
                tracestate=msg.tracestate if "msg" in locals() else None,
            )
        )


@billing_agent.subscribe(channel=agents_channel)
async def handle_other_messages(msg: TracedMessage) -> None:
    """Handle non-billing messages received on the agent channel."""
    logger.debug("Received non-billing message: %s", msg)

if __name__ == "__main__":

    async def run():
        from libraries.dspy_set_language_model import dspy_set_language_model

        from .dspy_modules.billing import process_billing

        dspy_set_language_model(settings)

        await clear_channels()

        test_conversation = (
            "User: How much is my premium?\n"
            "BillingAgent: Could you please provide your policy number?\n"
            "User: It's B67890.\n"
        )

        logger.info("Running test query for billing agent")
        chunks = process_billing(chat_history=test_conversation)
        async for chunk in chunks:
            if isinstance(chunk, StreamResponse):
                logger.info(f"Chunk: {chunk.chunk}")
            elif isinstance(chunk, Prediction):
                logger.info(f"Final response: {chunk.final_response}")

    asyncio.run(run())
