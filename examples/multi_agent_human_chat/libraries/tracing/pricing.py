#!/usr/bin/env python3
"""
Pricing calculator for AI model usage.
Provides cost calculations for different AI models based on token usage.
"""

from typing import Any, Dict, Tuple

# Default pricing data (fallback if remote loading fails)
DEFAULT_PRICING_DATA = {
    "chat": {
        # OpenAI Models
        "gpt-4o": {
            "input": 0.0005,  # $0.0005 per 1K tokens
            "output": 0.0015,  # $0.0015 per 1K tokens
        },
        "gpt-4o-mini": {
            "input": 0.00015,  # $0.00015 per 1K tokens
            "output": 0.0006,  # $0.0006 per 1K tokens
        },
        "gpt-4": {
            "input": 0.003,  # $0.003 per 1K tokens
            "output": 0.006,  # $0.006 per 1K tokens
        },
        "gpt-4-turbo": {
            "input": 0.001,  # $0.001 per 1K tokens
            "output": 0.003,  # $0.003 per 1K tokens
        },
        "gpt-3.5-turbo": {
            "input": 0.0005,  # $0.0005 per 1K tokens
            "output": 0.0015,  # $0.0015 per 1K tokens
        },
        # Anthropic Models
        "claude-3-5-sonnet-20241022": {
            "input": 0.003,  # $0.003 per 1K tokens
            "output": 0.015,  # $0.015 per 1K tokens
        },
        "claude-3-sonnet-20240229": {
            "input": 0.003,  # $0.003 per 1K tokens
            "output": 0.015,  # $0.015 per 1K tokens
        },
        "claude-3-haiku-20240307": {
            "input": 0.00025,  # $0.00025 per 1K tokens
            "output": 0.00125,  # $0.00125 per 1K tokens
        },
        # Google Models
        "gemini-1.5-pro": {
            "input": 0.0035,  # $0.0035 per 1K tokens
            "output": 0.0105,  # $0.0105 per 1K tokens
        },
        "gemini-1.5-flash": {
            "input": 0.000075,  # $0.000075 per 1K tokens
            "output": 0.0003,  # $0.0003 per 1K tokens
        },
        "gemini-1.0-pro": {
            "input": 0.0005,  # $0.0005 per 1K tokens
            "output": 0.0015,  # $0.0015 per 1K tokens
        },
        # Meta/Llama Models (via Groq or other providers)
        "llama3-8b-8192": {
            "input": 0.00005,  # $0.00005 per 1K tokens
            "output": 0.00008,  # $0.00008 per 1K tokens
        },
        "llama3-70b-8192": {
            "input": 0.00059,  # $0.00059 per 1K tokens
            "output": 0.00079,  # $0.00079 per 1K tokens
        },
        # Mixtral Models
        "mixtral-8x7b-32768": {
            "input": 0.00024,  # $0.00024 per 1K tokens
            "output": 0.00024,  # $0.00024 per 1K tokens
        },
    }
}


