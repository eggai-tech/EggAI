# EggAI Multi-Agent Meta Framework 🤖

[![Python 3.x](https://img.shields.io/badge/python-3.x-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge&logo=opensourceinitiative&logoColor=white)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen?style=for-the-badge&logo=github&logoColor=white)](https://github.com/eggai-tech/eggai/pulls)
[![GitHub Issues](https://img.shields.io/github/issues/eggai-tech/eggai?style=for-the-badge&logo=github&logoColor=white)](https://github.com/eggai-tech/eggai/issues)
[![GitHub Stars](https://img.shields.io/github/stars/eggai-tech/eggai?style=for-the-badge&logo=github&logoColor=white)](https://github.com/eggai-tech/eggai/stargazers)

`EggAI Multi-Agent Meta Framework` is an async-first meta framework for building, deploying, and scaling multi-agent systems for modern enterprise environments. It integrates seamlessly with popular AI libraries and includes extensive [examples](examples) to help you move quickly while staying flexible

## Table of Contents

[Features](#-features) •
[Overview](#-overview) •
[System Architecture](#-system-architecture) •
[Installation](#-installation) •
[Getting Started](#-getting-started) •
[Core Concepts](#-core-concepts) •
[Examples](#-examples) •
[Why Copy/Paste?](-why-copypaste) •
[Contribution](#-contribution) •
[License](#-license)

<!--start-->
## 🌟 Features

- 🤖 **Agent Management**: Simplify the orchestration and execution of multi-agent systems.
- 🚀 **Async-First**: Push-based APIs designed for high-concurrency, long-running and real-time processes.
- ⚡ **Event-Driven**: Enable adaptive and responsive system behaviors triggered by real-time events.
- 📈 **Horizontally Scalable**: Scale agent execution seamlessly to meet growing demands.
- 🚇 **Kafka Integration**: Native support for Kafka topics ensures seamless streaming and messaging.
- 🛠 **Flexible Architecture**: Easily adapt or extend components without disrupting workflows.
- 🔄 **Resilient by Design**: Built-in retry mechanisms and fault tolerance for production-grade robustness.

## 📖 Overview

`EggAI Multi-Agent Meta Framework` provides the `eggai` Python library that simplifies the development of multi-agent systems.
It allows developers to focus on business logic while handling the complexities of distributed systems.

## 🛠️ Meta-Framework Approach
EggAI is designed as a **meta-framework**, providing essential primitives like `Agent` and `Channel` to enable seamless communication within multi-agent systems. It also integrates easily with specialized frameworks like [DSPy](https://dspy.ai/), [LangChain](https://www.langchain.com/), or [LlamaIndex](https://www.llamaindex.ai/), so you can build a highly customizable and extensible environment tailored to your enterprise needs. 

## 🏗️ System Architecture

![System Architecture](./docs/assets/system-architecture.svg)

1. **Human Interaction**:

   - Users interact with the system via various **Human Channels**, such as chat interfaces or APIs, which are routed through the **Gateway**.

2. **Gateway**:

   - The Gateway acts as the entry point for all human communications and interfaces with the system to ensure secure and consistent message delivery.

3. **Coordinator**:

   - The **Coordinator** is the central component that manages the communication between humans and specialized agents.
   - It determines which agent(s) to involve and facilitates the interaction through the **Agent Channels**.

4. **Agents**:

   - The system is composed of multiple specialized agents (Agent 1, Agent 2, Agent 3), each responsible for handling specific types of tasks or functions.
   - Agents communicate with the Coordinator through their respective **Agent Channels**, ensuring scalability and modularity.

5. **Agent and Human Channels**:
   - **Human Channels** connect the Gateway to humans for interaction.
   - **Agent Channels** connect the Coordinator to agents, enabling task-specific processing and delegation.

## 📦 Installation

Install `eggai` via pip:

```bash
pip install eggai
```

## 🚀 Getting Started

Here's how you can quickly set up an agent to handle events in an event-driven system:

```python
import asyncio

from eggai import Agent, Channel

agent = Agent("OrderAgent")
channel = Channel()

@agent.subscribe(event_name="order_requested")
async def handle_order_requested(event):
    print(f"[ORDER AGENT]: Received order request. Event: {event}")
    await channel.publish({"event_name": "order_created", "payload": event})

@agent.subscribe(event_name="order_created")
async def handle_order_created(event):
    print(f"[ORDER AGENT]: Order created. Event: {event}")

async def main():
    await agent.run()
    await channel.publish({
        "event_name": "order_requested",
        "payload": {
            "product": "Laptop",
            "quantity": 1
        }
    })

    try:
        print("Agent is running. Press Ctrl+C to stop.")
        await asyncio.Event().wait()
    except asyncio.exceptions.CancelledError:
        print("Task was cancelled. Cleaning up...")
    finally:
        # Clean up resources
        await agent.stop()
        await channel.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

Copy this snippet into your project, customize it, and you’re good to go!

## 💡 Core Concepts

### 🤖 Agent

An `Agent` is an isolated unit of business logic designed to orchestrate workflows, process events, and communicate with external systems such as LLMs and APIs.
It reduces boilerplate while supporting complex and long-running workflows. Key features include:

- **Event Handling**: Use the `subscribe` decorator to bind user-defined handlers to specific events.  
- **Workflow Orchestration**: Manage long-running workflows and tasks efficiently.  
- **External System Communication**: Seamlessly interact with Large Language Models (LLMs), external APIs, and other systems.  
- **Lifecycle Management**: Automatically handle the lifecycle of Kafka consumers, producers, and other connected components.  
- **Boilerplate Reduction**: Focus on core business logic while leveraging built-in integrations for messaging and workflows.  

### 🚇 Channel

A `Channel` is the foundational communication layer that facilitates both event publishing and subscription.
It abstracts Kafka producers and consumers, enabling efficient and flexible event-driven operations. Key features include:

- **Event Communication**: Publish events to Kafka topics with ease.  
- **Event Subscription**: Subscribe to Kafka topics and process events directly through the `Channel`.  
- **Shared Resources**: Optimize resource usage by managing singleton Kafka producers and consumers across multiple agents or channels.  
- **Seamless Integration**: Act as a communication hub, supporting both Agents and other system components.  
- **Flexibility**: Allow Agents to leverage Channels for both publishing and subscribing, reducing complexity and duplication.  


<!--end-->
## 👀 Examples

We encourage you to **copy/paste** from our [examples folder](examples), which includes:

- [Getting Started](examples/00-getting-started/README.md): Orchestrate two agents asynchronously.
- [Coordinator](examples/01-coordinator/README.md): Bridge multiple communication channels.
- [Websocket Gateway](examples/02-websocket-gateway/README.md): Real-time interaction via WebSockets.
- [LangChain Tool Calling](examples/03-langchain-tool-calling/README.md): Integrate tool calling with [LangChain](https://www.langchain.com/).
- [Shared Context](examples/04-context/README.md): Maintain shared context across agents.
- [LiteLLM Integration](examples/05-litellm-agent/README.md): Power agents with [LiteLLM](https://www.litellm.ai/).
- [Multi-Agent Conversation](examples/06-multi-agent-conversation/README.md): Context aware multi-agent conversations.

## 📋 Why Copy/Paste?

**1. Full Ownership and Control**  
By copying and pasting, you have direct access to the underlying implementation. Tweak or rewrite as you see fit, the code is truly yours.

**2. Separation of Concerns**  
Just like decoupling design from implementation, copying code (rather than installing a monolithic dependency) reduces friction if you want to restyle or refactor how agents are structured.

**3. Flexibility**  
Not everyone wants a one-size-fits-all library. With copy/paste “recipes,” you can integrate only the parts you need.

**4. No Hidden Coupling**  
Sometimes, prepackaged frameworks lock in design decisions. By copying from examples, you choose exactly what gets included and how it’s used.

## 🤝 Contribution

`EggAI Multi-Agent Meta Framework` is open-source and we welcome contributions. If you're looking to contribute, please refer to [CONTRIBUTING.md](CONTRIBUTING.md).

## ⚖️ License

This project is licensed under the MIT License. See the [LICENSE.md](LICENSE.md) file for details.
