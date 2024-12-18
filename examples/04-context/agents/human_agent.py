from eggai import Agent

from channels import agents_channel, humans_channel

human_agent = Agent("HumanAgent")


@human_agent.subscribe(channel=agents_channel, filter_func=lambda msg: msg["event"] == "user_query")
async def user_asks(msg):
    print(f"User: {msg['payload']}")


@human_agent.subscribe(channel=humans_channel, filter_func=lambda msg: msg["event"] == "product_info")
async def print_agents_message(msg):
    print(f"Search Agent:")
    for product in msg["content"]:
        print("  - " + product["name"])


@human_agent.subscribe(channel=humans_channel, filter_func=lambda msg: msg["event"] == "related_products")
async def print_recommendation(msg):
    print(f"Recommendation Agent:")
    for product in msg["content"]:
        print("  - " + product["name"] + " (Reason: " + product["reason"] + ")")
