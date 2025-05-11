"""
SIMBA optimization utilities.

This module provides utilities for optimizing and loading SIMBA-optimized models.
"""
import os
from typing import Callable, List, Optional

import dspy
import mlflow

from libraries.logger import get_console_logger

logger = get_console_logger("dspy.simba")


def optimize_with_simba(
    program: dspy.Module,
    trainset: List[dspy.Example],
    metric: Callable,
    output_path: Optional[str] = None,
    max_steps: int = 8,
    max_demos: int = 5,
    log_to_mlflow: bool = True,
    experiment_name: str = "dspy_optimization",
    seed: int = 42
) -> dspy.Module:
    """
    Optimize a DSPy module using SIMBA algorithm.
    
    Args:
        program: The DSPy module to optimize
        trainset: The training dataset
        metric: Evaluation metric function
        output_path: Optional path to save the optimized model
        max_steps: Maximum optimization steps
        max_demos: Maximum demonstrations to include
        log_to_mlflow: Whether to log to MLflow
        experiment_name: MLflow experiment name
        seed: Random seed for reproducibility
        
    Returns:
        The optimized DSPy module
    """
    logger.info(f"Starting SIMBA optimization with {len(trainset)} examples...")
    
    # Set up MLflow logging if enabled
    if log_to_mlflow:
        mlflow.set_experiment(experiment_name)
        mlflow.log_params({
            "optimizer": "SIMBA",
            "max_steps": max_steps,
            "max_demos": max_demos,
            "train_examples": len(trainset),
            "seed": seed
        })
    
    # Create and run the optimizer
    simba = dspy.SIMBA(metric=metric, max_steps=max_steps, max_demos=max_demos)
    optimized_program = simba.compile(program, trainset=trainset, seed=seed)
    
    # Save the optimized program if path provided
    if output_path:
        logger.info(f"Saving optimized model to {output_path}")
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        optimized_program.save(output_path)
        
        if log_to_mlflow:
            mlflow.log_artifact(output_path)
    
    logger.info("SIMBA optimization complete")
    return optimized_program


def load_optimized_model(path: str) -> Optional[dspy.Module]:
    """
    Load a SIMBA-optimized model from a file.

    Args:
        path: Path to the saved model

    Returns:
        The loaded model or None if loading fails
    """
    if not os.path.exists(path):
        logger.warning(f"Optimized model not found at {path}")
        return None

    try:
        logger.info(f"Loading optimized model from {path}")

        # In DSPy 2.6.23, the load method needs to be called as an instance method
        program = dspy.Program()
        return program.load(path)
    except Exception as e:
        # Try alternative loading method if the first one fails
        try:
            logger.info(f"Trying alternative loading method for optimized model")
            # Import json and load directly
            import json
            with open(path, 'r') as f:
                json_data = json.load(f)
                logger.info(f"Successfully loaded JSON data from {path}")
                # Since we can't directly load the program,
                # return None and let the fallback mechanism handle it
                logger.info("JSON data loaded but can't create program, will use fallback")
                return None
        except Exception as e2:
            logger.error(f"All loading methods failed: {e2}")
            return None