# ReAct Framework with DSPy

## Overview

ReAct (Reasoning and Acting) enables agents to solve complex tasks by iteratively reasoning about the problem and taking actions via tools.

## Implementation

### Setup
```python
import dspy
from libraries.observability.tracing import TracedReAct, create_tracer

# Configure language model
dspy.configure(lm=dspy.LM(
    model="gemma-3-12b-it-qat",
    api_base="http://localhost:1234/v1"
))

# Create ReAct agent
tracer = create_tracer("billing_agent")
agent = TracedReAct(
    signature=BillingSignature,
    tools=[get_billing_info, update_payment],
    tracer=tracer,
    max_iters=5
)
```

### Signatures
```python
class BillingSignature(dspy.Signature):
    """Answer billing questions using available tools."""
    query: str = dspy.InputField()
    response: str = dspy.OutputField()
```

### Tools
```python
def get_billing_info(policy_number: str) -> dict:
    """Retrieve billing information for a policy."""
    return {"premium": 1200, "due_date": "2024-02-01"}
```

## ReAct Process

1. **Thought**: Analyze the user's request
2. **Action**: Select and execute appropriate tool
3. **Observation**: Process tool output
4. **Iterate**: Continue until task complete

### Example Flow
```
Query: "What's my premium for policy B67890?"

Thought: Need to retrieve billing info for policy B67890
Action: get_billing_info("B67890")
Observation: {"premium": 1200, "due_date": "2024-02-01"}
Thought: I have the information needed
Response: Your premium for policy B67890 is $1,200
```

## Agent Examples

### Billing Agent
```python
tools = [get_billing_info, update_payment, check_history]
react = TracedReAct(signature=BillingSignature, tools=tools)
```

### Claims Agent
```python
tools = [file_claim, check_status, update_claim]
react = TracedReAct(signature=ClaimsSignature, tools=tools)
```

### Policies Agent (with RAG)
```python
tools = [search_documents, get_policy_details]
react = TracedReAct(signature=PoliciesSignature, tools=tools)
```

## Streaming Responses
```python
async for chunk in dspy.streamify(agent(query=query)):
    if chunk.type == "response":
        yield chunk.content
```

## Optimization

### Automatic Prompt Optimization
```python
from dspy.teleprompt import BootstrapFewShot

optimizer = BootstrapFewShot(metric=accuracy_metric)
optimized_agent = optimizer.compile(agent, trainset=examples)
```

### When to Use Each Approach

| Method | Use Case |
|--------|----------|
| Manual prompts | Quick prototyping |
| Few-shot | Limited training data |
| Bootstrap | Production optimization |

## Error Handling
```python
try:
    result = agent(query=user_query)
except ToolExecutionError:
    result = fallback_response()
except MaxIterationsError:
    result = "Need more information"
```

## Best Practices

1. **Tools**: Keep focused, single-purpose
2. **Signatures**: Clear task descriptions
3. **Iterations**: Balance completeness vs latency
4. **Monitoring**: Track reasoning traces

---

**Previous:** [Building Agents Guide](building-agents-eggai.md) | **Next:** [Document Ingestion with Temporal](ingestion-pipeline.md)