
from opentelemetry import trace
from prometheus_client import Counter, Gauge, Histogram, start_http_server

# Import pricing functionality
from .pricing import calculate_request_cost

# OpenTelemetry GenAI Semantic Convention Metrics
# https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-metrics/
# 
# This implementation follows the official OpenTelemetry semantic conventions for 
# Generative AI metrics, including:
# - gen_ai.client.token.usage (Counter)
# - gen_ai.client.operation.duration (Histogram) 
# - gen_ai.server.request.duration (Histogram)
# - gen_ai.server.time_to_first_token (Histogram)
#
# All metric names, attribute names, and values are compliant with the specification.

# Official OpenTelemetry GenAI Semantic Convention Metrics (Prometheus compatible naming)
gen_ai_client_token_usage = Counter(
    'gen_ai_client_token_usage',
    'Number of tokens used in GenAI requests',
    ['gen_ai_system', 'gen_ai_request_model', 'gen_ai_operation_name', 'gen_ai_token_type', 'gen_ai_agent_name']
)

gen_ai_client_operation_duration = Histogram(
    'gen_ai_client_operation_duration',
    'GenAI operation duration',
    ['gen_ai_system', 'gen_ai_request_model', 'gen_ai_operation_name', 'gen_ai_agent_name'],
    buckets=[0.01, 0.02, 0.04, 0.08, 0.16, 0.32, 0.64, 1.28, 2.56, 5.12, 10.24, 20.48, 40.96, 81.92]
)

# Add the official server-side metrics for completeness
gen_ai_server_request_duration = Histogram(
    'gen_ai_server_request_duration',
    'GenAI server request duration',
    ['gen_ai_system', 'gen_ai_request_model', 'gen_ai_operation_name', 'gen_ai_agent_name'],
    buckets=[0.01, 0.02, 0.04, 0.08, 0.16, 0.32, 0.64, 1.28, 2.56, 5.12, 10.24, 20.48, 40.96, 81.92]
)

gen_ai_server_time_to_first_token = Histogram(
    'gen_ai_server_time_to_first_token',
    'Time to generate first token for successful responses',
    ['gen_ai_system', 'gen_ai_request_model', 'gen_ai_operation_name', 'gen_ai_agent_name'],
    buckets=[0.001, 0.005, 0.01, 0.02, 0.04, 0.06, 0.08, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0]
)

# Custom cost metrics (not in standard but useful for observability)
gen_ai_client_cost_total = Counter(
    'gen_ai_client_cost_total',
    'Total cost in USD for GenAI requests',
    ['gen_ai_system', 'gen_ai_request_model', 'gen_ai_operation_name', 'cost_type', 'gen_ai_agent_name']
)

gen_ai_client_cost_current = Gauge(
    'gen_ai_client_cost_current',
    'Cost in USD for the current request',
    ['gen_ai_system', 'gen_ai_request_model', 'gen_ai_operation_name', 'cost_type', 'gen_ai_agent_name']
)

gen_ai_client_cost_per_token = Gauge(
    'gen_ai_client_cost_per_token',
    'Cost per token for different models',
    ['gen_ai_system', 'gen_ai_request_model', 'gen_ai_operation_name', 'gen_ai_token_type', 'gen_ai_agent_name']
)

# Add a global variable to store the application name
_application_name = "unknown"


def normalize_gen_ai_system(model_name: str) -> str:
    """
    Normalize model name to standard gen_ai.system values.
    Following OpenTelemetry semantic conventions exactly.
    https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-metrics/
    """
    model_lower = model_name.lower()
    
    # OpenAI models
    if any(x in model_lower for x in ["gpt", "openai", "o1-", "davinci", "curie", "babbage", "ada"]):
        return "openai"
    
    # Anthropic models
    elif any(x in model_lower for x in ["claude", "anthropic"]):
        return "anthropic"
    
    # AWS Bedrock
    elif "bedrock" in model_lower:
        return "aws.bedrock"
    
    # Azure AI Inference
    elif "azure" in model_lower and "inference" in model_lower:
        return "az.ai.inference"
    
    # Azure OpenAI
    elif "azure" in model_lower and "openai" in model_lower:
        return "az.ai.openai"
    
    # Cohere models
    elif "cohere" in model_lower:
        return "cohere"
    
    # DeepSeek models
    elif "deepseek" in model_lower:
        return "deepseek"
    
    # Google Gemini models
    elif any(x in model_lower for x in ["gemini", "generativelanguage"]):
        return "gcp.gemini"
    
    # Google Vertex AI
    elif any(x in model_lower for x in ["vertex", "aiplatform"]):
        return "gcp.vertex_ai"
    
    # Generic Google Gen AI
    elif any(x in model_lower for x in ["google", "palm", "bard"]):
        return "gcp.gen_ai"
    
    # Groq models
    elif "groq" in model_lower:
        return "groq"
    
    # IBM Watsonx AI
    elif any(x in model_lower for x in ["watsonx", "ibm"]):
        return "ibm.watsonx.ai"
    
    # Meta models
    elif any(x in model_lower for x in ["llama", "meta"]):
        return "meta"
    
    # Mistral AI models
    elif "mistral" in model_lower:
        return "mistral_ai"
    
    # Perplexity models
    elif "perplexity" in model_lower:
        return "perplexity"
    
    # xAI models
    elif "xai" in model_lower:
        return "xai"
    
    # Local models via LM Studio or similar
    elif any(x in model_lower for x in ["lm_studio", "lm-studio", "local", "localhost"]):
        return "_OTHER"
    
    else:
        return "_OTHER"


