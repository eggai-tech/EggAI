import json
import dspy
from eggai import Channel, Agent
from eggai.transport import eggai_set_default_transport

from libraries.dspy_set_language_model import dspy_set_language_model
from libraries.tracing import TracedReAct, create_tracer, TracedMessage, traced_handler, format_span_as_traceparent
from libraries.logger import get_console_logger
from libraries.kafka_transport import create_kafka_transport
from .config import settings
from agents.claims.dspy_modules.claims import claims_optimized_dspy

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


# Sample in-memory claims database
claims_database = [
    {
        "claim_number": "1001",
        "policy_number": "A12345",
        "status": "In Review",
        "estimate": 2300.0,
        "estimate_date": "2025-05-15",
        "next_steps": "Submit repair estimates",
        "outstanding_items": ["Repair estimates"]
    },
    {
        "claim_number": "1002",
        "policy_number": "B67890",
        "status": "Approved",
        "estimate": 1500.0,
        "estimate_date": "2025-04-20",
        "next_steps": "Processing payment",
        "outstanding_items": []
    },
    {
        "claim_number": "1003",
        "policy_number": "C24680",
        "status": "Pending Documentation",
        "estimate": None,
        "estimate_date": None,
        "next_steps": "Upload photos and police report",
        "outstanding_items": ["Photos", "Police report"]
    },
]


@tracer.start_as_current_span("get_claim_status")
def get_claim_status(claim_number: str) -> str:
    """
    Retrieve claim status and details for a given claim_number.

    Args:
        claim_number (str): The unique identifier of the claim to retrieve.

    Returns:
        str: JSON string containing claim data or an error message.
    """
    logger.info(f"Retrieving claim status for claim number: {claim_number}")
    for record in claims_database:
        if record["claim_number"] == claim_number.strip():
            logger.info(f"Found claim record {claim_number}")
            return json.dumps(record)
    logger.warning(f"Claim not found: {claim_number}")
    return json.dumps({"error": "Claim not found."})


@tracer.start_as_current_span("file_claim")
def file_claim(policy_number: str, claim_details: str) -> str:
    """
    File a new claim under the given policy with provided details.

    Args:
        policy_number (str): The policy number under which to file the claim.
        claim_details (str): Description of the incident or damage.

    Returns:
        str: JSON string of the newly created claim record.
    """
    logger.info(f"Filing new claim for policy: {policy_number}")
    existing = [int(r["claim_number"]) for r in claims_database]
    new_number = str(max(existing) + 1 if existing else 1001)
    new_claim = {
        "claim_number": new_number,
        "policy_number": policy_number.strip(),
        "status": "Filed",
        "estimate": None,
        "estimate_date": None,
        "next_steps": "Provide documentation",
        "outstanding_items": ["Photos", "Police report"],
        "details": claim_details
    }
    claims_database.append(new_claim)
    logger.info(f"New claim filed: {new_number}")
    return json.dumps(new_claim)


@tracer.start_as_current_span("update_claim_info")
def update_claim_info(claim_number: str, field: str, new_value: str) -> str:
    """
    Update a given field in the claim record for the specified claim_number.

    Args:
        claim_number (str): The unique identifier of the claim to update.
        field (str): The field name to modify in the claim record.
        new_value (str): The new value to set for the specified field.

    Returns:
        str: JSON string of the updated claim record or an error message.
    """
    logger.info(f"Updating claim {claim_number}: {field} -> {new_value}")
    for record in claims_database:
        if record["claim_number"] == claim_number.strip():
            if field in record:
                try:
                    if field == "estimate":
                        record[field] = float(new_value)
                    elif field == "outstanding_items":
                        record[field] = [item.strip() for item in new_value.split(",")]
                    else:
                        record[field] = new_value
                except ValueError:
                    error_msg = f"Invalid value for {field}: {new_value}"
                    logger.error(error_msg)
                    return json.dumps({"error": error_msg})
                logger.info(f"Successfully updated {field} for claim {claim_number}")
                return json.dumps(record)
            logger.warning(f"Field '{field}' not in claim record.")
            return json.dumps({"error": f"Field '{field}' not in claim record."})

    logger.warning(f"Cannot update claim {claim_number}: not found")
    return json.dumps({"error": "Claim not found."})


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
