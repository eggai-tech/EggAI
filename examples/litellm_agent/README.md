# Integrating LiteLLM with EggAI

This example demonstrates integrating **LiteLLM** into the **eggai** SDK. It shows a system with two AI agents—**SupportAgent** and **EscalationAgent**—to handle customer inquiries efficiently and escalate complex issues when necessary.

Key features:

- LiteLLM integration
- Tool usage
- Collaborative between two agents

The code for this example is available [here](https://github.com/eggai-tech/EggAI/tree/main/examples/litellm_agent).

## Prerequisites

Ensure you have the following dependencies installed:

- **Python** 3.10+
- **Docker** and **Docker Compose**

Ensure you have a valid OpenAI API key set in your environment:

```bash
export OPENAI_API_KEY="your-api-key"
```

## Setup Instructions

Clone the EggAI repository:

```bash
git clone git@github.com:eggai-tech/EggAI.git
```

Move into the `examples/litellm_agent` folder:

```bash
cd examples/litellm_agent
```

Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # For Windows: venv\Scripts\activate
```

Install the required dependencies:

```bash
pip install -r requirements.txt
```

Start [Redpanda](https://github.com/redpanda-data/redpanda) using Docker Compose:

```bash
docker compose up -d
```

## Run the Example

```bash
python main.py
```

Expected output:

```plaintext
Handling customer inquiry: What is your return policy?
Agent is running. Press Ctrl+C to stop.
Querying knowledge base for: return_policy
Failed to decode response from SupportAgent, message was:  {
    "response": "Our return policy is 30 days from the date of purchase. Items must be in their original condition."
}
{
    "response": "Our return policy is 30 days from the date of purchase. Items must be in their original condition."
}
Handling customer inquiry: I have a billing issue that isn't resolved yet.
Querying knowledge base for: billing_issue
Response from SupportAgent: {'response': 'escalate'}
Escalating issue to EscalationAgent...
Creating support ticket for issue: I have a billing issue that isn't resolved yet.
Ticket created for escalated issue:  {'ticket_id': 'TCKT7707', 'department': 'Billing Department'}
^CTask was cancelled. Cleaning up...
```

What happens:

- Customers submit inquiries like "What is your return policy?" via the `humans` channel.
- **SupportAgent**: Processes general inquiries using the `GetKnowledge` tool.
  - Responds directly if the inquiry is simple.
  - Escalates complex issues to the EscalationAgent.
- **EscalationAgent**:
  - Creates a support ticket for escalated issues using the `TicketingTool`.
  - Publishes ticket details to the `agents` channel and informs the customer.

## Clean Up

Stop and clean up the Docker containers:

```bash
docker compose down -v
```

## Next Steps

Ready to explore further? Check out:

- **Advanced Examples:** Discover more complex use cases in the [examples](https://github.com/eggai-tech/EggAI/tree/main/examples/) folder.
- **Contribution Guidelines:** Get involved and help improve EggAI!
- **GitHub Issues:** [Submit a bug or feature request](https://github.com/eggai-tech/eggai/issues).
- **Documentation:** Refer to the official docs for deeper insights.
