import json

from sdk.eggai import Agent, Channel

from openai_client import openai_client
from memory_db import total_product_list

products_agent = Agent("ProductsAgent")
agents_channel = Channel("AgentsChannel")
humans_channel = Channel("HumansChannel")


@products_agent.subscribe(channel=agents_channel, filter_func=lambda msg: msg["type"] == "user_query")
async def handle_user_query(msg):
    message_id = msg["id"]
    product_list = get_product_info(msg["payload"])
    await humans_channel.publish({"type": "product_info", "payload": product_list, "id": message_id})
    await agents_channel.publish({
        "type": "product_info_sent",
        "meta": {
            "correlation_id": message_id
        },
        "context": {
            "user_query": msg["payload"],
            "product_list": product_list,
            "id": message_id
        }
    })

def get_product_information_system_prompt():
    return """
You are a Product Information Agent. Your task is to gather product data based on the user’s query and return a list of relevant products.

The following is a list of available products:
""" + json.dumps(total_product_list, indent=4) + """

1. The user will provide you with a product-related query.
2. You will respond by retrieving the top 3 products that best match the user's request.
3. You will provide the product information in JSON format, including the product name, category, and description.
4. If you cannot find any relevant products, you should respond with an empty list [].

Example:
- User query: "Can you recommend a smartphone?"
- Your action: Retrieve the top 3 smartphones based on the query and provide them in the following json format:

[
    {"name": "iPhone 15", "category": "Smartphone", "description": "Latest Apple smartphone with A17 chip and enhanced camera."},
    {"name": "Samsung Galaxy S23", "category": "Smartphone", "description": "High-performance Android smartphone with a 120Hz display."},
    {"name": "Google Pixel 8", "category": "Smartphone", "description": "Smartphone with a clean Android experience and advanced AI features."}
]
"""

def get_product_info(user_query: str):
    completion = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": get_product_information_system_prompt()},
            {"role": "user", "content": user_query}
        ]
    )

    return json.loads(completion.choices[0].message.content.strip())