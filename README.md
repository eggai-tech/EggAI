<img src="docs/assets/eggai-word-and-figuremark.svg" alt="EggAI word and figuremark" width="200px" style="margin-bottom: 16px;" />

<!--start-->

# Multi-Agent Meta Framework

[![Python 3.x](https://img.shields.io/badge/python-3.x-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge&logo=opensourceinitiative&logoColor=white)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen?style=for-the-badge&logo=github&logoColor=white)](https://github.com/eggai-tech/eggai/pulls)
[![GitHub Issues](https://img.shields.io/github/issues/eggai-tech/eggai?style=for-the-badge&logo=github&logoColor=white)](https://github.com/eggai-tech/eggai/issues)
[![GitHub Stars](https://img.shields.io/github/stars/eggai-tech/eggai?style=for-the-badge&logo=github&logoColor=white)](https://github.com/eggai-tech/eggai/stargazers)

`EggAI Multi-Agent Meta Framework` is an async-first meta framework for building scalable multi-agent systems for modern enterprise environments. It provides:

- <a href="#eggai-sdk">eggai SDK</a>: Core primitives for asynchronous, distributed multi-agent communication.
- <a href="#examples">Examples</a>: Practical implementation scenarios and integration guides with popular AI frameworks.

## Features

- 🚀 **Async-First**: Push-based APIs optimized for high-concurrency, long-running, and real-time processes.
- 🤖 **Agent Management**: Streamlined orchestration and execution of multi-agent systems.
- ⚡ **Event-Driven**: Adaptive and responsive system behaviors triggered by real-time events.
- 📈 **Horizontally Scalable**: Seamless scaling of agent execution to meet growing demands.
- 🛠 **Flexible Architecture**: Adaptable and extensible components without disrupting workflows.
- 🔄 **Resilient**: Built-in retry mechanisms and fault tolerance ensuring reliability.
- 🚇 **Kafka Integration**: Native support for efficient streaming and messaging with Kafka.

## EggAI SDK

**EggAI SDK** includes core components like `Agent` and `Channel` for decoupled communication in multi-agent systems. Its slim design offers flexibility for enterprise-grade applications and seamless integration with popular AI frameworks such as [DSPy](https://dspy.ai/), [LangChain](https://www.langchain.com/), and [LlamaIndex](https://www.llamaindex.ai/).

### Installation

Install `eggai` via pip:

```bash
pip install eggai
```

### Getting Started

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

### Core Concepts

An `Agent` is an isolated unit of business logic designed to orchestrate workflows, process events, and communicate with external systems such as LLMs and APIs.
It reduces boilerplate while supporting complex and long-running workflows. Key features include:

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

## Examples

We encourage you to explore and **copy/paste** from our examples for practical implementation scenarios and integration guides with popular AI frameworks.

<table>
  <tbody>
    <tr>
      <td>
        <a href="examples/00-getting-started"><strong>Getting Started</strong></a>:<br/>
        Orchestrate two agents asynchronously.
      </td>
      <td>
        <a href="examples/00-getting-started">
          <img src="docs/assets/example-00.png" alt="Getting Started Example"/>
        </a>
      </td>
    </tr>
    <tr>
      <td>
        <a href="examples/01-coordinator"><strong>Coordinator</strong></a>:<br/>
        Bridge multiple communication channels.
      </td>
      <td>
        <a href="examples/01-coordinator">
          <img src="docs/assets/example-01.png" alt="Coordinator Example"/>
        </a>
      </td>
    </tr>
    <tr>
      <td>
        <a href="examples/02-websocket-gateway"><strong>Websocket Gateway</strong></a>:<br/>
        Real-time interaction via WebSockets.
      </td>
      <td>
        <a href="examples/02-websocket-gateway">
          <img src="docs/assets/example-02.png" alt="Websocket Gateway Example"/>
        </a>
      </td>
    </tr>
    <tr>
      <td>
        <a href="examples/03-langchain-tool-calling"><strong>LangChain Tool Calling</strong></a>:<br/>
        Integrate tool calling with LangChain.
      </td>
      <td>
        <a href="examples/03-langchain-tool-calling">
          <img src="docs/assets/example-03.png" alt="LangChain Tool Calling Example"/>
        </a>
      </td>
    </tr>
    <tr>
      <td>
        <a href="examples/04-context"><strong>Shared Context</strong></a>:<br/>
        Maintain shared context across agents.
      </td>
      <td>
        <a href="examples/04-context">
          <img src="docs/assets/example-04.png" alt="Shared Context Example"/>
        </a>
      </td>
    </tr>
    <tr>
      <td>
        <a href="examples/05-litellm-agent"><strong>LiteLLM Agent</strong></a>:<br/>
        Power agents with LiteLLM.
      </td>
      <td>
        <a href="examples/05-litellm-agent">
          <img src="docs/assets/example-05.png" alt="LiteLLM Agent Example"/>
        </a>
      </td>
    </tr>
    <tr>
      <td>
        <a href="examples/06-multi-agent-conversation"><strong>Multi-Agent Conversation</strong></a>:<br/>
        Context aware multi-agent conversations.
      </td>
      <td>
        <a href="examples/06-multi-agent-conversation">
          <img src="docs/assets/example-06.png" alt="Multi-Agent Conversation Example"/>
        </a>
      </td>
    </tr>
    <tr>
      <td>
        <a href="examples/07-chat-with-agents"><strong>Insurance Company Support</strong></a>:<br/>
        Merges previous components to create an insurance support system with an intuitive user interface.
      </td>
      <td>
        <a href="examples/07-chat-with-agents">Example</a>
      </td>
    </tr>
    <tr>
      <td>
        <a href="examples/example_08_dspy"><strong>Agents Evaluation & DSPy</strong></a>:<br/>
        Demonstrates how to enhance agents and integrate DSPY for effective agent evaluation and improvement.
      </td>
      <td>
        <a href="examples/example_08_dspy">Example</a>
      </td>
    </tr>
  </tbody>
</table>

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
