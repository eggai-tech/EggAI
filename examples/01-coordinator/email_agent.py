from eggai import Agent, Channel

agent = Agent("EmailAgent")
channel = Channel()

@agent.subscribe(filter_func=lambda event: event["event_name"] == "order_created")
async def send_email(message):
    print(f"[EMAIL AGENT]: Received order created event. {message}")


@agent.subscribe(filter_func=lambda event: event["event_name"] == "order_created")
async def send_notification(message):
    print(f"[EMAIL AGENT]: Received order created event. {message}")
    await channel.publish({"human": True, "message": "Order created. Please check your email."})