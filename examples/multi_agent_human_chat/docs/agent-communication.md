# Multi-Agent Communication

In systems where multiple agents work together, there are different ways for them to communicate.  
This example uses Kafka to send and receive messages between agents.

## Transport Layer

Kafka is used to move messages between agents. It offers many benefits, especially for larger systems:

- Reliable message delivery
- Support for distributed systems
- Easy to scale
- Can retry messages if something goes wrong
- Handles errors and system failures well

Messages use the CloudEvents protocol, which is a common standard in the industry.

## Message Classification

In a system with multiple agents, each incoming message needs to be sent to the right agent.  
To do that, the system must decide which agent should handle the message.

There are different ways to do this. For example:

- Use regular expressions and basic language processing
- Ask a large language model (LLM) to decide the right agent

EggAI uses a flexible pattern. It looks at the message (or message history) and decides what kind of message it is.  
Here are some example message types:

- `billing_request`
- `policy_request`
- `claim_request`
- `ticketing_request`
- Any other message (like greetings) is left unclassified

## Decoupling Agents with Event-Driven Design

Once a message is labeled with a type, it can be sent out without knowing which agent will receive it.  
Agents subscribe only to the types of messages they are interested in. This keeps them separate and independent.

This is called an event-driven design.

It also means agents can act like parts of a decision tree. One agent can forward a message to another agent after doing a more detailed classification.

This approach combines the flexibility of AI with a clear structure that is easier to control and maintain.

## Context and State

This example uses a simple setup to make it easy to understand and share.  
The full conversation history is sent with each message to the agent.

In real systems, only part of the history or a summary may be sent.

The agents themselves are built to be stateless. This means they don’t keep information between messages.  
However, during a single request, they do keep a temporary internal state. For example, when the agent talks to the LLM, it runs in a loop where the LLM is called multiple times and tools may be used.

So while they seem stateless, they actually manage a short-lived internal state while processing a request.
