from eggai import Agent, Channel
from tests.test_events import channel

agent = Agent("Coordinator")

agents_channel = Channel()
human_channel = Channel("human")

@agent.subscribe(filter_func=lambda message: "human" in message and message["human"] == True)
async def handle_agent_messages(message):
    print("[COORDINATOR]: Received message from agent. Forwarding to human.")
    await human_channel.publish(message)

@agent.subscribe(channel=human_channel, filter_func=lambda message: "human" not in message)
async def handle_human_messages(message):
    print("[COORDINATOR]: Received message from human. Forwarding to agents.")
    await agents_channel.publish(message)