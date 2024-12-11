from eggai import Agent, Channel

agent = Agent("EmailAgent")
channel = Channel()

@agent.subscribe(filter_func=lambda event: event["event_name"] == "order_created")
async def send_email(message):
    print(f"[EMAIL AGENT]: order_created event received. Sending email to customer.")


@agent.subscribe(filter_func=lambda event: event["event_name"] == "order_created")
async def send_notification(message):
    print(f"[EMAIL AGENT]: order_created event received. Sending notification event.")
    await channel.publish({"human": True, "event_name": "notification", "payload": {"message": "Order created, you will receive an email soon."}})