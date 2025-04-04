import json
import threading
from typing import Optional, Literal

from eggai.transport import KafkaTransport, eggai_set_default_transport
from opentelemetry import trace
import dspy
from eggai import Channel, Agent
from libraries.tracing import TracedReAct, TracedMessage, traced_handler, format_span_as_traceparent
from libraries.logger import get_console_logger

from agents.policies.rag.retrieving import retrieve_policies
from agents.policies.config import settings


def create_kafka_transport():
    return KafkaTransport(
        bootstrap_servers=settings.kafka_bootstrap_servers
    )

eggai_set_default_transport(create_kafka_transport)

policies_agent = Agent(name="PoliciesAgent")

agents_channel = Channel("agents")
human_channel = Channel("human")

tracer = trace.get_tracer("policies_agent")
logger = get_console_logger("policies_agent.handler")

PolicyCategory = Literal["auto", "life", "home", "health"]

policies_database = [
    {
        "policy_number": "A12345",
        "name": "John Doe",
        "policy_category": "auto",
        "premium_amount": 500,
        "due_date": "2025-03-01",
    },
    {
        "policy_number": "B67890",
        "name": "Jane Smith",
        "policy_category": "life",
        "premium_amount": 300,
        "due_date": "2025-03-01",
    },
    {
        "policy_number": "C24680",
        "name": "Alice Johnson",
        "policy_category": "home",
        "premium_amount": 400,
        "due_date": "2025-03-01",
    },
]


class ThreadWithResult(threading.Thread):
    def __init__(self, target, args=(), kwargs=None):
        super().__init__(target=target, args=args, kwargs=kwargs or {})
        self._result = None

    def run(self):
        if self._target:
            self._result = self._target(*self._args, **self._kwargs)

    def join(self, *args):
        super().join(*args)
        return self._result


@tracer.start_as_current_span("query_policy_documentation")
def query_policy_documentation(query: str, policy_category: PolicyCategory) -> str:
    try:
        logger.info(
            f"Retrieving policy information for query: '{query}', category: '{policy_category}'"
        )
        thread = ThreadWithResult(
            target=retrieve_policies, args=(query, policy_category)
        )
        thread.start()
        results = thread.join()

        if results:
            logger.info(f"Found documentation: {len(results)} results")
            if len(results) >= 2:
                return json.dumps([results[0], results[1]])
            return json.dumps(results)

        logger.warning(
            f"No documentation found for query: '{query}', category: '{policy_category}'"
        )
        return "Documentation not found."
    except Exception as e:
        logger.error(f"Error retrieving policy documentation: {e}", exc_info=True)
        return "Error retrieving documentation."


@tracer.start_as_current_span("take_policy_by_number_from_database")
def take_policy_by_number_from_database(policy_number: str) -> str:
    """
    Retrieves detailed information for a given policy number.
    Returns a JSON-formatted string if the policy is found, or "Policy not found." otherwise.
    """
    logger.info(f"Retrieving policy details for policy number: '{policy_number}'")

    if not policy_number:
        logger.warning("Empty policy number provided")
        return "Invalid policy number format."

    try:
        cleaned_policy_number = policy_number.strip()
        for policy in policies_database:
            if policy["policy_number"] == cleaned_policy_number:
                logger.info(
                    f"Found policy: {policy['policy_number']} for {policy['name']}"
                )
                return json.dumps(policy)

        logger.warning(f"Policy not found: '{policy_number}'")
        return "Policy not found."
    except Exception as e:
        logger.error(f"Error retrieving policy by number: {e}", exc_info=True)
        return f"Error retrieving policy: {str(e)}"


class PolicyAgentSignature(dspy.Signature):
    """
    This signature defines the input and output for processing policy inquiries
    using a simple ReACT loop.

    Role:
    - You are the Policy Agent for an insurance company. Your job is to help users
      with inquiries about insurance policies (coverage details, premiums, etc.).
    - If the necessary policy details (e.g. a policy number) are provided, use a tool
      to retrieve policy information, it will return a JSON-formatted string if the policy is found with fields like name, premium amount, due date and policy category.
    - You can also use a tool query_policy_documentation for specific questions, you can query documentation about a policy by providing a query and a policy category retrieved from database.
    - If not, ask for the missing information.
    - Maintain a polite, concise, and helpful tone.
    - If documentation is found, please include it in the final response as summarized information, specifying the document reference formatted with parenthesis and an identifier POLICY_CATEGORY#REFERENCE (see home#3.1) or (see home#4.5.6).
    """

    chat_history: str = dspy.InputField(desc="Full conversation context.")

    policy_category: Optional[PolicyCategory] = dspy.OutputField(
        desc="Policy category."
    )
    policy_number: Optional[str] = dspy.OutputField(desc="Policy number.")
    documentation_summarized_output: Optional[str] = dspy.OutputField(
        desc="Policy documentation summarized output."
    )
    documentation_reference: Optional[str] = dspy.OutputField(
        desc="Reference on the documentation if found (e.g. Section 3.1 or Section 4.5.6)."
    )

    final_response: str = dspy.OutputField(desc="Final response message to the user.")
    final_response_with_documentation_reference: Optional[str] = dspy.OutputField(
        desc="Final response message to the user with documentation reference."
    )