class PricingCalculator:
    """Calculator for AI model pricing based on token usage."""

    def __init__(self):
        """Initialize the pricing calculator."""
        self.pricing_data = self._load_pricing_data()

    def _load_pricing_data(self) -> Dict[str, Any]:
        """Load pricing data from remote source or use default."""
        try:
            # Try to load from remote source (could be a URL in production)
            # For now, just use the default data
            return DEFAULT_PRICING_DATA
        except Exception:
            # Fallback to default pricing
            return DEFAULT_PRICING_DATA

    def _normalize_model_name(self, model_name: str) -> str:
        """Normalize model name to match pricing data keys."""
        if not model_name:
            return "gpt-3.5-turbo"  # Default fallback

        model_lower = model_name.lower().strip()

        # OpenAI models
        if model_lower in ["gpt-4o", "gpt-4o-2024-05-13"]:
            return "gpt-4o"
        elif model_lower in ["gpt-4o-mini", "gpt-4o-mini-2024-07-18"]:
            return "gpt-4o-mini"
        elif model_lower in ["gpt-4", "gpt-4-0613", "gpt-4-0314"]:
            return "gpt-4"
        elif model_lower in ["gpt-4-turbo", "gpt-4-turbo-2024-04-09"]:
            return "gpt-4-turbo"
        elif model_lower in ["gpt-3.5-turbo", "gpt-3.5-turbo-0125"]:
            return "gpt-3.5-turbo"

        # Anthropic models
        elif "claude-3.5-sonnet" in model_lower or "claude-3-5-sonnet" in model_lower:
            return "claude-3-5-sonnet-20241022"
        elif "claude-3-sonnet" in model_lower:
            return "claude-3-sonnet-20240229"
        elif "claude-3-haiku" in model_lower:
            return "claude-3-haiku-20240307"

        # Google models
        elif "gemini-1.5-pro" in model_lower:
            return "gemini-1.5-pro"
        elif "gemini-1.5-flash" in model_lower:
            return "gemini-1.5-flash"
        elif "gemini-pro" in model_lower or "gemini-1.0-pro" in model_lower:
            return "gemini-1.0-pro"

        # Meta/Llama models
        elif "llama3-8b" in model_lower or "llama-3-8b" in model_lower:
            return "llama3-8b-8192"
        elif "llama3-70b" in model_lower or "llama-3-70b" in model_lower:
            return "llama3-70b-8192"

        # Mixtral models
        elif "mixtral-8x7b" in model_lower:
            return "mixtral-8x7b-32768"

        # LM Studio models (map to local model equivalents)
        elif "lm_studio" in model_lower or "lm-studio" in model_lower:
            if "llama" in model_lower and ("8b" in model_lower or "7b" in model_lower):
                return "llama3-8b-8192"
            elif "mixtral" in model_lower:
                return "mixtral-8x7b-32768"
            else:
                return "llama3-8b-8192"  # Default for LM Studio

        # Default fallback
        return "gpt-3.5-turbo"

    def get_model_pricing(self, model_name: str) -> Tuple[float, float]:
        """Get pricing for a model (input_price_per_1k, output_price_per_1k)."""
        normalized_name = self._normalize_model_name(model_name)

        if normalized_name in self.pricing_data["chat"]:
            pricing = self.pricing_data["chat"][normalized_name]
            return pricing["input"], pricing["output"]
        else:
            # Fallback to default pricing
            default_pricing = self.pricing_data["chat"]["gpt-3.5-turbo"]
            return default_pricing["input"], default_pricing["output"]

    def calculate_cost(
        self, model_name: str, prompt_tokens: int, completion_tokens: int
    ) -> Dict[str, Any]:
        """Calculate cost for a request."""
        # Handle negative tokens gracefully
        prompt_tokens = max(0, prompt_tokens)
        completion_tokens = max(0, completion_tokens)

        # Get pricing
        input_price_per_1k, output_price_per_1k = self.get_model_pricing(model_name)

        # Calculate costs
        prompt_cost = (prompt_tokens / 1000.0) * input_price_per_1k
        completion_cost = (completion_tokens / 1000.0) * output_price_per_1k
        total_cost = prompt_cost + completion_cost

        return {
            "prompt_cost": prompt_cost,
            "completion_cost": completion_cost,
            "total_cost": total_cost,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "model": model_name,
            "prompt_price_per_1k": input_price_per_1k,
            "completion_price_per_1k": output_price_per_1k,
        }

    def get_supported_models(self) -> Dict[str, Dict[str, float]]:
        """Get all supported models and their pricing."""
        return self.pricing_data["chat"]


# Global pricing calculator instance (singleton)
_pricing_calculator = None


def get_pricing_calculator() -> PricingCalculator:
    """Get the global pricing calculator instance."""
    global _pricing_calculator
    if _pricing_calculator is None:
        _pricing_calculator = PricingCalculator()
    return _pricing_calculator


def calculate_request_cost(
    model_name: str, prompt_tokens: int, completion_tokens: int
) -> Dict[str, Any]:
    """Convenience function to calculate request cost."""
    calculator = get_pricing_calculator()
    return calculator.calculate_cost(model_name, prompt_tokens, completion_tokens)


# Export the main functions and classes
__all__ = [
    "PricingCalculator",
    "get_pricing_calculator",
    "calculate_request_cost",
    "DEFAULT_PRICING_DATA",
]
