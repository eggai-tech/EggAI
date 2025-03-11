from eggai import Agent

agent = Agent("EmailAgent")

@agent.subscribe(filter_by_message=lambda event: event.get("type") == "order_created")
async def send_email(msg):
    print(f"[EMAIL AGENT]: Received order created event. {msg.get('type')} {msg.get('data')}")