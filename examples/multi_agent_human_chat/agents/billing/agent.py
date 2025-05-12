from eggai import Agent, Channel

from libraries.channels import channels
from libraries.logger import get_console_logger
from libraries.tracing import (
    TracedMessage,
    create_tracer,
    format_span_as_traceparent,
    traced_handler,
)

from .dspy_modules.billing import billing_optimized_dspy

billing_agent = Agent(name="BillingAgent")
logger = get_console_logger("billing_agent.handler")

agents_channel = Channel(channels.agents)
human_channel = Channel(channels.human)

tracer = create_tracer("billing_agent")


def get_conversation_string(chat_messages):
    conversation = ""
    for chat in chat_messages:
        role = chat.get("role", "User")
        conversation += f"{role}: {chat['content']}\n"
    return conversation


async def publish_agent_response(connection_id, message):
    with tracer.start_as_current_span("publish_to_human") as publish_span:
        child_traceparent, child_tracestate = format_span_as_traceparent(publish_span)
        
        await human_channel.publish(
            TracedMessage(
                type="agent_message",
                source="BillingAgent",
                data={
                    "message": message,
                    "connection_id": connection_id,
                    "agent": "BillingAgent",
                },
                traceparent=child_traceparent,
                tracestate=child_tracestate,
            )
        )


@billing_agent.subscribe(
    channel=agents_channel, 
    filter_by_message=lambda msg: msg.get("type") == "billing_request"
)
@traced_handler("handle_billing_message")
async def handle_billing_message(msg: TracedMessage):
    # Add extensive debug logging
    logger.info(f"Received billing request: {msg}")
    logger.info(f"Message type: {msg.type}")
    logger.info(f"Message data: {msg.data}")
    
    # Extract message data
    chat_messages = msg.data.get("chat_messages", [])
    connection_id = msg.data.get("connection_id", "unknown")
    logger.info(f"Processing for connection_id: {connection_id}")

    conversation_string = get_conversation_string(chat_messages)
    logger.info("Processing billing request")
    
    try:
        # Get response from DSPy model
        response = billing_optimized_dspy(chat_history=conversation_string)
        
        # Log response details
        logger.info("Sending response to user")
        logger.info(f"Response: {response[:100]}..." if len(response) > 100 else response)

        # Send response to user
        await publish_agent_response(connection_id, response)
    except Exception as e:
        # Log error details
        logger.error(f"Error in agent handler: {str(e)}", exc_info=True)
        
        # Simple error message
        await publish_agent_response(
            connection_id,
            "I apologize, but I'm unable to process your billing request at this time. Please try again later."
        )


@billing_agent.subscribe(channel=agents_channel)
@traced_handler("handle_others")
async def handle_others(msg: TracedMessage):
    # Simply log non-billing messages
    logger.debug("Received non-billing message: %s", msg)


if __name__ == "__main__":
    import asyncio
    from uuid import uuid4

    from eggai.transport import eggai_set_default_transport

    from agents.billing.config import settings
    from libraries.dspy_set_language_model import dspy_set_language_model
    from libraries.kafka_transport import create_kafka_transport
    
    # Set up transport
    eggai_set_default_transport(
        lambda: create_kafka_transport(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            ssl_cert=settings.kafka_ca_content
        )
    )
    
    dspy_set_language_model(settings)
    logger.info("Running direct test for billing agent")
    
    # Define simple test case
    async def test_billing_direct():
        test_id = str(uuid4())
        test_connection_id = f"test-{test_id}"
        
        logger.info(f"Testing with connection_id: {test_connection_id}")
        
        # Create test message
        test_msg = TracedMessage(
            id=test_id,
            type="billing_request",
            source="TestScript",
            data={
                "chat_messages": [
                    {"role": "User", "content": "How much is my premium?"},
                    {"role": "BillingAgent", "content": "Could you please provide your policy number?"},
                    {"role": "User", "content": "It's B67890."}
                ],
                "connection_id": test_connection_id,
                "message_id": test_id
            }
        )
        
        # Direct call to handler
        await handle_billing_message(test_msg)
        logger.info("Test complete")
    
    # Run the test
    asyncio.run(test_billing_direct())