policies_react = dspy.asyncify(
    TracedReAct(
        PolicyAgentSignature,
        tools=[take_policy_by_number_from_database, query_policy_documentation],
        max_iters=7,
        name="policies_react",
        tracer=tracer,
    )
)


@policies_agent.subscribe(
    channel=agents_channel, filter_by_message=lambda msg: msg.get("type") == "policy_request"
)
@traced_handler("handle_policy_request")
async def handle_policy_request(msg_dict):
    try:
        msg = TracedMessage(**msg_dict)
        chat_messages = msg.data["chat_messages"]
        connection_id = msg.data.get("connection_id", "unknown")

        logger.info(f"Received policy request from connection {connection_id}")

        # Combine chat history
        conversation_string = ""
        for chat in chat_messages:
            role = chat.get("role", "User")
            conversation_string += f"{role}: {chat['content']}\n"

        logger.debug(f"Conversation context: {conversation_string[:100]}...")

        # Process with DSPy module
        logger.info("Processing with policies_react module")
        response = await policies_react(chat_history=conversation_string)

        # Extract final response
        final_response = response.final_response
        if (
            "final_response_with_documentation_reference" in response
            and response.final_response_with_documentation_reference
        ):
            final_response = response.final_response_with_documentation_reference
            logger.info("Using response with documentation references")

        # Log additional information
        if hasattr(response, "policy_number") and response.policy_number:
            logger.info(f"Policy number identified: {response.policy_number}")
        if hasattr(response, "policy_category") and response.policy_category:
            logger.info(f"Policy category identified: {response.policy_category}")
        if (
            hasattr(response, "documentation_reference")
            and response.documentation_reference
        ):
            logger.info(f"Documentation reference: {response.documentation_reference}")

        # Send response
        logger.info(f"Sending response to user: {final_response[:50]}...")
        with tracer.start_as_current_span("publish_to_human") as publish_span:
            child_traceparent, child_tracestate = format_span_as_traceparent(publish_span)
            await human_channel.publish(
                TracedMessage(
                    type="agent_message",
                    source="PoliciesAgent",
                    data={
                        "message": final_response,
                        "connection_id": connection_id,
                        "agent": "PoliciesAgent",
                    },
                    traceparent=child_traceparent,
                    tracestate=child_tracestate,
                )
            )
            logger.debug("Response sent successfully")
    except Exception as e:
        logger.error(f"Error in PoliciesAgent: {e}", exc_info=True)
        # Try to notify the user of the error
        try:
            with tracer.start_as_current_span("publish_to_human") as publish_span:
                child_traceparent, child_tracestate = format_span_as_traceparent(publish_span)
                await human_channel.publish(
                    TracedMessage(
                        type="agent_message",
                        source="PoliciesAgent",
                        data={
                            "message": "I'm sorry, I encountered an error while processing your request. Please try again.",
                            "connection_id": msg.data.get("connection_id"),
                            "agent": "PoliciesAgent",
                        },
                        traceparent=child_traceparent,
                        tracestate=child_tracestate,
                    )
                )
        except Exception as notify_error:
            logger.error(f"Failed to send error notification: {notify_error}")


@policies_agent.subscribe(channel=agents_channel)
async def handle_others(msg: TracedMessage):
    logger.debug("Received message: %s", msg)

if __name__ == "__main__":
    logger.info("Running policies agent as script")

    language_model = dspy.LM(settings.language_model, cache=settings.cache_enabled)
    logger.info(f"Configured language model: {settings.language_model}")

    dspy.configure(lm=language_model)

    # Test policy request
    test_conversation = """
    User: I need information about my policy.
    PoliciesAgent: Sure, I can help with that. Could you please provide me with your policy number?
    User: My policy number is A12345
    """

    logger.info("Running test query")
    response = policies_react(chat_history=test_conversation)
    logger.info(f"Test response: {response.final_response}")

    # Examples for reference:
    # Hey, I need an info on my Policy C24680, a fire ruined my kitchen table, can i get a refund?
    # Hey, I need an info on my Policy C24680, it is Fire Damage Coverage included?


