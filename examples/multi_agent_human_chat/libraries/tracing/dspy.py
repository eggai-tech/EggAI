"""
DSPy-specific tracing utilities.

This module provides tracing utilities for DSPy modules, including ChainOfThought,
ReAct, and other DSPy components.
"""

import asyncio
import functools
from typing import Callable, List, Optional

import dspy
from opentelemetry import trace

from libraries.logger import get_console_logger
from libraries.tracing.otel import safe_set_attribute
from libraries.tracing.schemas import GenAIAttributes

logger = get_console_logger("tracing.dspy")


def add_gen_ai_attributes_to_span(
    span: trace.Span, model_name: str = "claude", **kwargs
) -> None:
    """
    Add standard gen_ai attributes to a span to prevent errors with None values.

    Args:
        span: OpenTelemetry span to add attributes to
        model_name: Name of the model being used
        **kwargs: Additional attributes to set on the span
    """
    # Create attributes with defaults to ensure no None values
    attr_dict = {"model_name": model_name}

    # Add any additional attributes provided
    attr_dict.update({k: v for k, v in kwargs.items() if v is not None})

    # Create the model with all attributes
    gen_ai_attrs = GenAIAttributes(**attr_dict)

    # Set all attributes safely
    for key, value in gen_ai_attrs.to_span_attributes().items():
        safe_set_attribute(span, key, value)


class TracedChainOfThought(dspy.ChainOfThought):
    """
    Traced version of DSPy's ChainOfThought module.

    Args:
        signature: DSPy signature for the module
        name: Name to use in trace spans
        tracer: Optional specific tracer to use (defaults to module name)
    """

    def __init__(
        self,
        signature,
        name: Optional[str] = None,
        tracer: Optional[trace.Tracer] = None,
    ):
        super().__init__(signature)
        self.trace_name = name or self.__class__.__name__.lower()
        self.tracer = tracer or trace.get_tracer(f"dspy.{self.trace_name}")

    def __call__(self, *args, **kwargs):
        with self.tracer.start_as_current_span(f"{self.trace_name}_call") as span:
            add_gen_ai_attributes_to_span(span)
            span.set_attribute("dspy.call_args", str(args))
            span.set_attribute("dspy.call_kwargs", str(kwargs))
            return super().__call__(*args, **kwargs)

    def forward(self, **kwargs):
        with self.tracer.start_as_current_span(f"{self.trace_name}_forward") as span:
            add_gen_ai_attributes_to_span(span)
            span.set_attribute("dspy.forward_args", str(kwargs))
            return super().forward(**kwargs)

    def predict(self, **kwargs):
        with self.tracer.start_as_current_span(f"{self.trace_name}_predict") as span:
            add_gen_ai_attributes_to_span(span)
            span.set_attribute("dspy.predict_args", str(kwargs))
            return super().predict(**kwargs)


