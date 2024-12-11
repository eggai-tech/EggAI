from eggai import Agent, Channel

agent = Agent("OrderAgent")
channel = Channel()


@agent.subscribe(filter_func=lambda event: event["event_name"] == "order_requested")
async def create_order(event):
    print(f"[ORDER AGENT]: Received request to create order. {event}")
    await channel.publish({"event_name": "order_created", "payload": event.get("payload")})


@agent.subscribe(filter_func=lambda event: event["event_name"] == "order_created")
async def order_processing(message):
    print(f"[ORDER AGENT]: Received order created event. {message}")
