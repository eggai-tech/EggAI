"""Device management utilities for V7 classifier."""

from typing import Optional, Tuple

import torch


def is_cuda_available() -> bool:
    """Check if CUDA is available."""
    return torch.cuda.is_available()


def is_mps_available() -> bool:
    """Check if MPS is available.""" 
    return torch.backends.mps.is_available()


def no_grad():
    """Return torch.no_grad() context manager."""
    return torch.no_grad()


def get_device_config() -> Tuple[Optional[str], torch.dtype]:
    """Get optimal device configuration for model loading.
    
    Ideally the target device for the model, input, output should be configurable: cuda, mps, cpu
    
    Returns:
        Tuple of (device_map, dtype) for model loading
    """
    if torch.cuda.is_available():
        device_map = "auto"  # CUDA supports automatic device mapping
        # Use bfloat16 for newer GPUs (compute capability >= 8.0)
        dtype = torch.bfloat16 if torch.cuda.get_device_capability()[0] >= 8 else torch.float16
        print(f"Using CUDA device with {dtype}")
    elif torch.backends.mps.is_available():
        device_map = None  # MPS doesn't support device_map="auto"
        dtype = torch.float32  # Use float32 for MPS to avoid training issues
        print("Using MPS device with float32")
    else:
        device_map = None  # CPU fallback
        dtype = torch.float32
        print("Using CPU device with float32")
    
    return device_map, dtype


def move_to_mps(model, device_map: Optional[str] = None):
    """Move to mps if available and device_map is None.
    
    Args:
        model: The model to move
        device_map: Device mapping used during loading
        
    Returns:
        Model on appropriate device
    """
    # Only move to MPS if device_map wasn't used and MPS is available
    if torch.backends.mps.is_available() and device_map is None:
        model = model.to("mps")
    
    return model


def get_training_precision() -> dict:
    """Get precision settings for training.
    
    Returns:
        Dictionary with fp16 and bf16 settings
    """
    has_cuda = torch.cuda.is_available()
    has_mps = torch.backends.mps.is_available()
    
    # MPS doesn't handle fp16/bf16 training well, use float32
    if has_mps:
        return {
            "fp16": False,
            "bf16": False,
        }
    
    return {
        "fp16": has_cuda,
        "bf16": has_cuda and torch.cuda.get_device_capability()[0] >= 8,
    }