from eggai import Agent, Channel

agent = Agent("Coordinator")

agents_channel = Channel()
human_channel = Channel("human")

@agent.subscribe(filter_func=lambda msg: msg["type"] == "notification")
async def forward_agent_to_human(message):
    await human_channel.publish(message)

@agent.subscribe(channel=human_channel, filter_func=lambda msg: msg["type"] == "create_order")
async def forward_human_to_agents(msg):
    await agents_channel.publish({"type": "order_requested", "id": msg.get("id"), "payload": msg.get("payload")})

async def start_coordinator():
    await agent.run()

async def stop_coordinator():
    await agent.stop()