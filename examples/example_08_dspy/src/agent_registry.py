AGENT_REGISTRY = {
    "PolicyAgent": {
        "message_type": "policy_request",
        "description": (
            "Handles all policy-related inquiries. Responsibilities include fetching policy details, "
            "verifying policy status, updating policy information, and providing information on policy coverage and benefits. "
            "Users can interact with this agent by providing their policy numbers or requesting specific policy information."
        ),
    },
    "TicketingAgent": {
        "message_type": "ticketing_request",
        "description": (
            "Manages ticket creation, updates, and retrieval. This agent is responsible for logging user issues, "
            "tracking the status of existing tickets, and providing updates or resolutions to reported problems. "
            "Users can interact with this agent to report new issues or inquire about the status of their existing tickets."
        ),
    }
}