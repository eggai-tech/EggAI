# Intent Classification Agent with EggAI

This example demonstrates how to build and implement an intent classification agent using EggAI. The agent acts as a
*Triage*, processing user messages and routing them to the appropriate target agents based on the intent of the
conversation. The TriageAgent uses a custom classification model to determine whether a message is policy-related,
ticketing-related, or non-insurance-related.

Key features:

- **Intent Classification**: Automatically classifies user messages into one of three target agents: `PolicyAgent`,
  `TicketingAgent`, or `TriageAgent`.
- **Chain of Thought Reasoning**: Employs the `dspy` library for reasoning and structured decision-making in the
  classification process.
- **Testing Suite**: Includes test datasets and pytest-based evaluation to ensure performance of the intent classifier.

The code for this example is
available [here](https://github.com/eggai-tech/EggAI/tree/main/examples/intent_classification).

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

Move into the `examples/intent_classification` folder:

```bash
cd examples/intent_classification
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

## Run the Tests

```bash
pytest
```

This will demonstrate the intent classifier working with a sample dataset.

## Clean Up

Stop and clean up the Docker containers:

```bash
docker compose down -v
```

## Next Steps

Ready to explore further? Check out:

- **Advanced Examples:** Discover more complex use cases in
  the [examples](https://github.com/eggai-tech/EggAI/tree/main/examples/) folder.
- **Contribution Guidelines:** Get involved and help improve EggAI!
- **GitHub Issues:** [Submit a bug or feature request](https://github.com/eggai-tech/eggai/issues).
- **Documentation:** Refer to the official docs for deeper insights.
