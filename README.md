<img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/eggai-word-and-figuremark.svg" alt="EggAI word and figuremark" width="200px" style="margin-bottom: 16px;" />

# Multi-Agent Meta Framework

Documentation: [EggAI Docs](https://docs.egg-ai.com/)

<!--start-->

[![Python 3.x](https://img.shields.io/badge/python-3.x-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge&logo=opensourceinitiative&logoColor=white)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen?style=for-the-badge&logo=github&logoColor=white)](https://github.com/eggai-tech/eggai/pulls)
[![GitHub Issues](https://img.shields.io/github/issues/eggai-tech/eggai?style=for-the-badge&logo=github&logoColor=white)](https://github.com/eggai-tech/eggai/issues)
[![GitHub Stars](https://img.shields.io/github/stars/eggai-tech/eggai?style=for-the-badge&logo=github&logoColor=white)](https://github.com/eggai-tech/eggai/stargazers)

`EggAI Multi-Agent Meta Framework` makes it easy to build enterprise-grade multi-agent systems with quality-controlled output, using an async-first, distributed and composable architecture.
The framework includes:
- <a href="#eggai-sdk">EggAI SDK</a>:  A lightweight abstraction layer for building agents and enabling agent-to-agent communication.
- <a href="https://github.com/eggai-tech/eggai-examples">Examples</a>: Practical use cases showing how to use the SDK and integrate EggAI with leading AI frameworks.
- <a href="https://github.com/eggai-tech/eggai-demo">Demo</a>: A working multi-agent insurance support system showcasing the Meta Framework in action.

<p>
  <img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/eggai-meta-framework-arch.png" alt="EggAI Meta Framework Architecture" width="100%">
  <br>
  <em>EggAI Meta Framework design principles: framework-agnostic, async-first, distributed and composable</em>
</p>


## Demo: Multi-Agent Insurance Support System

To see the Egg AI Meta Framework in action, try our [Multi-Agent Insurance Support System](https://github.com/eggai-tech/eggai-demo).
This interactive demo showcases how EggAI can be used to orchestrate multiple specialized agents to provide
a personalized insurance support. It features billing inquiries, claims processing, policy information retrieval (RAG), and intelligent routing.

**[🎯 Try the Demo](https://github.com/eggai-tech/eggai-demo)**

![Multi-Agent Insurance Support System Demo Screenshot](https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/support-chat.png)


## Examples: AI Enablement in Action

EggAI's SDK is intentionally **simple**, **lightweight**, and **framework-agnostic**, making it easy to integrate with today's leading AI tools—and future-ready for what's next.
Here we show practical implementation scenarios and integration guides with popular AI frameworks.
Each example is self-contained and ready to run out of the box.
We encourage you to explore and **copy/paste** from our examples for your projects.

**[📚 Browse All Examples](https://github.com/eggai-tech/eggai-examples)**

If you're new to EggAI, we recommend starting with the [Getting Started](https://github.com/eggai-tech/eggai-examples/tree/main/getting_started) example to learn the basics of agent definition, communication flows and async orchestration.

<table style="width: 100%;">
  <tbody>
    <tr>
      <td style="width: 15%;">
        <a href="https://github.com/eggai-tech/eggai-examples/tree/main/getting_started">
          <img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/example-00.png" alt="Getting Started" width="80"/>
        </a>
      </td>
      <td>
        <a href="https://github.com/eggai-tech/eggai-examples/tree/main/getting_started"><strong>Getting Started</strong></a><br/>
        Orchestrate two agents asynchronously.<br/>
        <small>Tags: Communication</small>
      </td>
    </tr>
    <tr>
      <td>
        <a href="https://github.com/eggai-tech/eggai-examples/tree/main/coordinator">
          <img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/example-01.png" alt="Coordinator" width="80"/>
        </a>
      </td>
      <td>
        <a href="https://github.com/eggai-tech/eggai-examples/tree/main/coordinator"><strong>Coordinator</strong></a><br/>
        Bridge multiple communication channels.<br/>
        <small>Tags: Communication, Pattern</small>
      </td>
    </tr>
    <tr>
      <td>
        <a href="https://github.com/eggai-tech/eggai-examples/tree/main/websocket_gateway">
          <img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/example-02.png" alt="Websocket Gateway" width="80"/>
        </a>
      </td>
      <td>
        <a href="https://github.com/eggai-tech/eggai-examples/tree/main/websocket_gateway"><strong>Websocket Gateway</strong></a><br/>
        Real-time interaction via WebSockets.<br/>
        <small>Tags: Communication, Realtime</small>
      </td>
    </tr>
    <tr>
      <td>
        <a href="https://github.com/eggai-tech/eggai-examples/tree/main/dspy_react">
          <img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/react-agent-dspy.png" alt="DSPy ReAct" width="80"/>
        </a>
      </td>
      <td>
        <a href="https://github.com/eggai-tech/eggai-examples/tree/main/dspy_react"><strong>DSPy ReAct Agent</strong></a><br/>
        Advanced Agents with DSPy ReAct.<br/>
        <small>Tags: DSPy, Tool Calling, React</small>
      </td>
    </tr>
    <tr>
      <td>
        <a href="https://github.com/eggai-tech/eggai-examples/tree/main/langchain_tool_calling">
          <img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/example-03.png" alt="LangChain Tool Calling" width="80"/>
        </a>
      </td>
      <td>
        <a href="https://github.com/eggai-tech/eggai-examples/tree/main/langchain_tool_calling"><strong>LangChain Agent</strong></a><br/>
        Integrate tool calling with LangChain.<br/>
        <small>Tags: Tool Calling, LangChain</small>
      </td>
    </tr>
    <tr>
      <td>
        <a href="https://github.com/eggai-tech/eggai-examples/tree/main/litellm_agent">
          <img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/example-05.png" alt="LiteLLM Agent" width="80"/>
        </a>
      </td>
      <td>
        <a href="https://github.com/eggai-tech/eggai-examples/tree/main/litellm_agent"><strong>LiteLLM Agent</strong></a><br/>
        Power agents with LiteLLM.<br/>
        <small>Tags: LiteLLM</small>
      </td>
    </tr>
    <tr>
      <td>
        <a href="https://github.com/eggai-tech/eggai-examples/tree/main/agent_evaluation_dspy">
          <img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/agent-evaluation-dspy.png" alt="Agent Evaluation & DSPy" width="80"/>
        </a>
      </td>
      <td>
        <a href="https://github.com/eggai-tech/eggai-examples/tree/main/agent_evaluation_dspy"><strong>Agent Evaluation & Optimization with DSPy</strong></a><br/>
        Data-driven development with DSPy.<br/>
        <small>Tags: DSPy, Evaluation, Optimization</small>
      </td>
    </tr>
    <tr>
      <td>
        <a href="https://github.com/eggai-tech/eggai-examples/tree/main/safe_agents_guardrails">
          <img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/safe-agents-guardrails.png" alt="Safe Agents with Guardrails AI" width="80"/>
        </a>
      </td>
      <td>
        <a href="https://github.com/eggai-tech/eggai-examples/tree/main/safe_agents_guardrails"><strong>Safe Agents with Guardrails AI</strong></a><br/>
        Guarding LLM agents against toxicity and PII leakage.<br/>
        <small>Tags: DSPy, Guardrails</small>
      </td>
    </tr>
    <tr>
      <td>
        <a href="https://github.com/eggai-tech/eggai-examples/tree/main/triage_agent">
          <img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/triage-agent.png" alt="Triage Agent" width="80"/>
        </a>
      </td>
      <td>
        <a href="https://github.com/eggai-tech/eggai-examples/tree/main/triage_agent"><strong>Triage Agent</strong></a><br/>
        Triage Agent with classification and routing.<br/>
        <small>Tags: Classification, Routing</small>
      </td>
    </tr>
    <tr>
      <td>
        <a href="https://github.com/eggai-tech/eggai-examples/tree/main/shared_context">
          <img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/example-04.png" alt="Shared Context" width="80"/>
        </a>
      </td>
      <td>
        <a href="https://github.com/eggai-tech/eggai-examples/tree/main/shared_context"><strong>Shared Context</strong></a><br/>
        Maintain shared context across agents.<br/>
        <small>Tags: Communication, Memory</small>
      </td>
    </tr>
    <tr>
      <td>
        <a href="https://github.com/eggai-tech/eggai-examples/tree/main/multi_agent_conversation">
          <img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/example-06.png" alt="Multi-Agent Conversation" width="80"/>
        </a>
      </td>
      <td>
        <a href="https://github.com/eggai-tech/eggai-examples/tree/main/multi_agent_conversation"><strong>Multi-Agent Conversation</strong></a><br/>
        Context-aware multi-agent conversations.<br/>
        <small>Tags: Communication, Classification, Routing, Chat</small>
      </td>
    </tr>
  </tbody>
</table>

## EggAI SDK

**EggAI SDK** includes components like `Agent` and `Channel` for decoupled communication in multi-agent systems. Its slim design offers flexibility for enterprise-grade applications and seamless integration with popular AI frameworks such as [DSPy](https://dspy.ai/), [LangChain](https://www.langchain.com/), and [LlamaIndex](https://www.llamaindex.ai/), see examples below:

#### AI Framework Integrations

<details>
<summary>DSPy Agent</summary>

```python
# Install `eggai` and `dspy` and set OPENAI_API_KEY in the environment

import asyncio
import dspy
from eggai import Agent, Channel, eggai_main

dspy.configure(lm=dspy.LM("openai/gpt-4o-mini"))
qa_model = dspy.Predict("question -> answer")
agent, channel = Agent("QAAgent"), Channel()

@agent.subscribe(filter_by_message=lambda event: event.get("event_name") == "question_created")
async def handle_question(event):
    question = event["payload"]["question"]
    answer = qa_model(question=question).answer
    print(f"[QAAgent] Question: {question} | Answer: {answer}")

    await channel.publish({
        "event_name": "answer_generated",
        "payload": {"question": question, "answer": answer}
    })

@eggai_main
async def main():
    await agent.start()
    await channel.publish({
        "event_name": "question_created",
        "payload": {"question": "When was the Eiffel Tower built?"}
    })
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
```

</details>

<details>
<summary>LangChain Agent</summary>

```python
# Install `eggai` and `langchain` and set OPENAI_API_KEY in the environment

import asyncio
from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage
from eggai import Agent, Channel, eggai_main

llm = ChatOpenAI(model_name="gpt-4o", temperature=0)
agent, channel = Agent("QAAgent"), Channel()

@agent.subscribe(filter_by_message=lambda event: event.get("event_name") == "question_created")
async def handle_question(event):
    question = event["payload"]["question"]
    answer = llm([HumanMessage(content=question)]).content

    print(f"[QAAgent] Question: {question} | Answer: {answer}")

    await channel.publish({
        "event_name": "answer_generated",
        "payload": {"question": question, "answer": answer}
    })

@eggai_main
async def main():
    await agent.start()
    await channel.publish({
        "event_name": "question_created",
        "payload": {"question": "When was the Eiffel Tower built?"}
    })
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
```

</details>

<details>
<summary>LiteLLM Agent</summary>

```python
# Install `eggai` and `litellm` and set OPENAI_API_KEY in the environment

import asyncio
import litellm
from eggai import Agent, Channel, eggai_main

litellm.model = "gpt-4o"
agent, channel = Agent("QAAgent"), Channel()

@agent.subscribe(filter_by_message=lambda event: event.get("event_name") == "question_created")
async def handle_question(event):
    question = event["payload"]["question"]
    answer = litellm.completion(model=litellm.model, messages=[{"role": "user", "content": question}])["choices"][0]["message"]["content"]

    print(f"[QAAgent] Question: {question} | Answer: {answer}")

    await channel.publish({
        "event_name": "answer_generated",
        "payload": {"question": question, "answer": answer}
    })

@eggai_main
async def main():
    await agent.start()
    await channel.publish({
        "event_name": "question_created",
        "payload": {"question": "When was the Eiffel Tower built?"}
    })
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
```

</details>

<details>
<summary>LlamaIndex Agent</summary>

```python
# Install `eggai` and `llama_index` and set OPENAI_API_KEY in the environment

import asyncio
from llama_index.llms.openai import OpenAI
from eggai import Agent, Channel, eggai_main

llm = OpenAI(model="gpt-4o")
agent, channel = Agent("QAAgent"), Channel()

@agent.subscribe(filter_by_message=lambda event: event.get("event_name") == "question_created")
async def handle_question(event):
    question = event["payload"]["question"]
    answer = llm.complete(question).text

    print(f"[QAAgent] Question: {question} | Answer: {answer}")

    await channel.publish({
        "event_name": "answer_generated",
        "payload": {"question": question, "answer": answer}
    })

@eggai_main
async def main():
    await agent.start()
    await channel.publish({
        "event_name": "question_created",
        "payload": {"question": "When was the Eiffel Tower built?"}
    })
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
```

</details>

#### AI Agent Evaluations

<details>
<summary>Agent Evaluation using LLM-as-a-Judge metrics</summary>

```python
# Install `eggai` and `dspy` and set OPENAI_API_KEY in the environment
# Make sure to have the agent implementation in the `agent.py` file defined

import asyncio
import pytest
import dspy
from agent import agent
from eggai import Agent, Channel

dspy.configure(lm=dspy.LM("openai/gpt-4o-mini"))

ground_truth = [
    {"question": "When was the Eiffel Tower built?", "answer": "The Eiffel Tower was built between 1887 and 1889."},
    {"question": "Who wrote Hamlet?", "answer": "Hamlet was written by William Shakespeare."},
    {"question": "What is the capital of France?", "answer": "The capital of France is Paris."},
]

class EvaluationSignature(dspy.Signature):
    question: str = dspy.InputField(desc="Ground truth question.")
    agent_answer: str = dspy.InputField(desc="Agent-generated answer.")
    ground_truth_answer: str = dspy.InputField(desc="Expected correct answer.")

    judgment: bool = dspy.OutputField(desc="Pass (True) or Fail (False).")
    reasoning: str = dspy.OutputField(desc="Detailed justification in Markdown.")
    precision_score: float = dspy.OutputField(desc="Precision score (0.0 to 1.0).")

test_agent = Agent("TestAgent")
test_channel = Channel()
event_received = asyncio.Event()
received_event = None

@test_agent.subscribe(filter_by_message=lambda event: event.get("event_name") == "answer_generated")
async def handle_answer(event):
    global received_event
    received_event = event
    event_received.set()

@pytest.mark.asyncio
async def test_qa_agent():
    await agent.start()
    await test_agent.start()

    for item in ground_truth:
        event_received.clear()

        await test_channel.publish({"event_name": "question_created", "payload": {"question": item["question"]}})

        try:
            await asyncio.wait_for(event_received.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            pytest.fail(f"Timeout: No 'answer_generated' event was published for question: {item['question']}")

        assert received_event is not None, "No 'answer_generated' event was received."
        assert received_event["event_name"] == "answer_generated", "Unexpected event type received."
        assert "answer" in received_event["payload"], "The 'answer' key is missing in the payload."

        agent_answer = received_event["payload"]["answer"]
        question = received_event["payload"]["question"]
        ground_truth_answer = item["answer"]

        assert question == item["question"], f"Incorrect question in the answer payload: {question}"

        eval_model = dspy.asyncify(dspy.Predict(EvaluationSignature))
        evaluation_result = await eval_model(
            question=question,
            agent_answer=agent_answer,
            ground_truth_answer=ground_truth_answer
        )

        assert evaluation_result.judgment, "Judgment must be True. " + evaluation_result.reasoning
        assert 0.8 <= evaluation_result.precision_score <= 1.0, "Precision score must be between 0.8 and 1.0."
```

</details>

### Installation

Install `eggai` via pip:

```bash
pip install eggai
```

For local development, clone the repository and install the package in editable mode:

```bash
pip install -e .
```

### Getting Started

For a quick start with a structured project, use the EggAI CLI to generate a new multi-agent application:

```bash
pipx run eggai[cli] init
```

This will create a complete project with agents, console interface, and configuration files.

Alternatively, here's how you can quickly set up an agent to handle events in an event-driven system:

```python
import asyncio

from eggai import Agent, Channel, eggai_main

agent = Agent("OrderAgent")
channel = Channel()

@agent.subscribe(filter_by_message=lambda e: e.get("type") == "order_requested")
async def handle_order_requested(event):
    print(f"[ORDER AGENT]: Received order request. Event: {event}")
    await channel.publish({"type": "order_created", "payload": event})


@agent.subscribe(filter_by_message=lambda e: e.get("type") == "order_created")
async def handle_order_created(event):
    print(f"[ORDER AGENT]: Order created. Event: {event}")


@eggai_main
async def main():
    await agent.start()
    await channel.publish({
        "type": "order_requested",
        "payload": {
            "product": "Laptop",
            "quantity": 1
        }
    })

    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
```

Copy this snippet into your project, customize it, and you’re good to go!

### Core Concepts

An `Agent` is an autonomous unit of business logic designed to orchestrate workflows, process events, and communicate with external systems such as Large Language Models (LLMs) and APIs. It reduces boilerplate code while supporting complex and long-running workflows. Key features include:

- **Event Handling**: Use the `subscribe` decorator to bind user-defined handlers to specific events.
- **Workflow Orchestration**: Manage long-running workflows and tasks efficiently.
- **External System Communication**: Seamlessly interact with Large Language Models (LLMs), external APIs, and other systems.
- **Lifecycle Management**: Automatically handle the lifecycle of Kafka consumers, producers, and other connected components.
- **Boilerplate Reduction**: Focus on core business logic while leveraging built-in integrations for messaging and workflows.

A `Channel` is the foundational communication layer that facilitates both event publishing and subscription.
It abstracts Kafka producers and consumers, enabling efficient and flexible event-driven operations. Key features include:

- **Event Communication**: Publish events to Kafka topics with ease.
- **Event Subscription**: Subscribe to Kafka topics and process events directly through the `Channel`.
- **Shared Resources**: Optimize resource usage by managing singleton Kafka producers and consumers across multiple agents or channels.
- **Seamless Integration**: Act as a communication hub, supporting both Agents and other system components.
- **Flexibility**: Allow Agents to leverage Channels for both publishing and subscribing, reducing complexity and duplication.

### **Interoperability**

In enterprise environments, diverse programming languages and frameworks create fragmentation. EggAI Agents serve as thin, flexible connectors, enabling seamless integration within the multi-agent system. This ensures enterprises can continuously enhance their AI capabilities without the need for costly re-platforming.

If you use the Kafka transport, you can directly integrate using Kafka libraries available for various programming languages:

- [Python: `confluent-kafka`](https://github.com/confluentinc/confluent-kafka-python)
- [JavaScript / TypeScript: `kafkajs`](https://github.com/tulios/kafkajs)
- [Java / Kotlin: `kafka-clients`](https://mvnrepository.com/artifact/org.apache.kafka/kafka-clients)
- [Go: `sarama`](https://github.com/Shopify/sarama)
- [C#: `Confluent.Kafka`](https://github.com/confluentinc/confluent-kafka-dotnet)
- [Rust: `rdkafka`](https://github.com/fede1024/rust-rdkafka)

For structured communication within the multi-agent system, we recommend using the EggAI Message Base Schema, which defines a standardized message format for consistency and interoperability.

<details>
  <summary>View EggAI Message Base Schema</summary>

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "MessageBase",
  "description": "Base class for all messages in the communication protocol.",
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "format": "uuid",
      "description": "Unique identifier for correlating requests and responses."
    },
    "type": {
      "type": "string",
      "description": "Type of the message (e.g., request, response, event)."
    },
    "metadata": {
      "type": "object",
      "additionalProperties": true,
      "description": "Additional metadata for the message."
    },
    "context": {
      "type": "object",
      "additionalProperties": true,
      "description": "Contextual information for the message."
    },
    "payload": {
      "type": "object",
      "additionalProperties": true,
      "description": "Message-specific data."
    }
  },
  "required": ["id", "type"]
}
```

</details>

### Why Copy/Paste?

**1. Full Ownership and Control**  
By copying and pasting, you have direct access to the underlying implementation. Tweak or rewrite as you see fit, the code is truly yours.

**2. Separation of Concerns**  
Just like decoupling design from implementation, copying code (rather than installing a monolithic dependency) reduces friction if you want to restyle or refactor how agents are structured.

**3. Flexibility**  
Not everyone wants a one-size-fits-all library. With copy/paste “recipes,” you can integrate only the parts you need.

**4. No Hidden Coupling**  
Sometimes, prepackaged frameworks lock in design decisions. By copying from examples, you choose exactly what gets included and how it’s used.

<!--end-->

## Contribution

`EggAI Multi-Agent Meta Framework` is open-source and we welcome contributions. If you're looking to contribute, please refer to [CONTRIBUTING.md](CONTRIBUTING.md).

## License

This project is licensed under the MIT License. See the [LICENSE.md](LICENSE.md) file for details.
