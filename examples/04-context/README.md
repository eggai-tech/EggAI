# Context Sharing Between Agents with EggAI 🧠📡

Welcome to the **04-context** example for **EggAI**! This demonstration showcases how agents can share and utilize context across different stages of a user query, enabling more personalized and connected responses.

In this scenario, we have two agents communicating through a shared context mechanism. The **Product Agent** retrieves a list of relevant products from an in-memory database based on a user query and stores contextual information. The **Recommendation Agent** then uses this context to suggest related items, emulating a "You may also like..." pattern often seen in e-commerce environments.

---

## What’s Inside? 🗂️

- **Product Agent**: Receives a user query, searches an in-memory database of products (e.g., smartphones and laptops), and returns a list of 3 products that best match the query. At the same time, it writes the query’s context to a shared `ContextHolder`.
- **ContextHolder**: A simple, in-memory key-value store that maps a query’s message ID to relevant context data. This ensures any agent downstream can access the necessary context to make informed decisions.
- **Recommendation Agent**: Triggers upon receiving product results from the Product Agent. It looks up the stored context, examines the query and previously returned products, and then provides additional recommended items that were not part of the initial search results.

The primary goal is to demonstrate how EggAI’s architecture facilitates sharing context between agents, resulting in a richer, more coherent multi-agent workflow.

---

## Prerequisites 🔧

Please ensure that you have the following installed:

- **Python** 3.10+
- **Docker** and **Docker Compose**
- The EggAI framework (`pip install eggai`)

---

## Architecture Overview 🔄

The flow is as follows:

1. **User Query** → The Product Agent receives a search request for certain products (e.g., "smartphones").
2. **Database Query** → The Product Agent fetches 3 matching products from the in-memory product database.
3. **Context Storage** → The Product Agent stores the query and returned products’ context (such as the search term and the returned product IDs) in `ContextHolder`, keyed by the query’s unique message ID.
4. **Recommendation Trigger** → The Recommendation Agent listens for product result events. When triggered, it retrieves the stored context.
5. **Additional Suggestions** → Leveraging the query context, the Recommendation Agent recommends additional products related to the search but not in the initial product set. These recommendations might say, "You may also like…" followed by similar items.
6. **Response to User** → The user receives both the initial product list and the additional recommendations, showing how contextual continuity enhances the user experience.

---

## Setup Instructions ⏳

### Step 1: Create a Virtual Environment (Optional) 🌍

Creating a virtual environment is not mandatory, but highly recommended:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Step 2: Install EggAI 🎓

If you haven’t already:

```bash
pip install eggai openai
```

### Step 3: Start Services with Docker 🚢

This example still relies on a messaging broker (e.g., Redpanda) and other services:

```bash
docker compose up -d
```

This will start the broker and any additional components required to run the agents.

---

## Running the Example 🏆

Navigate to the `examples/04-context` folder and run the main script (remember to set your OpenAI API key):

```bash
OPENAI_API_KEY="your-api-key" python main.py
```

**What to expect:**

1. The Product Agent receives a user query (e.g., "smartphones").
2. It looks up matching smartphones in the in-memory database and returns 3 products.
3. Simultaneously, the Product Agent stores the query’s context into `ContextHolder`.
4. The Recommendation Agent, upon detecting that products have been returned, retrieves the context. It then recommends a few related items based on the user query and the products found.
5. The console output (or log) will display both the initial product list and the recommended products, illustrating how context is maintained and utilized across multiple agents.
    ```plaintext
    Agent is running. Press Ctrl+C to stop.
    User: Can you recommend a smartphone, i like gaming on it. I prefer Apple if possible
    Search Agent:
      - iPhone 15
      - Samsung Galaxy S23
      - OnePlus 11
    Recommendation Agent:
      - MacBook Pro 14-inch (Reason: Recommended as it offers a seamless Apple ecosystem experience for gaming and productivity.)
      - Razer Blade 15 (Reason: Recommended for gaming enthusiasts, providing high-quality graphics and performance.)
    Task was cancelled. Cleaning up...
    ```

---

## Cleaning Up ❌

When you’re done:

```bash
docker compose down -v
```

This stops running containers and removes associated volumes.

---

## Next Steps 🚀

- **Deeper Dives**: Check out other examples in the `examples` folder for more complex multi-agent scenarios.
- **Contribution**: Help improve EggAI by contributing code, documentation, or filing issues.
- **Issues & Feedback**: [Report issues or request features](https://github.com/eggai-tech/EggAI/issues).

---

Thank you for exploring how EggAI manages context sharing between agents. We hope this example sparks ideas for more personalized, context-aware multi-agent applications! 🤖🥚