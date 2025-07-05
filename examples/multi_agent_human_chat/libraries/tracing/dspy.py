import asyncio
import functools
from typing import Callable, List, Optional

import dspy
from opentelemetry import trace

from libraries.dspy_set_language_model import TrackingLM
from libraries.logger import get_console_logger
from libraries.tracing.otel import safe_set_attribute
from libraries.tracing.schemas import GenAIAttributes

logger = get_console_logger("tracing.dspy")


def add_gen_ai_attributes_to_span(
    span: trace.Span, model_name: str = "claude", **kwargs
) -> None:
    attr_dict = {"model_name": model_name}

    attr_dict.update({k: v for k, v in kwargs.items() if v is not None})

    gen_ai_attrs = GenAIAttributes(**attr_dict)

    for key, value in gen_ai_attrs.to_span_attributes().items():
        safe_set_attribute(span, key, value)


class TracedChainOfThought(dspy.ChainOfThought):

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

    def decorator(fn):
        tracer = trace.get_tracer(f"dspy.{name or fn.__name__}")

        def set_gen_ai_attributes(span: trace.Span, **kwargs):
            # Extract relevant attributes from kwargs
            extracted_attrs = {}

            # Service tier is commonly passed in kwargs
            if "service_tier" in kwargs:
                extracted_attrs["service_tier"] = kwargs.get("service_tier")

            # Use the common helper function for attribute setting
            add_gen_ai_attributes_to_span(span, **extracted_attrs)

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

    def __init__(
        self,
        signature,
        tools: Optional[List[Callable]] = None,
        max_iters: Optional[int] = 5,
        name: Optional[str] = None,
        tracer: Optional[trace.Tracer] = None,
    ):
        super().__init__(signature, tools=tools, max_iters=max_iters)
        self.trace_name = name or self.__class__.__name__.lower()
        self.tracer = tracer or trace.get_tracer(f"dspy.{self.trace_name}")

    def __call__(self, *args, **kwargs):
        with self.tracer.start_as_current_span(f"{self.trace_name}_call") as span:
            span.set_attribute("dspy.call_args", str(args))
            span.set_attribute("dspy.call_kwargs", str(kwargs))
            res = super().__call__(*args, **kwargs)
            usage = res.get_lm_usage()
            if usage:
                model_name = list(usage.keys())[0] if usage else "unknown_model"
                add_gen_ai_attributes_to_span(span, model_name=model_name)
                for k, v in usage[model_name].items():
                    if v is not None and not isinstance(v, dict):
                        span.set_attribute(k, v)

            return res

    def forward(self, **kwargs):
        with self.tracer.start_as_current_span(f"{self.trace_name}_forward") as span:
            add_gen_ai_attributes_to_span(span)
            span.set_attribute("dspy.forward_args", str(kwargs))
            res = super().forward(**kwargs)
            lm: TrackingLM = dspy.settings.get("lm")
            prompt = lm.history[-1].get("prompt", "")
            if prompt:
                span.set_attribute("dspy.prompt", prompt)
            messages = lm.history[-1].get("messages", [])
            if messages:
                concatenated_contents = "\n".join(
                    msg.get("content", "") for msg in messages if isinstance(msg, dict)
                )
                span.set_attribute("dspy.messages", concatenated_contents)
            return res
