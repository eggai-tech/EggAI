<img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/eggai-word-and-figuremark.svg" alt="EggAI word and figuremark" width="200px" style="margin-bottom: 16px;" />

# Multi-Agent Meta Framework

Documentation: [EggAI Docs](https://docs.egg-ai.com/)

<!--start-->

[![Python 3.x](https://img.shields.io/badge/python-3.x-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge&logo=opensourceinitiative&logoColor=white)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen?style=for-the-badge&logo=github&logoColor=white)](https://github.com/eggai-tech/eggai/pulls)
[![GitHub Issues](https://img.shields.io/github/issues/eggai-tech/eggai?style=for-the-badge&logo=github&logoColor=white)](https://github.com/eggai-tech/eggai/issues)
[![GitHub Stars](https://img.shields.io/github/stars/eggai-tech/eggai?style=for-the-badge&logo=github&logoColor=white)](https://github.com/eggai-tech/eggai/stargazers)

`EggAI Multi-Agent Meta Framework` makes it easy to build enterprise-grade multi-agent systems with quality-controlled output, using an async-first, distributed and composable architecture. It provides:

- <a href="#examples">Examples</a>: Practical implementation scenarios using popular AI frameworks.
- <a href="#eggai-sdk">eggai SDK</a>: Slim SDK for asynchronous, distributed multi-agent communication.

### Meta Framework

The EggAI Multi-Agent Meta Framework is a framework-agnostic AI orchestration layer designed for flexibility and scalability. It enables seamless integration with popular AI frameworks.

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

@agent.subscribe(filter_func=lambda event: event.get("event_name") == "question_created")
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

@agent.subscribe(filter_func=lambda event: event.get("event_name") == "question_created")
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

@agent.subscribe(filter_func=lambda event: event.get("event_name") == "question_created")
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

@agent.subscribe(filter_func=lambda event: event.get("event_name") == "question_created")
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

@test_agent.subscribe(filter_func=lambda event: event.get("event_name") == "answer_generated")
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

## Examples

Practical implementation scenarios and integration guides with popular AI frameworks. We encourage you to explore and **copy/paste** from our examples for your projects.

If you're new to EggAI, we recommend starting with the [Getting Started](examples/getting_started) example to learn the basics. If you want to see a more extensive multi-agent system in action, check out the [Multi-Agent Insurance Support System](examples/multi_agent_human_chat) example.

<table style="width: 100%;">
  <tbody>
    <tr>
      <td style="width: 15%;">
        <a href="examples/getting_started">
          <img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/example-00.png" alt="Getting Started" width="80"/>
        </a>
      </td>
      <td>
        <a href="examples/getting_started"><strong>Getting Started</strong></a><br/>
        Orchestrate two agents asynchronously.<br/>
        <small>Tags: Communication</small>
      </td>
    </tr>
    <tr>
      <td>
        <a href="examples/coordinator">
          <img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/example-01.png" alt="Coordinator" width="80"/>
        </a>
      </td>
      <td>
        <a href="examples/coordinator"><strong>Coordinator</strong></a><br/>
        Bridge multiple communication channels.<br/>
        <small>Tags: Communication, Pattern</small>
      </td>
    </tr>
    <tr>
      <td>
        <a href="examples/websocket_gateway">
          <img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/example-02.png" alt="Websocket Gateway" width="80"/>
        </a>
      </td>
      <td>
        <a href="examples/websocket_gateway"><strong>Websocket Gateway</strong></a><br/>
        Real-time interaction via WebSockets.<br/>
        <small>Tags: Communication, Realtime</small>
      </td>
    </tr>
    <tr>
      <td>
        <a href="examples/dspy_react">
          <img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/react-agent-dspy.png" alt="DSPy ReAct" width="80"/>
        </a>
      </td>
      <td>
        <a href="examples/dspy_react"><strong>DSPy ReAct Agent</strong></a><br/>
        Advanced Agents with DSPy ReAct.<br/>
        <small>Tags: DSPy, Tool Calling, React</small>
      </td>
    </tr>
    <tr>
      <td>
        <a href="examples/langchain_tool_calling">
          <img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/example-03.png" alt="LangChain Tool Calling" width="80"/>
        </a>
      </td>
      <td>
        <a href="examples/langchain_tool_calling"><strong>LangChain Agent</strong></a><br/>
        Integrate tool calling with LangChain.<br/>
        <small>Tags: Tool Calling, LangChain</small>
      </td>
    </tr>
    <tr>
      <td>
        <a href="examples/litellm_agent">
          <img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/example-05.png" alt="LiteLLM Agent" width="80"/>
        </a>
      </td>
      <td>
        <a href="examples/litellm_agent"><strong>LiteLLM Agent</strong></a><br/>
        Power agents with LiteLLM.<br/>
        <small>Tags: LiteLLM</small>
      </td>
    </tr>
    <tr>
      <td>
        <a href="examples/agent_evaluation_dspy">
          <img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/agent-evaluation-dspy.png" alt="Agent Evaluation & DSPy" width="80"/>
        </a>
      </td>
      <td>
        <a href="examples/agent_evaluation_dspy"><strong>Agent Evaluation & Optimization with DSPy</strong></a><br/>
        Data-driven development with DSPy.<br/>
        <small>Tags: DSPy, Evaluation, Optimization</small>
      </td>
    </tr>
    <tr>
      <td>
        <a href="examples/safe_agents_guardrails">
          <img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/safe-agents-guardrails.png" alt="Safe Agents with Guardrails AI" width="80"/>
        </a>
      </td>
      <td>
        <a href="examples/safe_agents_guardrails"><strong>Safe Agents with Guardrails AI</strong></a><br/>
        Guarding LLM agents against toxicity and PII leakage.<br/>
        <small>Tags: DSPy, Guardrails</small>
      </td>
    </tr>
    <tr>
      <td>
        <a href="examples/triage_agent">
          <img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/triage-agent.png" alt="Triage Agent" width="80"/>
        </a>
      </td>
      <td>
        <a href="examples/triage_agent"><strong>Triage Agent</strong></a><br/>
        Triage Agent with classification and routing.<br/>
        <small>Tags: Classification, Routing</small>
      </td>
    </tr>
    <tr>
      <td>
        <a href="examples/shared_context">
          <img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/example-04.png" alt="Shared Context" width="80"/>
        </a>
      </td>
      <td>
        <a href="examples/shared_context"><strong>Shared Context</strong></a><br/>
        Maintain shared context across agents.<br/>
        <small>Tags: Communication, Memory</small>
      </td>
    </tr>
    <tr>
      <td>
        <a href="examples/multi_agent_conversation">
          <img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/example-06.png" alt="Multi-Agent Conversation" width="80"/>
        </a>
      </td>
      <td>
        <a href="examples/multi_agent_conversation"><strong>Multi-Agent Conversation</strong></a><br/>
        Context-aware multi-agent conversations.<br/>
        <small>Tags: Communication, Classification, Routing, Chat</small>
      </td>
    </tr>
    <tr>
      <td>
        <a href="examples/multi_agent_human_chat">
          <img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/multi-agent-human-chat.png" alt="Multi-Agent Insurance Support System" width="80"/>
        </a>
      </td>
      <td>
        <a href="examples/multi_agent_human_chat"><strong>Multi-Agent Insurance Support System</strong></a><br/>
        Insurance support system with a support chat UI.<br/>
        <small>Tags: Communication, Realtime, Classification, Routing, Chat</small>
      </td>
    </tr>
  </tbody>
</table>

## EggAI SDK

**EggAI SDK** includes components like `Agent` and `Channel` for decoupled communication in multi-agent systems. Its slim design offers flexibility for enterprise-grade applications and seamless integration with popular AI frameworks such as [DSPy](https://dspy.ai/), [LangChain](https://www.langchain.com/), and [LlamaIndex](https://www.llamaindex.ai/).


### Installation

Install `eggai` via pip:

```bash
pip install eggai
```

### Getting Started

Here's how you can quickly set up an agent to handle events in an event-driven system:

```python
import asyncio

from eggai import Agent, Channel, eggai_main

agent = Agent("OrderAgent")
channel = Channel()

@agent.subscribe(filter_func=lambda e: e.get("event_name") == "order_requested")
async def handle_order_requested(event):
    print(f"[ORDER AGENT]: Received order request. Event: {event}")
    await channel.publish({"event_name": "order_created", "payload": event})


@agent.subscribe(filter_func=lambda e: e.get("event_name") == "order_created")
async def handle_order_created(event):
    print(f"[ORDER AGENT]: Order created. Event: {event}")


@eggai_main
async def main():
    await agent.start()
    await channel.publish({
        "event_name": "order_requested",
        "payload": {
            "product": "Laptop",
            "quantity": 1
        }
    })

    await asyncio.Future() # Keep the event loop running

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
