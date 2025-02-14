# Triage Agent with classification and routing

This example demonstrates how to build and implement a Triage Agent using EggAI. The Triage Agent is designed to handle
incoming messages, classify them based on predefined criteria (e.g., urgency, type, or category), and route them to the
appropriate agents or services for further processing. By ensuring efficient task delegation and resource utilization,
the Triage Agent plays a critical role in optimizing workflows.

## Key Features:

- **Message Classification**: Automatically classifies user messages into one of three target agents: `PolicyAgent`,
  `TicketingAgent`, or `TriageAgent`.
- **Dynamic Routing**: Routes messages to the most suitable agents or services based on the classification outcome,
  enabling efficient and accurate task handling.
- **Chain of Thought Reasoning**: Utilizes the `dspy` library for structured decision-making, enhancing the reasoning
  process in message classification.
- **Comprehensive Testing Suite**: Includes test datasets and pytest-based evaluation to validate the performance and
  accuracy of the classification model.

The code for this example is
available [here](https://github.com/eggai-tech/EggAI/tree/main/examples/intent_classification).

## Prerequisites

Ensure you have the following dependencies installed:

- **Python** 3.10+
- **Docker** and **Docker Compose**

Ensure you have a valid OpenAI API key set in your environment:

```bash
export OPENAI_API_KEY="your-api-key"
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
