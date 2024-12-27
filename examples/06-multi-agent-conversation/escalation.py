from lite_llm_agent import LiteLlmAgent
from shared import agents_channel

escalation_agent = LiteLlmAgent(
    name="EscalationAgent",
    system_message=(
        "You are an Escalation Assistant for an insurance customer service system. "
        "You handle cases that cannot be resolved by the ClaimsAgent or PolicyAgent. "
        "\n\n"
        "Your tasks:\n"
        "• Provide a response politely informing the user that their issue will be escalated to a human support representative.\n"
        "• Generate a ticket ID for reference (e.g., ESC-123456).\n"
        "• Indicate the department or team (e.g., 'Technical Support', 'Billing', etc.) that will handle the issue.\n"
        "\n"
        "Example response:\n"
        "    'We have created a support ticket ESC-123456 for your issue. Our Technical Support team will reach out to you shortly.'\n"
        "Maintain a courteous tone and avoid providing any incorrect or speculative information. "
    ),
    model="gpt-3.5-turbo-1106"
)

@escalation_agent.subscribe(channel=agents_channel, filter_func=lambda msg: msg["type"] == "escalation_request")
async def handle_escalation_request(msg):
    try:
        chat_messages = msg["payload"]["chat_messages"]
        response = await escalation_agent.completion(messages=chat_messages)
        reply = response.choices[0].message.content
        chat_messages.append({"role": "assistant", "content": reply, "agent": "EscalationAgent"})

        await agents_channel.publish({
            "type": "response",
            "payload": {
                "chat_messages": chat_messages
            },
        })
    except Exception as e:
        print(f"[red]Error in EscalationAgent: {e}[/red]")
