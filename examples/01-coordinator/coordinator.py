from eggai import Agent, Channel

agent = Agent("Coordinator")

agents_channel = Channel()
human_channel = Channel("human")

@agent.subscribe(filter_func=lambda message: "human" in message and message["human"] == True)
async def forward_agent_to_human(message):
    print("[COORDINATOR]: human=true message received. Forwarding to human channel.")
    await human_channel.publish(message)

@agent.subscribe(channel=human_channel, filter_func=lambda message: "action" in message)
async def forward_human_to_agents(message):
    print("[COORDINATOR]: action message received. Forwarding to agents channel.")
    if message["action"] == "create_order":
        await agents_channel.publish({"event_name": "order_requested", "payload": message.get("payload")})

@agent.subscribe(channel=human_channel, filter_func=lambda message: message["event_name"] == "notification")
async def handle_notifications(message):
    print("[COORDINATOR]: Received notification for human: ", message["payload"]["message"])
