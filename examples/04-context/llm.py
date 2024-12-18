import json
import os

from openai import OpenAI

product_list = [
    {"name": "iPhone 15", "category": "Smartphone", "description": "Latest Apple smartphone with A17 chip and enhanced camera."},
    {"name": "Samsung Galaxy S23", "category": "Smartphone", "description": "High-performance Android smartphone with a 120Hz display."},
    {"name": "Google Pixel 8", "category": "Smartphone", "description": "Smartphone with a clean Android experience and advanced AI features."},
    {"name": "OnePlus 11", "category": "Smartphone", "description": "Flagship Android smartphone with fast charging and a 50MP camera."},
    {"name": "Sony Xperia 1 IV", "category": "Smartphone", "description": "High-end smartphone designed for media creators with 4K OLED screen."},
    {"name": "MacBook Pro 14-inch", "category": "Laptop", "description": "Powerful laptop with M1 Pro chip, Retina display, and long battery life."},
    {"name": "Dell XPS 13", "category": "Laptop", "description": "Compact and lightweight laptop with an Intel Core i7 processor and stunning display."},
    {"name": "HP Spectre x360", "category": "Laptop", "description": "Convertible laptop with 360-degree hinge, Intel Core i7, and AMOLED touchscreen."},
    {"name": "Lenovo ThinkPad X1 Carbon", "category": "Laptop", "description": "Durable business laptop with a powerful Intel Core i7 processor and great battery life."},
    {"name": "Razer Blade 15", "category": "Laptop", "description": "High-performance gaming laptop with NVIDIA GeForce RTX 3070 and 144Hz display."}
]

def get_product_information_system_prompt():
    product_list_json = json.dumps(product_list, indent=4)

    return """
You are a Product Information Agent. Your task is to gather product data based on the user’s query and return a list of relevant products.

The following is a list of available products:
""" + product_list_json + """

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


def get_recommendation_agent_system_prompt():
    product_list_json = json.dumps(product_list, indent=4)
    return """
You are a Recommender Agent. Your task is to recommend products based on the user context history.

The following is a list of available products:
""" + product_list_json + """

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

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_product_info(user_query: str):
    completion = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": get_product_information_system_prompt()},
            {"role": "user", "content": user_query}
        ]
    )

    return json.loads(completion.choices[0].message.content.strip())


def get_related_products(context):
    completion = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": get_recommendation_agent_system_prompt()},
            {"role": "user", "content": json.dumps(context)}
        ]
    )

    return json.loads(completion.choices[0].message.content.strip())