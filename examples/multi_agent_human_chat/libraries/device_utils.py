"""Device detection utilities for PyTorch."""

import torch


def get_device() -> str:
    """Get the optimal device for PyTorch operations."""
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        return "mps"
    if hasattr(torch, 'xpu') and torch.xpu.is_available():
        return "xpu"
    return "cpu"