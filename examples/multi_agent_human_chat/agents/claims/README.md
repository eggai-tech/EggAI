# Claims Agent

## Overview

The Claims Agent is a specialized AI agent built to handle insurance claims inquiries and processing. It provides a conversational interface for:

- Retrieving claim status information
- Filing new claims
- Updating existing claim information
- Answering claims-related questions

The agent leverages an optimized DSPy model to generate contextually appropriate responses based on the conversation history.

## Business Requirements

The Claims Agent fulfills these core business requirements:

1. **Claim Status Retrieval**
   - Provide current status (e.g., "In Review", "Approved", "Pending")
   - Show estimated payout amounts when available
   - Display expected processing dates when available
   - List any outstanding items needed from the customer

2. **New Claim Filing**
   - Accept policy number and incident details
   - Create new claims with appropriate metadata
   - Generate a unique claim identifier
   - Confirm successful claim creation
   - Provide next steps for documentation

3. **Claim Information Updates**
   - Allow updating contact information (address, phone, email)
   - Support changes to claim descriptions
   - Request confirmation before applying changes
   - Acknowledge successful updates

4. **Security and Compliance**
   - Only provide claim information to authorized requesters
   - Never expose sensitive data in responses
   - Handle errors gracefully with user-friendly messages
   - Support tracing for audit requirements

## Architecture

The Claims Agent follows a modular architecture with these key components:

### Core Components

- **Agent Module** (`agent.py`): Central implementation that configures the agent, defines message handlers, and coordinates processing.
- **Config** (`config.py`): Configuration settings for the agent, including model parameters.

### DSPy Integration

- **Claims Model** (`dspy_modules/claims.py`): Optimized DSPy model for generating context-aware responses, with standardized configuration.
- **Claims Data** (`dspy_modules/claims_data.py`): Data operations for claim retrieval, filing, and updating.

### Communication Flow

1. Messages are received through the agents channel
2. Chat history is formatted into conversation strings
3. Requests are processed by the DSPy model
4. Responses are published to the human channel

## Usage

The Claims Agent follows the EggAI agent pattern and can be started with:

```bash
make start-claims
```

### Message Format

To communicate with the Claims Agent, send messages to the `agents` channel with the following structure:

```json
{
  "type": "claim_request",
  "source": "FrontendAgent",
  "data": {
    "chat_messages": [
      {"role": "User", "content": "Hi, I'd like to check my claim status"},
      {"role": "ClaimsAgent", "content": "Sure, could you provide your claim number?"},
      {"role": "User", "content": "It's 1001"}
    ],
    "connection_id": "user-session-123"
  }
}
```

### Responses

The agent sends responses to the `human` channel with:

```json
{
  "type": "agent_message",
  "source": "ClaimsAgent",
  "data": {
    "message": "Your claim #1001 is currently 'In Review'. We estimate a payout of $2300 by 2025-05-15. We're still awaiting your repair estimates—please submit them at your earliest convenience.",
    "connection_id": "user-session-123",
    "agent": "ClaimsAgent"
  }
}
```

## Development

### Testing

Run the Claims Agent tests with:

```bash
make test-claims-agent
```

### Extending

To add new claim-related capabilities:

1. Implement new data operations in `dspy_modules/claims_data.py`
2. Update the prompt in `dspy_modules/claims.py` if necessary
3. Run optimizer with `make compile-claims-optimizer` if prompt changes
4. Add test cases to `tests/test_agent.py` using the `get_test_cases()` function

## Integration Points

- **Frontend**: Integrates with the Frontend Agent through message passing
- **Triage**: Can receive requests forwarded by the Triage Agent
- **Policies**: May reference policy information available from the Policies Agent