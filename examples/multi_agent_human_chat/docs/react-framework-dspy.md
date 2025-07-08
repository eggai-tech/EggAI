# ReAct Framework with DSPy

This document explains how the multi-agent system implements the ReAct (Reasoning and Acting) framework using DSPy for intelligent task completion.

## Overview

ReAct is a paradigm that enables agents to reason about tasks and take actions iteratively. In our system, specialized agents (Billing, Claims, Policies, Escalation) use DSPy's TracedReAct implementation to:

1. **Reason** about the user's request
2. **Act** by calling appropriate tools
3. **Observe** the results
4. **Iterate** until the task is complete

## DSPy Implementation

### Core Components

The system uses a custom `TracedReAct` class (extending DSPy's `ReAct`) which provides:
- Automatic reasoning traces via OpenTelemetry
- Tool execution management
- Context maintenance across iterations
- Streaming response generation
- Distributed tracing integration

### Agent Configuration

Each ReAct agent is configured with:

```python
import dspy
from libraries.observability.tracing import TracedReAct, create_tracer

# Initialize DSPy with language model
dspy.configure(
    lm=dspy.LM(
        model=config.language_model,
        api_base=config.language_model_api_base,
        temperature=0.7
    )
)

# Create tracer for observability
tracer = create_tracer("billing_agent")

# Create ReAct agent with tools and tracing
agent = TracedReAct(
    signature=BillingSignature,
    tools=[get_billing_info, update_payment_method],
    name="billing_react",
    tracer=tracer,
    max_iters=5
)
```

### Signature Definition

DSPy signatures define the input/output contract:

```python
class BillingSignature(dspy.Signature):
    """Answer billing questions accurately using available tools."""
    
    user_query: str = dspy.InputField(
        desc="The user's billing-related question"
    )
    response: str = dspy.OutputField(
        desc="Helpful response addressing the billing inquiry"
    )
```

## Tool Integration

### Tool Definition

Tools are Python functions decorated with metadata:

```python
def get_billing_info(policy_number: str) -> dict:
    """
    Retrieve billing information for a policy.
    
    Args:
        policy_number: The policy number to look up
        
    Returns:
        Billing details including premium, due date, and payment status
    """
    # Implementation details
    return billing_data
```

### Tool Registration

Tools are registered with the ReAct agent:

```python
tools = [
    get_billing_info,
    update_payment_method,
    check_payment_history,
    calculate_premium
]

agent = TracedReAct(
    signature=BillingSignature,
    tools=tools
)
```

## Reasoning Process

### Step-by-Step Execution

1. **Initial Reasoning**
   ```
   Thought: User is asking about their premium for policy B67890.
   I need to retrieve the billing information for this policy.
   ```

2. **Action Selection**
   ```
   Action: get_billing_info
   Action Input: {"policy_number": "B67890"}
   ```

3. **Observation**
   ```
   Observation: {
     "policy_number": "B67890",
     "premium": 1200,
     "due_date": "2024-02-01",
     "status": "current"
   }
   ```

4. **Follow-up Reasoning**
   ```
   Thought: I have the billing information. The premium is $1200
   and it's due on February 1st. I should provide a complete answer.
   ```

5. **Final Response**
   ```
   Response: Your premium for policy B67890 is $1,200, 
   due on February 1st, 2024. Your account is current.
   ```

### Multi-Step Reasoning

For complex queries, the agent performs multiple iterations:

```python
# Query: "Update my payment method and set up autopay"

# Iteration 1: Update payment method
Thought: Need to update payment method first
Action: update_payment_method
Result: Payment method updated

# Iteration 2: Enable autopay
Thought: Now enable automatic payments
Action: enable_autopay
Result: Autopay activated

# Final response combining both actions
Response: I've updated your payment method and enabled autopay.
```

## Agent Examples

### Billing Agent

```python
from libraries.observability.tracing import TracedReAct, create_tracer

class BillingAgent:
    def __init__(self):
        self.tracer = create_tracer("billing_agent")
        self.react = TracedReAct(
            signature=BillingSignature,
            tools=[
                get_billing_info,
                update_payment_method,
                check_payment_history,
                calculate_premium,
                enable_autopay
            ],
            name="billing_react",
            tracer=self.tracer,
            max_iters=5
        )
    
    async def handle_inquiry(self, query: str) -> str:
        # Execute ReAct reasoning
        result = self.react(query=query)
        return result.response
```

### Claims Agent

```python
class ClaimsAgent:
    def __init__(self):
        self.tracer = create_tracer("claims_agent")
        self.react = TracedReAct(
            signature=ClaimsSignature,
            tools=[
                file_new_claim,
                check_claim_status,
                update_claim_info,
                get_claim_documents,
                calculate_deductible
            ],
            name="claims_react",
            tracer=self.tracer,
            max_iters=7  # More iterations for complex claims
        )
```

### Policies Agent with RAG

The Policies agent combines ReAct with retrieval:

```python
class PoliciesAgent:
    def __init__(self):
        self.tracer = create_tracer("policies_agent")
        self.react = TracedReAct(
            signature=PoliciesSignature,
            tools=[
                search_policy_documentation,  # RAG tool
                get_personal_policy_details,
                compare_coverage_options,
                calculate_coverage_limits
            ],
            name="policies_react",
            tracer=self.tracer
        )
    
    def search_policy_documentation(self, query: str) -> str:
        """Search Vespa for relevant policy documentation."""
        results = self.vespa_client.search(query)
        return self.format_search_results(results)
```

## Streaming Responses

DSPy enables streaming for better user experience:

```python
async def stream_response(agent, query):
    # Stream reasoning process
    async for chunk in dspy.streamify(agent(query=query)):
        if chunk.type == "thought":
            # Optionally show reasoning to user
            pass
        elif chunk.type == "response":
            # Stream final response
            yield chunk.content
```

## Optimization

### Prompt Optimization

DSPy supports automatic prompt optimization:

```python
from dspy.teleprompt import BootstrapFewShot

# Create optimizer
optimizer = BootstrapFewShot(metric=accuracy_metric)

# Optimize prompts based on examples
optimized_agent = optimizer.compile(
    agent,
    trainset=training_examples
)
```

### Performance Tuning

- **Max Iterations**: Balance between completeness and latency
- **Temperature**: Control creativity vs determinism
- **Tool Selection**: Provide focused tool sets per agent
- **Context Window**: Manage conversation history efficiently

## Error Handling

### Graceful Failures

```python
try:
    result = agent(query=user_query)
except ToolExecutionError as e:
    # Handle tool failures
    result = agent.fallback_response(e)
except MaxIterationsError:
    # Handle reasoning loops
    result = "I need more information to complete this request."
```

### Tool Validation

```python
def validate_tool_input(tool, args):
    """Validate tool inputs before execution."""
    schema = tool.input_schema
    return schema.validate(args)
```

## Integration with Multi-Agent System

### Message Flow

1. User query arrives via Kafka
2. Agent creates ReAct instance
3. ReAct performs reasoning and actions
4. Results stream back through Kafka
5. Frontend displays progressive updates

### Context Sharing

Agents can share context through tools:

```python
def get_shared_context(conversation_id: str) -> dict:
    """Retrieve context from other agents."""
    return shared_context_store.get(conversation_id)
```

## Best Practices

### 1. Tool Design
- Keep tools focused and single-purpose
- Provide clear descriptions for reasoning
- Return structured data for easy parsing
- Handle errors gracefully

### 2. Prompt Engineering
- Use DSPy's automatic optimization
- Provide clear task descriptions
- Include examples in signatures
- Test with diverse queries

### 3. Performance
- Limit max iterations appropriately
- Cache tool results when possible
- Stream responses for better UX
- Monitor reasoning traces

### 4. Debugging
- Enable trace logging
- Review reasoning steps
- Validate tool inputs/outputs
- Track iteration counts

## Monitoring

Track ReAct performance with:
- Average iterations per query
- Tool usage frequency
- Reasoning quality metrics
- Response accuracy
- Latency per iteration

---

**Previous:** [Building Agents Guide](building-agents-eggai.md) | **Next:** [Document Ingestion with Temporal](ingestion-pipeline.md)