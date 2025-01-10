from sdk.eggai import Agent, Channel

agent = Agent("OrderAgent")
channel = Channel()


@agent.subscribe(filter_func=lambda event: event["event_name"] == "order_requested")
async def create_order(event):
    print(f"[ORDER AGENT]: order_requested event received. Emitting order_created event.")
    await channel.publish({"event_name": "order_created", "payload": event.get("payload")})


@agent.subscribe(filter_func=lambda event: event["event_name"] == "order_created")
async def order_processing(message):
    print(f"[ORDER AGENT]: order_created event received.")
