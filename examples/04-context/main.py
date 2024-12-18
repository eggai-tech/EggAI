import asyncio

from eggai import Agent, Channel

from context_holder import ContextHolder
from llm import get_product_info, get_related_products

context_holder = ContextHolder()

agents_channel = Channel("AgentsChannel")
humans_channel = Channel("HumansChannel")

products_agent = Agent("ProductsAgent")
@products_agent.subscribe(channel=agents_channel, filter_func=lambda msg: msg["event"] == "user_query")
async def handle_user_query(msg):
    message_id = msg["message_id"]
    product_list = get_product_info(msg["payload"])
    context_holder.add_context(message_id, {"user_query": msg["payload"], "product_list": product_list})
    await humans_channel.publish({"event": "product_info", "content": product_list, "message_id": message_id})
    await agents_channel.publish({"event": "product_info_sent", "message_id": message_id})


recommendation_agent = Agent("RecommendationAgent")
@recommendation_agent.subscribe(channel=agents_channel, filter_func=lambda msg: msg["event"] == "product_info_sent")
async def handle_product_info_sent(msg):
    message_id = msg["message_id"]
    context = context_holder.get_context(message_id)
    related_products = get_related_products(context)
    await humans_channel.publish({"event": "related_products", "content": related_products, "message_id": message_id})
    await agents_channel.publish({"event": "related_products_sent", "message_id": message_id})


audit_agent = Agent("AuditAgent")
@audit_agent.subscribe(channel=agents_channel, filter_func=lambda msg: msg["event"] == "user_query")
async def user_asks(msg):
    print(f"User: {msg['payload']}")

@audit_agent.subscribe(channel=humans_channel, filter_func=lambda msg: msg["event"] == "product_info")
async def print_agents_message(msg):
    print(f"Search Agent:")
    for product in msg["content"]:
        print("  - " + product["name"])

@audit_agent.subscribe(channel=humans_channel, filter_func=lambda msg: msg["event"] == "related_products")
async def print_recommendation(msg):
    print(f"Recommendation Agent:")
    for product in msg["content"]:
        print("  - " + product["name"] + " (Reason: " + product["reason"] + ")")


async def main():
    await audit_agent.run()
    await products_agent.run()
    await recommendation_agent.run()

    await agents_channel.publish({
        "message_id": "ID-0",
        "event": "user_query",
        "payload": "Can you recommend a smartphone, i like gaming on it. I prefer Apple if possible"
    })

    try:
        print("Agent is running. Press Ctrl+C to stop.")
        await asyncio.Event().wait()
    except asyncio.exceptions.CancelledError:
        print("Task was cancelled. Cleaning up...")
    finally:
        await recommendation_agent.stop()
        await products_agent.stop()
        await audit_agent.stop()
        await Channel.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exiting...")