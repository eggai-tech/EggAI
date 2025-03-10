"""
DSPy-specific tracing utilities.

This module provides tracing utilities for DSPy modules, including ChainOfThought,
ReAct, and other DSPy components.
"""

from typing import Optional, List, Callable

import dspy
from opentelemetry import trace

from libraries.logger import get_console_logger

logger = get_console_logger("tracing.dspy")

class TracedChainOfThought(dspy.ChainOfThought):
    """
    Traced version of DSPy's ChainOfThought module.
    
    Args:
        signature: DSPy signature for the module
        name: Name to use in trace spans
        tracer: Optional specific tracer to use (defaults to module name)
    """
    
    def __init__(self, signature, name: Optional[str] = None, tracer: Optional[trace.Tracer] = None):
        super().__init__(signature)
        self.trace_name = name or self.__class__.__name__.lower()
        self.tracer = tracer or trace.get_tracer(f"dspy.{self.trace_name}")
        
    def __call__(self, *args, **kwargs):
        with self.tracer.start_as_current_span(f"{self.trace_name}_call"):
            return super().__call__(*args, **kwargs)
            
    def forward(self, **kwargs):
        with self.tracer.start_as_current_span(f"{self.trace_name}_forward"):
            return super().forward(**kwargs)
            
    def predict(self, **kwargs):
        with self.tracer.start_as_current_span(f"{self.trace_name}_predict"):
            return super().predict(**kwargs)


class TracedReAct(dspy.ReAct):
    """
    Traced version of DSPy's ReAct module.
    
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
        tracer: Optional[trace.Tracer] = None
    ):
        super().__init__(signature, tools=tools, max_iters=max_iters)
        self.trace_name = name or self.__class__.__name__.lower()
        self.tracer = tracer or trace.get_tracer(f"dspy.{self.trace_name}")
        
    def __call__(self, *args, **kwargs):
        with self.tracer.start_as_current_span(f"{self.trace_name}_call"):
            return super().__call__(*args, **kwargs)
            
    def forward(self, **kwargs):
        with self.tracer.start_as_current_span(f"{self.trace_name}_forward"):
            return super().forward(**kwargs)
            
    def predict(self, **kwargs):
        with self.tracer.start_as_current_span(f"{self.trace_name}_predict"):
            return super().predict(**kwargs)

