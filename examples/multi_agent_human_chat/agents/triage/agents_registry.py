AGENT_REGISTRY = {
    "PoliciesAgent": {
        "message_type": "policy_request",
        "description": "Handles policy-related queries",
    },
    "BillingAgent": {
        "message_type": "billing_request",
        "description": "Handles billing-related queries",
    },
    "EscalationAgent": {
        "message_type": "escalation_request",
        "description": "Handles escalations, everything related to tickets and support must be handled by this agent",
    },
}