import json

from eggai import Channel
from lite_llm_agent import LiteLlmAgent

agents_channel = Channel("agents")
humans_channel = Channel("humans")

# Initialize SupportAgent with a system prompt guiding its decision-making
support_agent = LiteLlmAgent(
    name="SupportAgent",
    system_message=(
        "You are a customer support assistant. Answer the customer's question if it is related to general inquiries like "
        "return policies, shipping times, product information, etc. If the question is complex or beyond your knowledge, "
        "respond by escalating the issue to a specialist. Your response should be a json object with the key 'response'."
        "The value should be the response to the customer. If you need to escalate the issue, respond with {\"response\": \"escalate\"}."
    ),
    model="openai/gpt-4"
)


@support_agent.tool(name="GetKnowledge", description="Get knowledge from a knowledge base.")
def get_knowledge(query):
    """
    Get knowledge from a knowledge base.

    :param query: The query to search for in the knowledge base, can be return_policy, shipping_times, or product_information. Otherwise need to escalate.
    """
    print(f"Querying knowledge base for: {query}")
    knowledge_base = {
        "return_policy": "Our return policy is 30 days from the date of purchase. Items must be in their original condition.",
        "shipping_times": "Shipping times vary based on the shipping method selected. Standard shipping takes 3-5 business days.",
        "product_information": "Our products are made from high-quality materials and are designed to last for years."
    }
    return knowledge_base.get(query, "escalate")


# Subscribe SupportAgent to handle customer inquiries
@support_agent.subscribe(channel=humans_channel, filter_func=lambda msg: msg["type"] == "customer_inquiry")
async def handle_inquiry(msg):
    print(f"Handling customer inquiry: {msg['payload']}")
    response = await support_agent.completion(messages=[{
        "role": "user",
        "content": msg["payload"]
    }])

    reply = json.loads(response.choices[0].message.content)

    print(f"Response from SupportAgent: {reply}")

    if reply.get("response") == "escalate":
        print("Escalating issue to EscalationAgent...")
        # Escalate the issue to EscalationAgent
        await agents_channel.publish({
            "type": "escalate_request",
            "payload": msg["payload"]
        })
    else:
        print("Responding directly to the customer...")
        # Respond directly to the customer
        await humans_channel.publish({
            "type": "response",
            "payload": reply
        })
