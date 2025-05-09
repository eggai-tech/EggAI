# Agent Optimization in EggAI Multi-Agent System

This document explains our approach to optimizing the agent prompts in the EggAI multi-agent system using DSPy and COPRO.

## COPRO and ReAct Optimization

The optimization of ReAct-based agents presents unique challenges compared to simpler DSPy modules. This document captures our approach and lessons learned.

### Challenges with ReAct Optimization

1. **Standard DSPy Optimization Limitations**:
   - Most DSPy optimizers like COPRO are designed for simple input→output modules like `dspy.Predict`
   - ReAct's multi-step reasoning and tool usage creates complexity for traditional optimizers
   - Current DSPy documentation lacks clear guidance on optimizing ReAct agents (see [DSPy Issue #703](https://github.com/stanfordnlp/dspy/issues/703))

2. **Our Solution Overview**:
   - Use COPRO to optimize the agent's signature (instructions)
   - Preserve the ReAct framework and tool-using capabilities
   - Apply custom loading mechanisms to incorporate optimized instructions

## Implementation Details

### 1. Mock Tools for Optimization

During optimization, we use mock tool implementations that return fixed sample data:

```python
# Mock tools for optimization (these won't actually be called during optimization)
def mock_get_billing_info(policy_number: str):
    """Mock implementation of get_billing_info for optimization."""
    return '{"policy_number": "A12345", "billing_cycle": "Monthly", "amount_due": 120.0, "due_date": "2025-02-01", "status": "Paid"}'
```

This allows COPRO to optimize around the ReAct framework without making actual external calls.

### 2. Synthetic Dataset Creation

We generate synthetic examples that represent realistic interactions:

```python
# In billing_dataset.py, claims_dataset.py, policies_dataset.py
def create_billing_dataset():
    """Creates a synthetic dataset of billing inquiries and expected responses."""
    examples = [
        {
            "chat_history": "User: What's my current balance?\nBillingAgent: I'd be happy to help check your balance. Could you please provide your policy number?\nUser: My policy number is A12345.",
            "final_response": "Your current amount due is $120.00 with a due date of 2025-02-01. Your status is 'Paid'."
        },
        # More examples...
    ]
    return examples
```

### 3. Saving Optimization Results

We save only the optimized signature, not the full program:

```python
# Save optimized signature to JSON
optimized_signature = optimized_program.signature
optimized_signature.save(str(json_path))
```

### 4. Loading Optimized Signatures into TracedReAct

We added a custom method to the TracedReAct class to load these signatures:

```python
@staticmethod
def load_signature(path):
    """
    Load a signature from a JSON file saved by an optimizer.
    
    Args:
        path: Path to the JSON file containing the signature
        
    Returns:
        The loaded signature class that can be used to create a new TracedReAct
    """
    try:
        # First try to load it as a signature
        signature = dspy.Signature.load(path)
        return signature
    except Exception as e:
        # If that fails, try to load as a Predict and extract the signature
        try:
            predict = dspy.Predict.load(path)
            if hasattr(predict, 'signature'):
                return predict.signature
        except Exception as e2:
            raise ValueError(f"Could not load signature from {path}")
```

### 5. Robust Error Handling with Fallbacks

We implemented a CustomCOPRO class to handle incomplete model outputs:

```python
class CustomCOPRO(COPRO):
    def propose_configuration(self, prompt_template, field_configs=None):
        """Override to handle incomplete outputs from model"""
        try:
            result = super().propose_configuration(prompt_template, field_configs)
            return result
        except Exception as e:
            logger.warning(f"Standard COPRO proposal failed: {e}")
            # Fallback to a simpler format if the model output is incomplete
            if "proposed_prefix_for_output_field" in str(e):
                # Create a minimal valid configuration
                return {
                    "proposed_instruction": prompt_template["instruction"],
                    "proposed_prefix_for_output_field": "I'll help with your billing inquiry."
                }
            else:
                raise e
```

### 6. Multiple Save Formats

We implemented a multi-stage approach to saving optimized signatures:

```python
try:
    # Try saving the full signature
    optimized_signature = optimized_program.signature
    optimized_signature.save(str(json_path))
    logger.info(f"Saved optimized signature to {json_path}")
except Exception as save_error:
    logger.warning(f"Full signature save failed: {save_error}")
    
    # Fallback to manual JSON save of critical parts
    try:
        import json
        
        # Extract essential signature components
        if hasattr(optimized_program, 'signature'):
            signature_data = {
                "instructions": optimized_program.signature.instructions,
                "fields": []
            }
            
            # Try to extract field information
            if hasattr(optimized_program.signature, 'fields'):
                for field in optimized_program.signature.fields:
                    if hasattr(field, 'name') and hasattr(field, 'prefix'):
                        signature_data["fields"].append({
                            "name": field.name,
                            "prefix": field.prefix
                        })
            
            # Save simplified signature
            with open(str(json_path), 'w') as f:
                json.dump(signature_data, f, indent=2)
    except Exception as simplified_save_error:
        logger.error(f"Simplified signature save also failed: {simplified_save_error}")
```

### 7. Multi-Stage Loading Strategy

At runtime, agents attempt to load and use optimized instructions with multiple fallbacks:

```python
try:
    # Try standard loading method first
    json_path = Path(__file__).resolve().parent / "optimized_billing.json"
    if os.path.exists(json_path):
        try:
            # Method 1: Standard DSPy signature loading
            billing_signature = TracedReAct.load_signature(str(json_path))
            billing_optimized = TracedReAct(
                billing_signature,
                tools=[get_billing_info, update_billing_info],
                name="billing_react_optimized",
                tracer=tracer,
                max_iters=5,
            )
        except Exception as load_error:
            # Method 2: Custom JSON format loading
            try:
                import json
                with open(str(json_path), 'r') as f:
                    signature_data = json.load(f)
                
                # Create a new signature using the saved data
                from dataclasses import dataclass
                
                @dataclass
                class BillingCustomSignature(BillingSignature):
                    pass
                
                # Set custom instructions if available
                if "instructions" in signature_data:
                    BillingCustomSignature.__doc__ = signature_data["instructions"]
                
                # Create a new TracedReAct with the custom signature
                billing_optimized = TracedReAct(
                    BillingCustomSignature,
                    tools=[get_billing_info, update_billing_info],
                    name="billing_react_optimized",
                    tracer=tracer,
                    max_iters=5,
                )
            except Exception:
                # Method 3: Last resort - fallback to unoptimized version
                billing_optimized = dspy.Predict(BillingSignature)
except Exception:
    # Final fallback to unoptimized version
    billing_optimized = dspy.Predict(BillingSignature)
```

## Performance Optimizations

We've implemented several optimizations to improve the performance and reliability of the optimization process:

1. **Reduced COPRO Parameters**:
   - Reduced breadth from 3 to 2
   - Reduced depth from 2 to 1
   - This improves speed while still providing good optimization results

2. **Smaller Dataset Sizes**:
   - Limited the training set to a maximum of 8 examples
   - Reduced test set size to 10% of the total dataset
   - Significantly reduces optimization time without major quality loss

3. **Reduced Thread Count**:
   - Set evaluator thread count to 2
   - Prevents excessive model API calls and resource usage

4. **Model Selection**:
   - Switched from Gemma3 to Mixtral for improved structured output support
   - Configure models in .env file or through environment variables

## Running the Optimizers

To run all optimizers:

```bash
make compile-all
```

To run individual agent optimizers:

```bash
make compile-billing-optimizer
make compile-claims-optimizer
make compile-policies-optimizer
```

Optimizer commands will:
1. Ask for confirmation before running (except for `compile-all` which runs with automatic "yes" responses)
2. Create a synthetic dataset (or load existing ones)
3. Evaluate a baseline score
4. Run COPRO optimization with the reduced parameters
5. Save the optimized signature with fallback mechanisms
6. Log metrics to MLflow for comparison and tracking

## Common Errors and Solutions

1. **Ensuring Consistent Evaluation**:
   - We explicitly disable DSPy caching during optimization with `dspy_set_language_model(settings, overwrite_cache_enabled=False)`
   - This ensures each evaluation is independent and not influenced by cached results

2. **"proposed_prefix_for_output_field" Error**:
   - Symptom: COPRO crashes with an error about missing fields
   - Solution: Our CustomCOPRO class handles this by providing a minimal valid configuration

2. **Save/Load Errors**:
   - Symptom: Optimized signature fails to save in standard DSPy format
   - Solution: The multi-stage save/load system with fallbacks ensures optimization results are preserved

3. **Model Output Format Issues**:
   - Symptom: Models like Mixtral may return incomplete structured outputs
   - Solution: Robust error handling and fallbacks in the CustomCOPRO class

4. **"No outputs detected" Error**:
   - Symptom: DSPy can't parse model output for ReAct format
   - Solution: Reduced length and complexity of examples helps, and fallback to unoptimized version if needed

## Future Improvements

1. **Better DSPy Integration**: As DSPy develops better support for ReAct optimization, we can adapt our approach
2. **Larger Datasets**: Creating more diverse synthetic examples would improve optimization results
3. **Custom Metrics**: Our precision metrics could be expanded to better capture agent performance
4. **Parallel Optimization**: Using cloud models or multiple local models could speed up optimization
5. **Adaptive Model Selection**: Automatically choose the best model for optimization based on performance characteristics

## Conclusion

Our approach balances the current limitations in DSPy's support for ReAct optimization while still achieving improved agent performance. By optimizing the signature instructions while preserving the ReAct framework, we get the benefits of COPRO's prompt optimization without losing the tool-using capabilities of our agents.