def normalize_operation_name(model_name: str, prompt: str = None, messages: list = None) -> str:
    """
    Determine the operation name based on the request type.
    Following OpenTelemetry semantic conventions exactly.
    https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-metrics/
    
    Valid values: chat, create_agent, embeddings, execute_tool, generate_content, invoke_agent, text_completion
    """
    # If messages are provided, it's likely a chat completion
    if messages:
        return "chat"
    
    # Check for embedding models
    model_lower = model_name.lower()
    if any(x in model_lower for x in ["embedding", "embed", "ada-002"]):
        return "embeddings"
    
    # Check for multimodal content generation (Gemini style)
    if any(x in model_lower for x in ["gemini", "generate-content"]):
        return "generate_content"
    
    # Default to chat for most modern models, text_completion for legacy
    if any(x in model_lower for x in ["gpt-4", "gpt-3.5", "claude", "gemini", "llama"]):
        return "chat"
    elif any(x in model_lower for x in ["davinci", "curie", "babbage", "ada"]):
        return "text_completion"
    
    # Default to chat for unknown models
    return "chat"


def export_semantic_metrics(lm, operation_duration: float = None, span=None):
    """
    Export metrics following OpenTelemetry GenAI semantic conventions.
    
    Args:
        lm: The TrackingLM instance
        operation_duration: Duration of the operation in seconds
        span: Optional current span to extract attributes from
    """
    global _application_name
    
    # Extract model info
    model_name = getattr(lm, 'model_name', 'unknown')
    gen_ai_system = normalize_gen_ai_system(model_name)
    gen_ai_operation_name = normalize_operation_name(model_name)
    
    # Use the global application name set via init_token_metrics()
    agent_name = _application_name
    
    # Calculate costs
    cost_info = None
    if lm.prompt_tokens > 0 or lm.completion_tokens > 0:
        try:
            cost_info = calculate_request_cost(model_name, lm.prompt_tokens, lm.completion_tokens)
        except Exception as e:
            print(f"Error calculating cost: {e}")
            cost_info = None
    
    # Export semantic convention metrics
    if lm.prompt_tokens > 0:
        gen_ai_client_token_usage.labels(
            **{
                'gen_ai_system': gen_ai_system,
                'gen_ai_request_model': model_name,
                'gen_ai_operation_name': gen_ai_operation_name,
                'gen_ai_token_type': "input",
                'gen_ai_agent_name': agent_name
            }
        ).inc(lm.prompt_tokens)
    
    if lm.completion_tokens > 0:
        gen_ai_client_token_usage.labels(
            **{
                'gen_ai_system': gen_ai_system,
                'gen_ai_request_model': model_name,
                'gen_ai_operation_name': gen_ai_operation_name,
                'gen_ai_token_type': "output",
                'gen_ai_agent_name': agent_name
            }
        ).inc(lm.completion_tokens)
    
    # Record operation duration if available
    if operation_duration is not None:
        gen_ai_client_operation_duration.labels(
            **{
                'gen_ai_system': gen_ai_system,
                'gen_ai_request_model': model_name,
                'gen_ai_operation_name': gen_ai_operation_name,
                'gen_ai_agent_name': agent_name
            }
        ).observe(operation_duration)
    
    # Export cost metrics
    if cost_info:
        # Total costs
        gen_ai_client_cost_total.labels(
            **{
                'gen_ai_system': gen_ai_system,
                'gen_ai_request_model': model_name,
                'gen_ai_operation_name': gen_ai_operation_name,
                'cost_type': "input",
                'gen_ai_agent_name': agent_name
            }
        ).inc(cost_info["prompt_cost"])
        
        gen_ai_client_cost_total.labels(
            **{
                'gen_ai_system': gen_ai_system,
                'gen_ai_request_model': model_name,
                'gen_ai_operation_name': gen_ai_operation_name,
                'cost_type': "output",
                'gen_ai_agent_name': agent_name
            }
        ).inc(cost_info["completion_cost"])
        
        gen_ai_client_cost_total.labels(
            **{
                'gen_ai_system': gen_ai_system,
                'gen_ai_request_model': model_name,
                'gen_ai_operation_name': gen_ai_operation_name,
                'cost_type': "total",
                'gen_ai_agent_name': agent_name
            }
        ).inc(cost_info["total_cost"])
        
        # Current request costs
        gen_ai_client_cost_current.labels(
            **{
                'gen_ai_system': gen_ai_system,
                'gen_ai_request_model': model_name,
                'gen_ai_operation_name': gen_ai_operation_name,
                'cost_type': "input",
                'gen_ai_agent_name': agent_name
            }
        ).set(cost_info["prompt_cost"])
        
        gen_ai_client_cost_current.labels(
            **{
                'gen_ai_system': gen_ai_system,
                'gen_ai_request_model': model_name,
                'gen_ai_operation_name': gen_ai_operation_name,
                'cost_type': "output",
                'gen_ai_agent_name': agent_name
            }
        ).set(cost_info["completion_cost"])
        
        gen_ai_client_cost_current.labels(
            **{
                'gen_ai_system': gen_ai_system,
                'gen_ai_request_model': model_name,
                'gen_ai_operation_name': gen_ai_operation_name,
                'cost_type': "total",
                'gen_ai_agent_name': agent_name
            }
        ).set(cost_info["total_cost"])
        
        # Cost per token metrics
        gen_ai_client_cost_per_token.labels(
            **{
                'gen_ai_system': gen_ai_system,
                'gen_ai_request_model': model_name,
                'gen_ai_operation_name': gen_ai_operation_name,
                'gen_ai_token_type': "input",
                'gen_ai_agent_name': agent_name
            }
        ).set(cost_info["prompt_price_per_1k"] / 1000.0)
        
        gen_ai_client_cost_per_token.labels(
            **{
                'gen_ai_system': gen_ai_system,
                'gen_ai_request_model': model_name,
                'gen_ai_operation_name': gen_ai_operation_name,
                'gen_ai_token_type': "output",
                'gen_ai_agent_name': agent_name
            }
        ).set(cost_info["completion_price_per_1k"] / 1000.0)


