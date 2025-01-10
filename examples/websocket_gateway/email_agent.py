from eggai import Agent, Channel

agent = Agent("EmailAgent")
channel = Channel()

@agent.subscribe(filter_func=lambda event: event["type"] == "order_created")
async def send_email(message):
    print(f"[EMAIL AGENT]: order_created event received. Sending email to customer.")


@agent.subscribe(filter_func=lambda event: event["type"] == "order_created")
async def send_notification(message):
    print(f"[EMAIL AGENT]: order_created event received. Sending notification event.")
    await channel.publish({
        "id": message.get("id"),
        "type": "notification",
        "payload": {"message": "Order created, you will receive an email soon."}
    })

async def start_email_agent():
    await agent.run()

async def stop_email_agent():
    await agent.stop()