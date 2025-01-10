from sdk.eggai import Agent, Channel

human_agent = Agent("HumanAgent")
agents_channel = Channel("AgentsChannel")
humans_channel = Channel("HumansChannel")

@human_agent.subscribe(channel=agents_channel, filter_func=lambda msg: msg["type"] == "user_query")
async def user_asks(msg):
    print(f"User: {msg['payload']}")


@human_agent.subscribe(channel=humans_channel, filter_func=lambda msg: msg["type"] == "product_info")
async def print_agents_message(msg):
    print(f"Search Agent:")
    for product in msg["payload"]:
        print("  - " + product["name"])


@human_agent.subscribe(channel=humans_channel, filter_func=lambda msg: msg["type"] == "related_products")
async def print_recommendation(msg):
    print(f"Recommendation Agent:")
    for product in msg["payload"]:
        print("  - " + product["name"] + " (Reason: " + product["reason"] + ")")
