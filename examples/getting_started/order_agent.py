from eggai import Agent, Channel
from eggai.schemas import Message

agent = Agent("OrderAgent")
channel = Channel()


@agent.subscribe(filter_by_message=lambda event: event.get("type") == "order_requested")
async def create_order(msg):
    print(f"[ORDER AGENT]: Received request to create order. {msg.get('type')} {msg.get('data')}")
    await channel.publish(Message(type="order_created", source="main", data=msg.get("data")))


@agent.subscribe(filter_by_message=lambda event: event.get("type") == "order_created")
async def order_processing(msg):
    print(f"[ORDER AGENT]: Received order created event. {msg.get('type')} {msg.get('data')}")
