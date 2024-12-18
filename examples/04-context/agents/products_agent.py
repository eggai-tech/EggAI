from eggai import Agent

from channels import agents_channel, humans_channel
from context_holder import context_holder
from llm import get_product_info

products_agent = Agent("ProductsAgent")


@products_agent.subscribe(channel=agents_channel, filter_func=lambda msg: msg["event"] == "user_query")
async def handle_user_query(msg):
    message_id = msg["message_id"]
    product_list = get_product_info(msg["payload"])
    context_holder.add_context(message_id, {"user_query": msg["payload"], "product_list": product_list})
    await humans_channel.publish({"event": "product_info", "content": product_list, "message_id": message_id})
    await agents_channel.publish({"event": "product_info_sent", "message_id": message_id})
