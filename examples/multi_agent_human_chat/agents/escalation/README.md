# Escalation Agent

## Overview

The Escalation Agent handles complex customer issues that require special attention or escalation beyond the automated system. It manages a multi-step workflow to collect necessary information, confirm escalation requirements, and create support tickets for human follow-up.

## Key Features

- Implements a state-based escalation workflow
- Creates support tickets for issues other agents can't resolve
- Maintains session data throughout the escalation process
- Handles customer complaints requiring management attention
- Manages technical issues needing dedicated follow-up

## Architecture

### Core Components

- **Agent Module** (`agent.py`): Implements the escalation workflow and state management
- **Config** (`config.py`): Configuration settings for the agent

### State Machine

The Escalation Agent manages a multi-step workflow with distinct states:

1. **Initial Assessment**: Collecting issue details
2. **Information Gathering**: Getting specific information depending on issue type
3. **Confirmation**: Verifying ticket creation requirements
4. **Ticket Creation**: Generating a support ticket
5. **Resolution**: Providing reference number and next steps

### Escalation Capabilities

The agent implements multiple DSPy-based modules using ChainOfThought and ReAct modules:

- **Signatures**: Various specialized signatures for different stages of the escalation process:
  - RetrieveTicketInfoSignature: Extracts ticket information from conversations
  - ClassifyConfirmationSignature: Classifies user confirmations 
  - CreateTicketSignature: Creates support tickets with collected information
- **Tools**: Provides a specialized tool for ticket operations:
  - `create_ticket`: Creates a ticket in the database with department, title, and contact info

### Message Flow

1. Messages arrive on the `agents` channel with `escalation_request` type
2. Current state determines processing logic
3. State transitions occur based on user input
4. Responses are published to the `human` channel

## Technical Details

### State Management

```python
STATES = {
    "INITIAL": 0,
    "GATHERING_INFO": 1,
    "CONFIRMATION": 2,
    "CREATING_TICKET": 3,
    "RESOLVED": 4
}
```

Session data is maintained for each connection, tracking:
- Current state
- Issue details
- Customer information
- Ticket reference (when created)

### Input Validation

The agent validates user inputs at each stage:
- Ensures required fields are provided
- Validates contact information formats
- Confirms issue categorization

### Error Handling

Comprehensive error handling provides graceful degradation:
- Timeouts for stuck sessions
- Exception handling for each state
- User-friendly error messages

## Development

### Testing

Tests for the Escalation Agent verify:
- State transitions
- Session data persistence
- Ticket creation logic
- Error handling

Run tests with:
```bash
make test-escalation-agent
```

### Extending

To add new escalation capabilities:
1. Add new state handling in the agent's process methods
2. Update state transition logic
3. Implement any new validation requirements
4. Add corresponding test cases

## Integration Points

- **Frontend Agent**: Provides user interface for the escalation process
- **Triage Agent**: Routes appropriate issues to the Escalation Agent
- **Other Agents**: May refer difficult cases to Escalation when unable to handle