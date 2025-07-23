# Demo: DSPy ReAct Agent with External Tools

This demo showcases a **real DSPy ReAct agent** that can reason and use external tools through the adapter system.

## What's Different from Simple Demo

### Simple Demo (`simple_demo_agent.py`)
- Rule-based tool selection
- Basic string parsing
- Manual tool execution

### ReAct Demo (`run_react_demo.py`) 
- **Real DSPy ReAct reasoning**
- **Intelligent tool selection**
- **Step-by-step problem solving**
- **Natural language understanding**

## Architecture

```
┌─────────────────────┐    ┌──────────────────────┐    ┌─────────────────┐
│  Console Interface  │    │   DSPy ReAct Agent   │    │    Adapters     │
│                     │    │                      │    │                 │
│ • User Input        │◄──►│ • Think about task   │◄──►│ • MockAPI       │
│ • Display Response  │    │ • Choose tools       │    │ • MCP Servers   │
│ • Thinking Indicator│    │ • Execute reasoning  │    │ • REST APIs     │
│                     │    │ • Generate response  │    │                 │
└─────────────────────┘    └──────────────────────┘    └─────────────────┘
         │                           │                           │
    EggAI Channels             DSPy Framework            Kafka Protocol
```

## Key Components

### `react_signature.py`
- DSPy signature for ReAct reasoning
- Defines input/output structure

### `tool_integration.py`  
- Converts external tools to DSPy format
- Handles async/sync compatibility
- Tool testing and validation

### `react_agent.py`
- Main ReAct agent implementation
- Tool discovery and integration
- Conversation history management

### `console_interface.py`
- Interactive console with thinking indicators
- Real-time response handling
- User-friendly interface

## Running the Demo

### Prerequisites
```bash
# Set OpenAI API key
export OPENAI_API_KEY="your-key-here"

# Start Kafka (from main mcp directory)
cd ../..
make docker-up
```

### Run ReAct Demo
```bash
cd poc/demo/
python run_react_demo.py
```

### Example Interactions

**Math Problems:**
```
You: Add 15 and 27
🤖 Agent: I'll help you add those numbers. Let me use the calculator tool.

[ReAct thinks: I need to add 15 and 27, I should use the add tool]
[ReAct acts: Using add tool with parameters a=15, b=27]
[ReAct observes: Tool returned 42]

The result of adding 15 and 27 is 42.
```

**Greetings:**
```
You: Say hello to Alice
🤖 Agent: I'll generate a friendly greeting for Alice.

[ReAct thinks: User wants me to greet Alice, I should use the greet tool]
[ReAct acts: Using greet tool with parameter name="Alice"] 
[ReAct observes: Tool returned "Hello, Alice!"]

Hello, Alice! 👋
```

**Tool Discovery:**
```
You: What tools do you have?
🤖 Agent: I have access to these external tools:
• add: Add two numbers together
• greet: Generate a greeting message for someone

These tools are provided through external adapters and I can use them to help you with various tasks!
```

## ReAct Process

The agent follows DSPy's ReAct pattern:

1. **Think**: Understand the user's request
2. **Act**: Choose and execute appropriate tools  
3. **Observe**: Process tool results
4. **Repeat**: Continue until task is complete
5. **Respond**: Generate final answer

This creates intelligent, step-by-step problem solving with full reasoning transparency.

## Benefits vs Simple Demo

✅ **Intelligent Reasoning**: Real LLM-powered decision making
✅ **Natural Language**: Understands intent, not just keywords  
✅ **Multi-step Tasks**: Can chain multiple tools together
✅ **Error Recovery**: Handles tool failures gracefully
✅ **Extensible**: Easy to add new reasoning patterns
✅ **Transparent**: Shows thinking process (in logs)