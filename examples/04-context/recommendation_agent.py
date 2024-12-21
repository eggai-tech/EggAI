import json

from eggai import Agent, Channel

from memory_db import total_product_list
from openai_client import openai_client

recommendation_agent = Agent("RecommendationAgent")
agents_channel = Channel("AgentsChannel")
humans_channel = Channel("HumansChannel")


@recommendation_agent.subscribe(channel=agents_channel, filter_func=lambda msg: msg["type"] == "product_info_sent")
async def handle_product_info_sent(msg):
    message_id = msg["id"]
    context = msg["context"]
    related_products = get_related_products(context)
    await humans_channel.publish({"type": "related_products", "payload": related_products, "id": message_id})


def get_recommendation_agent_system_prompt():
    return """
You are a Recommender Agent. Your task is to recommend products based on the user context history.

The following is a list of available products:
""" + json.dumps(total_product_list, indent=4) + """

1. The user will provide you the history of their context, the user query, and the product list retrieved.
2. You will respond by recommending products that are related to the user's context history.
3. Don't recommend the same products that were already provided in the user's context history, and provide at least 2 additional products, preferably related to the user's query but on a different category.
4. You will provide the product information in JSON format, including the product name, category, and description, and reason why the product is picked.
5. If you cannot find any relevant products, you should respond with an empty list [].

Example:
- User send his context history: { user_query: "Can you recommend a smartphone, i like gaming!", product_list: [ {"name": "iPhone 15", "category": "Smartphone", "description": "Latest Apple smartphone with A17 chip and enhanced camera."}, {"name": "Samsung Galaxy S23", "category": "Smartphone", "description": "High-performance Android smartphone with a 120Hz display."}, {"name": "Google Pixel 8", "category": "Smartphone", "description": "Smartphone with a clean Android experience and advanced AI features."} ] }
- Your action: Recommend additional products that are related to the user's context history, but having different category from the history, in json format

[
    {"name": "Razer Blade 15", "category": "Laptop", "description": "High-performance gaming laptop with NVIDIA GeForce RTX 3070 and 144Hz display.", "reason": "Recommended for gaming enthusiasts."},
]
"""

def get_related_products(context):
    context_str = json.dumps({
        "user_query": context["user_query"],
        "product_list": context["product_list"]
    })

    completion = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": get_recommendation_agent_system_prompt()},
            {"role": "user", "content": context_str}
        ]
    )

    return json.loads(completion.choices[0].message.content.strip())