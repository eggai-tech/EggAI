import json

from eggai import Agent

from channels import agents_channel, humans_channel

audit_agent = Agent("AuditAgent")


@audit_agent.subscribe(channel=agents_channel)
@audit_agent.subscribe(channel=humans_channel)
async def audit(msg):
    with open("../out.log", "a") as f:
        f.write(json.dumps(msg) + "\n")
