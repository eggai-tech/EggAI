from sdk.eggai import Agent, Channel

agent = Agent("OrderAgent")
channel = Channel()


@agent.subscribe(filter_func=lambda msg: msg["type"] == "order_requested")
async def create_order(msg):
    print(f"[ORDER AGENT]: order_requested event received. Emitting order_created event.")
    await channel.publish({"type": "order_created", "payload": msg.get("payload"), "id": msg.get("id")})


@agent.subscribe(filter_func=lambda msg: msg["type"] == "order_created")
async def order_processing(msg):
    print(f"[ORDER AGENT]: order_created event received.")

async def start_order_agent():
    await agent.run()

async def stop_order_agent():
    await agent.stop()