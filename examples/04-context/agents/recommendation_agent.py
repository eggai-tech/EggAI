from eggai import Agent

from channels import agents_channel, humans_channel
from context_holder import context_holder
from llm import get_related_products

recommendation_agent = Agent("RecommendationAgent")


@recommendation_agent.subscribe(channel=agents_channel, filter_func=lambda msg: msg["event"] == "product_info_sent")
async def handle_product_info_sent(msg):
    message_id = msg["message_id"]
    context = context_holder.get_context(message_id)
    related_products = get_related_products(context)
    await humans_channel.publish({"event": "related_products", "content": related_products, "message_id": message_id})
    await agents_channel.publish({"event": "related_products_sent", "message_id": message_id})
