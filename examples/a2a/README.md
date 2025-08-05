# EggAI A2A (Agent-to-Agent) Text Processing Example

This example demonstrates how to create an EggAI agent with A2A (Agent-to-Agent) support for text-based operations, enabling it to expose skills that process text directly without complex data structures.

## Overview

The demo includes:
- A simple EggAI agent with three text-based A2A skills:
  - **Greet**: Creates personalized greetings based on input names
  - **Reverse**: Reverses any input text
  - **Analyze**: Provides text statistics (character count, word count, etc.)
- An A2A client that connects to the agent and tests all skills

## Prerequisites

- Python 3.8+

## Installation

This example uses the local EggAI SDK from the repository:

```bash
pip install -r requirements.txt
```

This will install:
- EggAI SDK from the local `../../sdk` directory (in editable mode)
- A2A SDK and other dependencies

## Running the Example

The example uses EggAI's InMemoryTransport, so no external message broker is needed.

1. In one terminal, start the A2A-enabled agent:
```bash
python simple_demo.py
```

2. In another terminal, run the client:
```bash
python client.py
```

## What the Demo Does

### The Agent

The agent creates three simple text processing skills:

1. **Greeter** - Takes a name and returns a personalized greeting
   - Special handling for "World" 
   - Different responses for long names
   - Friendly greetings for regular names

2. **Reverser** - Takes any text and returns it reversed
   - Simple but useful for demonstrating text transformation

3. **Analyzer** - Takes text and returns statistics
   - Character count
   - Word count
   - Average word length

### The Client

The client demonstrates all skills by:
- Greeting different names (Alice, World, and a long name)
- Reversing various texts including palindromes
- Analyzing a pangram sentence

## How It Works

### Simple Text Messages

Unlike complex JSON structures, this example uses simple text strings:

```python
class TextMessage(BaseMessage[str]):
    type: str = "text.message"
```

### Skill Registration

Skills are registered with the `a2a_capability` parameter:

```python
@agent.subscribe(
    channel=Channel("greetings"), 
    data_type=TextMessage, 
    a2a_capability="greet"
)
async def greet(message: TextMessage) -> str:
    name = message.data.strip()
    # Process and return greeting
```

### Direct Text Returns

Skills return plain strings instead of complex objects:

```python
async def reverse(message: TextMessage) -> str:
    return message.data[::-1]  # Simply return reversed text
```

## Extending the Example

You can extend this example by adding more text processing skills:
- Text case converter (upper/lower/title)
- Word counter or frequency analyzer
- Simple text encryption/decryption
- Language detection
- Sentiment analysis (with appropriate libraries)
- Text summarization