def export_token_metrics(lm, span=None):
    """
    Export semantic convention metrics.
    
    Args:
        lm: The TrackingLM instance
        span: Optional current span to extract attributes from
    """
    # Export semantic convention metrics
    export_semantic_metrics(lm, span=span)


def patch_tracking_lm():
    """Patch TrackingLM to automatically export metrics after each forward call."""
    from libraries.dspy_set_language_model import TrackingLM
    
    original_forward = TrackingLM.forward
    
    def patched_forward(self, prompt=None, messages=None, **kwargs):
        import time
        start_time = time.time()
        
        result = original_forward(self, prompt, messages, **kwargs)
        
        # Calculate operation duration
        operation_duration = time.time() - start_time
        
        # Export metrics after each forward call
        try:
            current_span = trace.get_current_span()
            export_token_metrics(self, current_span)
            # Also export semantic metrics with duration
            export_semantic_metrics(self, operation_duration, current_span)
        except Exception as e:
            print(f"Error exporting token metrics: {e}")
        
        return result
    
    TrackingLM.forward = patched_forward
    print("✓ Patched TrackingLM to export OpenTelemetry semantic convention metrics")


def start_metrics_server(port: int = 9091):
    """Start Prometheus metrics server."""
    start_http_server(port)
    print(f"✓ Prometheus metrics server started on port {port}")


def init_token_metrics(port: int = 9091, application_name: str = "unknown"):
    """
    Initialize the complete token metrics system.
    
    This function:
    1. Patches TrackingLM to automatically export metrics
    2. Starts the Prometheus metrics server
    3. Enables OpenTelemetry semantic convention metrics
    
    Args:
        port: Port for the Prometheus metrics server (default: 9091)
        application_name: Name of the application for metrics labeling (default: "unknown")
    """
    global _application_name
    _application_name = application_name
    
    print("Initializing GenAI token metrics system...")
    print(f"Application name: {application_name}")
    
    # Patch TrackingLM to automatically export metrics after each forward call
    patch_tracking_lm()
    
    # Start the Prometheus metrics server
    start_metrics_server(port)
    
    print(f"✅ Token metrics system initialized on port {port}")
    print("✅ OpenTelemetry semantic convention metrics enabled")


# Auto-initialize when imported (with default settings)
# This ensures metrics are available even if init_token_metrics() isn't called explicitly
try:
    # Only patch TrackingLM, don't start server automatically
    patch_tracking_lm()
    print("✓ Auto-initialized TrackingLM patching for metrics export")
except Exception as e:
    print(f"Warning: Could not auto-initialize metrics patching: {e}")


if __name__ == "__main__":
    # Example usage - full initialization with server
    init_token_metrics()
    print("OpenTelemetry GenAI semantic convention metrics exporter is running...")
    
    # Keep the server running
    import time
    while True:
        time.sleep(60)