from eggai import Agent

agent = Agent("EmailAgent")

@agent.subscribe(filter_func=lambda event: event["event_name"] == "order_created")
async def send_email(message):
    print(f"[EMAIL AGENT]: Received order created event. {message}")