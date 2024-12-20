# EggAI Multi-Agent Framework 🤖

[![Python 3.x](https://img.shields.io/badge/python-3.x-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge&logo=opensourceinitiative&logoColor=white)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen?style=for-the-badge&logo=github&logoColor=white)](https://github.com/eggai-tech/eggai/pulls)
[![GitHub Issues](https://img.shields.io/github/issues/eggai-tech/eggai?style=for-the-badge&logo=github&logoColor=white)](https://github.com/eggai-tech/eggai/issues)
[![GitHub Stars](https://img.shields.io/github/stars/eggai-tech/eggai?style=for-the-badge&logo=github&logoColor=white)](https://github.com/eggai-tech/eggai/stargazers)

`EggAI Multi-Agent Framework` is an async-first meta framework for building, deploying, and scaling multi-agent systems for modern enterprise environments.

## Table of Contents

[Features](#-features) •
[Overview](#-overview) •
[System Architecture](#-system-architecture) •
[Installation](#-installation) •
[Getting Started](#-getting-started) •
[Core Concepts](#-core-concepts) •
[Examples](#-examples) •
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

`EggAI Multi-Agent Framework` provides the `eggai` Python library that simplifies the development of multi-agent systems.
It allows developers to focus on business logic while handling the complexities of distributed systems.

## 🛠️ Meta-Framework Approach
EggAI is designed as a meta-framework, offering a robust baseline setup that includes essential primitives such as Agent and Channel classes. This foundational structure enables seamless communication within multi-agent systems while providing the flexibility to integrate and utilize various specialized frameworks like DSPy, LangChain, and LlamaIndex within each agent. By adopting a meta-framework architecture, EggAI ensures that developers can leverage the strengths of multiple tools and libraries, fostering a highly customizable and extensible development environment tailored to diverse enterprise needs.

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

This code demonstrates how to define an `Agent` and use it to process events from Kafka topics.

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

For detailed examples, please refer to [examples](examples).

## 🤝 Contribution

`EggAI Multi-Agent Framework` is open-source and we welcome contributions. If you're looking to contribute, please refer to [CONTRIBUTING.md](CONTRIBUTING.md).

## ⚖️ License

This project is licensed under the MIT License. See the [LICENSE.md](LICENSE.md) file for details.
