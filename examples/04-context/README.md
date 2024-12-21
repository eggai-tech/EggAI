# Context Sharing Between Agents with EggAI 🧠📡

Welcome to the **04-context** example for **EggAI**! In this demonstration, you’ll see how agents can share and utilize context across different stages of a user query without a dedicated context store. The context is now directly embedded and passed through the message events themselves. This approach streamlines the flow of information, reducing the reliance on external stores.

In this scenario, two agents collaborate:

- **Product Agent**: Retrieves a list of relevant products based on a user query and includes the query context directly in its output message.
- **Recommendation Agent**: Reads the context from the incoming message (which contains the user’s query and previously selected products) and uses it to suggest additional related items.

This pattern simulates a "You may also like..." flow often seen in e-commerce.

---

## What’s Inside? 🗂️

- **Product Agent**: 
  - Receives a user query (e.g., "smartphones").
  - Searches an in-memory database of products.
  - Returns a list of 3 best-matching products.
  - Embeds the query’s context (such as the search term and returned product IDs) directly into the response message.

- **Recommendation Agent**:
  - Listens for product result events from the Product Agent.
  - Extracts context (query, product list) from the received message.
  - Suggests related items not in the initial product set, providing a richer and more coherent user experience.

By passing context directly in messages, we simplify the architecture and make the context chain more transparent and traceable.

---

## Prerequisites 🔧

Please ensure that you have the following installed:

- **Python** 3.10+
- **Docker** and **Docker Compose**
- The EggAI framework (`pip install eggai`)

---

## Architecture Overview 🔄

The flow is as follows:

1. **User Query** → The Product Agent receives a search request (e.g., "I want a gaming smartphone, preferably Apple").
2. **Database Query** → The Product Agent fetches 3 matching products from the in-memory database.
3. **Direct Context Passing** → The Product Agent includes the original query and the chosen products’ details in the same message that publishes the results.
4. **Recommendation Trigger** → The Recommendation Agent listens for the Product Agent's output message. Upon receipt, it extracts the context (the user query and returned products) directly from the message payload.
5. **Additional Suggestions** → Using the provided context, the Recommendation Agent recommends related items that complement the initial search results.
6. **Response to User** → The user receives both the initial product list and additional recommendations, demonstrating a context-rich user experience without external storage.

---

## Setup Instructions ⏳

### Step 1: Create a Virtual Environment (Optional) 🌍

Although optional, we recommend creating a virtual environment:

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

This example requires a messaging broker (e.g., Redpanda):

```bash
docker compose up -d
```

This starts the broker and any required services.

---

## Running the Example 🏆

Navigate to the `examples/04-context` folder and run the main script (remember to set your OpenAI API key):

```bash
OPENAI_API_KEY="your-api-key" python main.py
```

**What to expect:**

1. **User Input**: You provide a query like: "Can you recommend a smartphone? I like gaming on it. I prefer Apple if possible."
2. **Product Agent**: 
   - Finds relevant products and returns three items (e.g., `iPhone 15`, `Samsung Galaxy S23`, `OnePlus 11`).
   - The message it sends out includes the user's original query and these three product IDs in its payload.
3. **Recommendation Agent**:
   - Receives the Product Agent’s message, reads the embedded context, and identifies that the user prefers Apple and is interested in gaming.
   - Suggests related items that were not included in the initial search results but match the user’s context (e.g., a high-performance Apple laptop or a gaming-focused laptop).
4. **Console Output**: 
   ```plaintext
   Agent is running. Press Ctrl+C to stop.
   User: Can you recommend a smartphone, I like gaming on it. I prefer Apple if possible
   Product Agent:
     - iPhone 15
     - Samsung Galaxy S23
     - OnePlus 11
   Recommendation Agent:
     - MacBook Pro 14-inch (Reason: Recommended as it offers a seamless Apple ecosystem experience for gaming and productivity.)
     - Razer Blade 15 (Reason: Recommended for gaming enthusiasts who want top-tier performance.)
   Task was cancelled. Cleaning up...
   ```

By inspecting these messages, you’ll see the entire query context and returned products are passed along, eliminating the need for an external context holder.

---

## Cleaning Up ❌

When you’re done:

```bash
docker compose down -v
```

This stops running containers and removes associated volumes.

---

## Next Steps 🚀

- **Deeper Dives**: Check other examples in the `examples` folder for more advanced patterns.
- **Contribution**: Contribute code, documentation, or report issues to make EggAI better.
- **Feedback**: [Report issues or request features](https://github.com/eggai-tech/EggAI/issues).

---

Thank you for exploring how EggAI can manage context-sharing directly through messages. This streamlined approach aims to inspire more transparent, maintainable, and context-rich multi-agent applications! 🤖🥚