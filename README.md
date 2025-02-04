<img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/eggai-word-and-figuremark.svg" alt="EggAI word and figuremark" width="200px" style="margin-bottom: 16px;" />

# Multi-Agent Meta Framework

Documentation: [EggAI Docs](https://docs.egg-ai.com/)

<!--start-->

[![Python 3.x](https://img.shields.io/badge/python-3.x-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge&logo=opensourceinitiative&logoColor=white)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen?style=for-the-badge&logo=github&logoColor=white)](https://github.com/eggai-tech/eggai/pulls)
[![GitHub Issues](https://img.shields.io/github/issues/eggai-tech/eggai?style=for-the-badge&logo=github&logoColor=white)](https://github.com/eggai-tech/eggai/issues)
[![GitHub Stars](https://img.shields.io/github/stars/eggai-tech/eggai?style=for-the-badge&logo=github&logoColor=white)](https://github.com/eggai-tech/eggai/stargazers)

`EggAI Multi-Agent Meta Framework` is an async-first meta framework for building enterprise-grade multi-agent systems. It provides:

- <a href="#examples">Examples</a>: Practical implementation scenarios using popular AI frameworks such as DSPy, LiteLLM and LangChain.
- <a href="#eggai-sdk">eggai SDK</a>: Slim SDK for asynchronous, distributed multi-agent communication with Kafka and InMemory transports.

### Features

- 🤖 **Multi-Agent Orchestration**: Designed for seamless multi-agent collaboration.
- 🚀 **Async-First**: Push-based APIs optimized for high-concurrency, long-running, and real-time processes.
- ⚡ **Event-Driven**: Adaptive and responsive system behaviors triggered by real-time events.
- 📈 **Horizontally Scalable**: Seamless scaling of agent execution to meet growing demands.
- 🛠 **Flexible Architecture**: Adaptable and extensible components without disrupting workflows.
- 🔄 **Resilient**: Built-in retry mechanisms and fault tolerance ensuring reliability.
- 🚇 **Kafka Integration**: Native support for message streaming with Kafka.

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

<!--end-->

### Why Copy/Paste?

**1. Full Ownership and Control**  
By copying and pasting, you have direct access to the underlying implementation. Tweak or rewrite as you see fit, the code is truly yours.

**2. Separation of Concerns**  
Just like decoupling design from implementation, copying code (rather than installing a monolithic dependency) reduces friction if you want to restyle or refactor how agents are structured.

**3. Flexibility**  
Not everyone wants a one-size-fits-all library. With copy/paste “recipes,” you can integrate only the parts you need.

**4. No Hidden Coupling**  
Sometimes, prepackaged frameworks lock in design decisions. By copying from examples, you choose exactly what gets included and how it’s used.

## Contribution

`EggAI Multi-Agent Meta Framework` is open-source and we welcome contributions. If you're looking to contribute, please refer to [CONTRIBUTING.md](CONTRIBUTING.md).

## License

This project is licensed under the MIT License. See the [LICENSE.md](LICENSE.md) file for details.
