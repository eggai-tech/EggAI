import json
import threading
from typing import Optional, Literal
from opentelemetry import trace
import dspy
from dotenv import load_dotenv
from eggai import Channel, Agent
from eggai.schemas import Message
from libraries.tracing import TracedReAct, traced_asyncify

from agents.policies.rag.retrieving import retrieve_policies

policies_agent = Agent(name="PoliciesAgent")

agents_channel = Channel("agents")
human_channel = Channel("human")

tracer = trace.get_tracer("policies_agent")

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
        print(f"[Tool] Retrieving policy information for query: {query}, category: {policy_category}")
        thread = ThreadWithResult(target=retrieve_policies, args=(query, policy_category))
        thread.start()
        results = thread.join()
        if results:
            print(f"[Tool] Found documentation: {len(results)} results.")
            return json.dumps([results[0], results[1]])
        return "Documentation not found."
    except Exception as e:
        print(f"[Tool] Error retrieving policy documentation: {e}")
        return "Error retrieving documentation."


@tracer.start_as_current_span("take_policy_by_number_from_database")
def take_policy_by_number_from_database(policy_number: str) -> str:
    """
    Retrieves detailed information for a given policy number.
    Returns a JSON-formatted string if the policy is found, or "Policy not found." otherwise.
    """
    print(f"[Tool] Retrieving policy details for policy number: {policy_number}")
    for policy in policies_database:
        if policy["policy_number"] == policy_number.strip():
            return json.dumps(policy)
    return "Policy not found."


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

    policy_category: Optional[PolicyCategory] = dspy.OutputField(desc="Policy category.")
    policy_number: Optional[str] = dspy.OutputField(desc="Policy number.")
    documentation_summarized_output: Optional[str] = dspy.OutputField(desc="Policy documentation summarized output.")
    documentation_reference: Optional[str] = dspy.OutputField(desc="Reference on the documentation if found (e.g. Section 3.1 or Section 4.5.6).")

    final_response: str = dspy.OutputField(desc="Final response message to the user.")
    final_response_with_documentation_reference: Optional[str] = dspy.OutputField(desc="Final response message to the user with documentation reference.")


policies_react = traced_asyncify(
    TracedReAct(
        PolicyAgentSignature, 
        tools=[take_policy_by_number_from_database, query_policy_documentation], 
        max_iters=7,
        name="policies_react",
        tracer=tracer
    ),
    name="policies_react_async",
    tracer=tracer
)


@policies_agent.subscribe(
    channel=agents_channel, filter_func=lambda msg: msg.get("type") == "policy_request"
)
@tracer.start_as_current_span("handle_policy_request")
async def handle_policy_request(msg_dict):
    try:
        msg = Message(**msg_dict)
        chat_messages = msg.data["chat_messages"]
        conversation_string = ""
        for chat in chat_messages:
            role = chat.get("role", "User")
            conversation_string += f"{role}: {chat['content']}\n"
        response = await policies_react(chat_history=conversation_string)
        final_response = response.final_response
        if "final_response_with_documentation_reference" in response and response.final_response_with_documentation_reference:
            final_response = response.final_response_with_documentation_reference

        print("Additional data: ", response)

        await human_channel.publish(
            Message(
                type="agent_message",
                source="PoliciesAgent",
                data={
                    "message": final_response,
                    "connection_id": msg.data.get("connection_id"),
                    "agent": "PoliciesAgent",
                }
            )
        )
    except Exception as e:
        print(f"Error in PoliciesAgent: {e}")


if __name__ == "__main__":
    load_dotenv()
    language_model = dspy.LM("openai/gpt-4o-mini")
    dspy.configure(lm=language_model)

    # EXAMPLE FOR RAG:
    # Hey, I need an info on my Policy C24680, a fire ruined my kitchen table, can i get a refund?
    # Hey, I need an info on my Policy C24680, it is Fire Damage Coverage included?

    print(
        policies_react(
            chat_history="""
    User: I need information about my policy.
    PoliciesAgent: Sure, I can help with that. Could you please provide me with your policy number?
    User: My policy number is A12345
    """
        ).final_response
    )
