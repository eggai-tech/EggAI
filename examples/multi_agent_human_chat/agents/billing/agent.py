import json
import dspy
from eggai import Channel, Agent
from eggai.transport import eggai_set_default_transport

from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.tracing import TracedReAct, create_tracer, TracedMessage, traced_handler, format_span_as_traceparent
from libraries.logger import get_console_logger
from libraries.kafka_transport import create_kafka_transport
from .config import settings
from agents.billing.dspy_modules.billing import billing_optimized_dspy
from agents.billing.dspy_modules.billing_data import get_billing_info, update_billing_info, BILLING_DATABASE

# Set up Kafka transport
eggai_set_default_transport(
    lambda: create_kafka_transport(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        ssl_cert=settings.kafka_ca_content
    )
)

billing_agent = Agent(name="BillingAgent")
logger = get_console_logger("billing_agent.handler")

agents_channel = Channel("agents")
human_channel = Channel("human")

tracer = create_tracer("billing_agent")

class BillingAgentSignature(dspy.Signature):
    """
    You are the Billing Agent for an insurance company.

    ROLE:
      - Assist customers with billing-related inquiries such as due amounts, billing cycles, payment statuses, etc.
      - Retrieve or update billing information as needed.
      - Provide polite, concise, and helpful answers.

    TOOLS:
      - get_billing_info(policy_number): Retrieves billing information (amount due, due date, payment status, etc.).
      - update_billing_info(policy_number, field, new_value): Updates a particular field in the billing record.

    RESPONSE FORMAT:
      - Provide a concise, courteous message summarizing relevant billing info using specific patterns:
        - For current balance inquiries: "Your current amount due is $X.XX with a due date of YYYY-MM-DD. Your status is 'Status'."
        - For next payment info: "Your next payment of $X.XX is due on YYYY-MM-DD, and your current status is 'Status'."
        - For billing cycle inquiries: "Your current billing cycle is 'Cycle' with the next payment of $X.XX due on YYYY-MM-DD."

    GUIDELINES:
      - Maintain a polite, professional tone.
      - Only use the tools if necessary (e.g., if the user provides a policy number and requests an update or info).
      - If a policy number is missing or unclear, politely ask for it.
      - Avoid speculation or divulging irrelevant details.
      - IMPORTANT: When a user asks "How much do I owe", always use the "current amount due" format.
      - IMPORTANT: When a user asks about billing date, use the "next payment" format.
      - IMPORTANT: When a user mentions "billing cycle", use the "billing cycle" format.
      - IMPORTANT: Dates MUST be in the format YYYY-MM-DD. For example, use "2025-03-15" instead of "March 15th, 2025".

    Input Fields:
      - chat_history: A string containing the full conversation thus far.

    Output Fields:
      - final_response: The final text answer to the user regarding their billing inquiry.
    """

    chat_history: str = dspy.InputField(desc="Full conversation context.")
    final_response: str = dspy.OutputField(desc="Billing response to the user.")


# Create TracedReAct instance with the traced tools from billing_data
billing_react = TracedReAct(
    BillingAgentSignature,
    tools=[get_billing_info, update_billing_info],
    name="billing_react",
    tracer=tracer,
    max_iters=5,
)


@billing_agent.subscribe(
    channel=agents_channel, filter_by_message=lambda msg: msg["type"] == "billing_request"
)
@traced_handler("handle_billing_message")
async def handle_billing_message(msg_dict):
    try:
        msg = TracedMessage(**msg_dict)
        chat_messages = msg.data.get("chat_messages")
        connection_id = msg.data.get("connection_id", "unknown")

        conversation_string = ""
        for chat in chat_messages:
            role = chat.get("role", "User")
            conversation_string += f"{role}: {chat['content']}\n"

        logger.info("Processing billing request")
        logger.debug(f"Conversation context: {conversation_string[:100]}...")

        # Use optimized DSPy module if available, otherwise fallback to TracedReAct
        try:
            logger.info("Using optimized billing module")
            final_text = billing_optimized_dspy(chat_history=conversation_string)
        except Exception as e:
            logger.warning(f"Error using optimized module: {e}, falling back to TracedReAct")
            response = billing_react(chat_history=conversation_string)
            final_text = response.final_response
        
        logger.info("Sending response to user")
        logger.info(f"Response: {final_text[:100]}...")

        # Create a child span for the publish operation
        with tracer.start_as_current_span("publish_to_human") as publish_span:
            # Get updated trace context from current span
            child_traceparent, child_tracestate = format_span_as_traceparent(publish_span)
            await human_channel.publish(
                TracedMessage(
                    type="agent_message",
                    source="BillingAgent",
                    data={
                        "message": final_text,
                        "connection_id": connection_id,
                        "agent": "BillingAgent",
                    },
                    traceparent=child_traceparent,
                    tracestate=child_tracestate,
                )
            )
    except Exception as e:
        logger.error(f"Error in BillingAgent: {e}", exc_info=True)

@billing_agent.subscribe(channel=agents_channel)
async def handle_others(msg: TracedMessage):
    logger.debug("Received message: %s", msg)


if __name__ == "__main__":
    language_model = dspy_set_language_model(settings)
    test_conversation = (
        "User: Hi, I'd like to know my next billing date.\n"
        "BillingAgent: Sure! Please provide your policy number.\n"
        "User: It's B67890.\n"
    )

    logger.info("Running test query")
    result = billing_react(chat_history=test_conversation)
    logger.info(f"Test response: {result.final_response}")