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
    model="openai/gpt-3.5-turbo"
)


@support_agent.tool()
def get_knowledge(query):
    """
    Get knowledge from a knowledge base.

    :param query: The query to search for in the knowledge base, can be return_policy, shipping_times, or product_information, otherwise needs to escalate.
    """
    print(f"Querying knowledge base for: {query}")
    knowledge_base = {
        "return_policy": "Our return policy is 30 days from the date of purchase. Items must be in their original condition.",
        "shipping_times": "Shipping times vary based on the shipping method selected. Standard shipping takes 3-5 business days.",
        "product_information": "Our products are made from high-quality materials and are designed to last for years."
    }
    return query in knowledge_base and knowledge_base[query] or "escalate"


# Subscribe SupportAgent to handle customer inquiries
@support_agent.subscribe(channel=humans_channel, filter_func=lambda msg: msg["type"] == "customer_inquiry")
async def handle_inquiry(msg):
    try:
        print(f"Handling customer inquiry: {msg['payload']}")
        response = await support_agent.completion(messages=[{
            "role": "user",
            "content": "User wrote: " + msg["payload"] + ". Whats your response? Please return it as JSON."
        }])

        try:
            reply = json.loads(response.choices[0].message.content.strip())
        except json.JSONDecodeError as e:
            print("Failed to decode response from SupportAgent, message was: ", response.choices[0].message.content.strip())
            return

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
    except Exception as e:
        print("Error handling inquiry:", e)
