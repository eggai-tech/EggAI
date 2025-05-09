import dspy
from eggai import Agent, Channel
from eggai.transport import eggai_set_default_transport

from agents.claims.dspy_modules.claims import claims_optimized_dspy
from agents.claims.dspy_modules.claims_data import (
    file_claim,
    get_claim_status,
    update_claim_info,
)
from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.kafka_transport import create_kafka_transport
from libraries.logger import get_console_logger
from libraries.tracing import (
    TracedMessage,
    TracedReAct,
    create_tracer,
    format_span_as_traceparent,
    traced_handler,
)

from .config import settings

# Set up Kafka transport
eggai_set_default_transport(
    lambda: create_kafka_transport(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        ssl_cert=settings.kafka_ca_content
    )
)

claims_agent = Agent(name="ClaimsAgent")
logger = get_console_logger("claims_agent.handler")

agents_channel = Channel("agents")
human_channel = Channel("human")

tracer = create_tracer("claims_agent")


class ClaimsAgentSignature(dspy.Signature):
    """
    You are the Claims Agent for an insurance company.

    ROLE:
    - Help customers with all claims-related questions and actions, including:
      • Filing a new claim
      • Checking the status of an existing claim
      • Explaining required documentation
      • Estimating payouts and timelines
      • Updating claim details (e.g. contact info, incident description)

    TOOLS:
    - get_claim_status(claim_number: str) -> str:
        Retrieves the current status, payment estimate, next steps, and any outstanding items for a given claim. Returns JSON string.
    - file_claim(policy_number: str, claim_details: str) -> str:
        Creates a new claim under the customer’s policy with the provided incident details. Returns JSON string of new claim.
    - update_claim_info(claim_number: str, field: str, new_value: str) -> str:
        Modifies a specified field (e.g., "address", "phone", "damage_description") on an existing claim. Returns JSON string of updated claim.

    RESPONSE FORMAT:
    - Respond in a clear, courteous, and professional tone.
    - Summarize the key information or confirm the action taken.
    - Example for status inquiry:
        “Your claim #123456 is currently ‘In Review’. We estimate a payout of $2,300 by 2025-05-15. We’re still awaiting your repair estimates—please submit them at your earliest convenience.”
    - Example for filing a claim:
        “I’ve filed a new claim #789012 under policy ABC-123. Please upload photos of the damage and any police report within 5 business days to expedite processing.”

    GUIDELINES:
    - Only invoke a tool when the user provides or requests information that requires it (a claim number for status, policy number and details to file, etc.).
    - If the user hasn’t specified a claim or policy number when needed, politely request it:
        “Could you please provide your claim number so I can check its status?”
    - Do not disclose internal processes or irrelevant details.
    - Keep answers concise—focus only on what the customer needs to know or do next.
    - Always confirm changes you make:
        “I’ve updated your mailing address on claim #123456 as requested.”

    Input Fields:
    - chat_history: str — Full conversation context.

    Output Fields:
    - final_response: str — Claims response to the user.
    """

    chat_history: str = dspy.InputField(desc="Full conversation context.")
    final_response: str = dspy.OutputField(desc="Claims response to the user.")


claims_react = TracedReAct(
    ClaimsAgentSignature,
    tools=[get_claim_status, file_claim, update_claim_info],
    name="claims_react",
    tracer=tracer,
    max_iters=5,
)


@claims_agent.subscribe(
    channel=agents_channel, filter_by_message=lambda msg: msg["type"] == "claim_request"
)
@traced_handler("handle_claims_message")
async def handle_claims_message(msg_dict):
    try:
        msg = TracedMessage(**msg_dict)
        chat_messages = msg.data.get("chat_messages")
        connection_id = msg.data.get("connection_id", "unknown")

        conversation_string = ""
        for chat in chat_messages:
            role = chat.get("role", "User")
            conversation_string += f"{role}: {chat['content']}\n"

        logger.info("Processing claims request")
        logger.debug(f"Conversation context: {conversation_string[:100]}...")

        # Use optimized DSPy module if available, otherwise fallback to TracedReAct
        try:
            logger.info("Using optimized claims module")
            final_text = claims_optimized_dspy(chat_history=conversation_string)
        except Exception as e:
            logger.warning(f"Error using optimized module: {e}, falling back to TracedReAct")
            response = claims_react(chat_history=conversation_string)
            final_text = response.final_response

        logger.info("Sending response to user")
        logger.debug(f"Response: {final_text[:100]}...")

        with tracer.start_as_current_span("publish_to_human") as publish_span:
            child_traceparent, child_tracestate = format_span_as_traceparent(publish_span)
            await human_channel.publish(
                TracedMessage(
                    type="agent_message",
                    source="ClaimsAgent",
                    data={
                        "message": final_text,
                        "connection_id": connection_id,
                        "agent": "ClaimsAgent",
                    },
                    traceparent=child_traceparent,
                    tracestate=child_tracestate,
                )
            )
    except Exception as e:
        logger.error(f"Error in ClaimsAgent: {e}", exc_info=True)


@claims_agent.subscribe(channel=agents_channel)
async def handle_others(msg: TracedMessage):
    logger.debug("Received message: %s", msg)


if __name__ == "__main__":
    language_model = dspy_set_language_model(settings)
    test_conversation = (
        "User: Hi, I'd like to file a new claim.\n"
        "ClaimsAgent: Certainly! Could you provide your policy number and incident details?\n"
        "User: Policy A12345, my car was hit at a stop sign.\n"
    )

    logger.info("Running test query for claims agent")
    result = claims_react(chat_history=test_conversation)
    logger.info(f"Test response: {result.final_response}")
