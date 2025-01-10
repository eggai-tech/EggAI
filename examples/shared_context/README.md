# Context Sharing Between Agents

This example demonstrates how agents can share and utilize context using the **eggai** sdk.

Example overview:

- **Product Agent**:
  - Receives a user query (e.g., "smartphones").
  - Searches an in-memory product database and returns 3 matches.
  - Embeds the query and product details in the shared context.
- **Recommendation Agent**:
  - Listens for Product Agent messages.
  - Reads the shared context (query, product list) to suggest related items.
  - Enhances the user experience with additional, context-aware recommendations.

The code for the example can be found [here](https://github.com/eggai-tech/EggAI/tree/main/examples/shared_context).

## Prerequisites

Ensure you have the following dependencies installed:

- **Python** 3.10+
- **Docker** and **Docker Compose**

Ensure you have a valid OpenAI API key set in your environment:

```bash
export OPEN_AI_API_KEY="your-api-key"
```

## Setup Instructions

Clone the EggAI repository:

```bash
git clone git@github.com:eggai-tech/EggAI.git
```

Move into the `examples/shared_context` folder:

```bash
cd examples/shared_context
```

Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # For Windows: venv\Scripts\activate
```

Install the required dependencies:

```bash
pip install -r requirements.txt
```

Start [Redpanda](https://github.com/redpanda-data/redpanda) using Docker Compose:

```bash
docker compose up -d
```

## Run the Example

```bash
python main.py
```

Expected output:

```plaintext
Agent is running. Press Ctrl+C to stop.
User: Can you recommend a smartphone, i like gaming on it. I prefer Apple if possible
Search Agent:
  - iPhone 15
  - Samsung Galaxy S23
  - OnePlus 11
Recommendation Agent:
  - MacBook Pro 14-inch (Reason: Although not a smartphone, this Apple laptop is great for gaming due to its powerful processor.)
  - Razer Blade 15 (Reason: Recommended for gaming enthusiasts who require high-performance hardware.)
^CTask was cancelled. Cleaning up...
```

What happens:

1. **User Query**: The Product Agent receives a search request (e.g., "I want a gaming smartphone, preferablvy Apple").
2. **Product Search**: The Product Agent fetches matching items and includes the query and product details in its message.
3. **Context Passing**: The Recommendation Agent extracts this context and uses it to suggest related products.
4. **Response to User**: Users receive both the initial product list and additional recommendations, creating a context-rich experience.

## Clean Up

Stop and clean up the Docker containers:

```bash
docker compose down -v
```

## Next Steps

Ready to explore further? Check out:

- **Advanced Examples:** Discover more complex use cases in the [examples](https://github.com/eggai-tech/EggAI/tree/main/examples/) folder.
- **Contribution Guidelines:** Get involved and help improve EggAI!
- **GitHub Issues:** [Submit a bug or feature request](https://github.com/eggai-tech/eggai/issues).
- **Documentation:** Refer to the official docs for deeper insights.