def traced_dspy_function(name=None, span_namer=None):
    """
    Decorator to add tracing to DSPy functions.

    This creates a span for the function and logs inputs/outputs.
    Handles both synchronous and asynchronous functions.

    Args:
        name: Optional name for the span (defaults to function name)
        span_namer: Optional function to derive span name from arguments

    Returns:
        Decorated function with tracing
    """

    def decorator(fn):
        tracer = trace.get_tracer(f"dspy.{name or fn.__name__}")

        def set_gen_ai_attributes(span: trace.Span, **kwargs):
            """Set standard gen_ai attributes on the span to prevent errors."""
            # Extract relevant attributes from kwargs
            extracted_attrs = {}

            # Service tier is commonly passed in kwargs
            if "service_tier" in kwargs:
                extracted_attrs["service_tier"] = kwargs.get("service_tier")

            # Use the common helper function for attribute setting
            add_gen_ai_attributes_to_span(
                span, **extracted_attrs
            )

        @functools.wraps(fn)
        def sync_wrapper(*args, **kwargs):
            span_name = name or fn.__name__
            if span_namer:
                try:
                    span_name = span_namer(*args, **kwargs) or span_name
                except Exception as e:
                    logger.warning(f"Error in span_namer: {e}")

            with tracer.start_as_current_span(span_name) as span:
                try:
                    # Set default gen_ai attributes
                    set_gen_ai_attributes(span, **kwargs)

                    # Trace a subset of kwargs for context
                    if "chat_history" in kwargs:
                        chat_excerpt = (
                            kwargs["chat_history"][:200] + "..."
                            if len(kwargs["chat_history"]) > 200
                            else kwargs["chat_history"]
                        )
                        safe_set_attribute(span, "dspy.chat_history", chat_excerpt)

                    result = fn(*args, **kwargs)
                    return result
                except Exception as e:
                    span.record_exception(e)
                    logger.error(f"Error in {fn.__name__}: {e}")
                    raise

        @functools.wraps(fn)
        async def async_wrapper(*args, **kwargs):
            span_name = name or fn.__name__
            if span_namer:
                try:
                    span_name = span_namer(*args, **kwargs) or span_name
                except Exception as e:
                    logger.warning(f"Error in span_namer: {e}")

            with tracer.start_as_current_span(span_name) as span:
                try:
                    # Set default gen_ai attributes
                    set_gen_ai_attributes(span, **kwargs)

                    # Trace a subset of kwargs for context
                    if "chat_history" in kwargs:
                        chat_excerpt = (
                            kwargs["chat_history"][:200] + "..."
                            if len(kwargs["chat_history"]) > 200
                            else kwargs["chat_history"]
                        )
                        safe_set_attribute(span, "dspy.chat_history", chat_excerpt)

                    result = await fn(*args, **kwargs)
                    return result
                except Exception as e:
                    span.record_exception(e)
                    logger.error(f"Error in {fn.__name__}: {e}")
                    raise

        # Choose which wrapper to return based on whether fn is a coroutine function
        if asyncio.iscoroutinefunction(fn):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


class TracedReAct(dspy.ReAct):
    """
    Traced version of DSPy's ReAct module with support for optimized loading.

    Args:
        signature: DSPy signature for the module
        tools: List of tools to use
        max_iters: Maximum iterations for ReAct
        name: Name to use in trace spans
        tracer: Optional specific tracer to use (defaults to module name)
    """

    def __init__(
        self,
        signature,
        tools: Optional[List[Callable]] = None,
        max_iters: Optional[int] = 5,
        name: Optional[str] = None,
        tracer: Optional[trace.Tracer] = None,
        model_name: str = "claude",
    ):
        super().__init__(signature, tools=tools, max_iters=max_iters)
        self.trace_name = name or self.__class__.__name__.lower()
        self.model_name = model_name
        self.tracer = tracer or trace.get_tracer(f"dspy.{self.trace_name}")

    def __call__(self, *args, **kwargs):
        with self.tracer.start_as_current_span(f"{self.trace_name}_call") as span:
            add_gen_ai_attributes_to_span(span, model_name=self.model_name)
            span.set_attribute("dspy.call_args", str(args))
            span.set_attribute("dspy.call_kwargs", str(kwargs))
            res = super().__call__(*args, **kwargs)
            logger.info("ReAct call completed, result: %s", res)
            logger.info("lm usage: %s", res._lm_usage)
            return res


    def forward(self, **kwargs):
        with self.tracer.start_as_current_span(f"{self.trace_name}_forward") as span:
            add_gen_ai_attributes_to_span(span, model_name=self.model_name)
            span.set_attribute("dspy.forward_args", str(kwargs))
            res = super().forward(**kwargs)
            logger.info("ReAct forward completed, result: %s", res)
            logger.info("lm usage: %s", res._lm_usage)
            return res

    @staticmethod
    def load_signature(path):
        """
        Load a signature from a JSON file saved by an optimizer.
        """
        logger.info(f"Loading signature from {path}")
        try:
            # First try to load it as a signature
            signature = dspy.Signature.load(path)
            return signature
        except Exception as e:
            # If that fails, try to load as a Predict and extract the signature
            logger.warning(f"Failed to load as signature directly: {e}")
            try:
                predict = dspy.Predict.load(path)
                if hasattr(predict, "signature"):
                    return predict.signature
            except Exception as e2:
                logger.error(f"Failed to load signature: {e2}")
                raise ValueError(f"Could not load signature from {path}")
