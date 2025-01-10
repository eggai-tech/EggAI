from lite_llm_agent import LiteLlmAgent
from shared import agents_channel

claims_agent = LiteLlmAgent(
    name="ClaimsAgent",
    system_message=(
        "You are a Claims Assistant for an insurance company, specialized in handling inquiries related to claims. "
        "Examples of claims-related topics include:\n"
        "1. Filing a new claim\n"
        "2. Checking the status of an existing claim\n"
        "3. Understanding claim coverage or payouts\n"
        "\n"
        "When responding to users:\n"
        "• Provide clear instructions on how to file a claim if needed.\n"
        "• If a claim ID is provided, use it to check or update the status.\n"
        "• Be concise but thorough in your responses.\n"
        "• Always maintain a polite and empathetic tone.\n"
        "\n"
        "If the request extends beyond your scope or requires further escalation, ask the TriageAgent to forward the conversation to the EscalationAgent."
    ),
    model="openai/gpt-3.5-turbo",
)

@claims_agent.subscribe(channel=agents_channel, filter_func=lambda msg: msg["type"] == "claims_request")
async def handle_claims_request(msg):
    try:
        chat_messages = msg["payload"]["chat_messages"]
        response = await claims_agent.completion(messages=chat_messages)
        reply = response.choices[0].message.content
        chat_messages.append({"role": "assistant", "content": reply, "agent": "ClaimsAgent"})

        await agents_channel.publish({
            "type": "response",
            "agent": "ClaimsAgent",
            "payload": {
                "chat_messages": chat_messages
            },
        })
    except Exception as e:
        print(f"[red]Error in ClaimsAgent: {e}[/red]")
