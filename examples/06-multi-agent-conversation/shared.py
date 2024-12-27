from eggai import Channel

agents_channel = Channel("cli.agents")
humans_channel = Channel("cli.humans")

AGENT_REGISTRY = {
    "PolicyAgent": {
        "description": "Handles policy-related inquiries.",
        "keywords": ["policy details", "coverage", "premiums", "policy changes", "policy number", "renewal"]
    },
    "ClaimsAgent": {
        "description": "Handles claims-related inquiries.",
        "keywords": ["file a claim", "claim status", "claim amount", "accident", "damage", "incident"]
    },
    "EscalationAgent": {
        "description": "Handles escalated inquiries and out-of-scope requests.",
        "keywords": ["escalate", "speak to a human", "complaint", "refund", "support", "issue", "problem"]
    },
}
