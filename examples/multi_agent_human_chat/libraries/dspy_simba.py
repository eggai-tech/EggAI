import datetime
import os
import time
from typing import Callable, List, Optional

import dspy
import mlflow
from dspy.evaluate import Evaluate

from libraries.logger import get_console_logger

logger = get_console_logger("dspy_simba.optimizer")


class SIMBAOptimizer:
    """
    Optimizer for DSPy modules using SIMBA (Stochastic Introspective Mini-Batch Ascent).

    This optimizer improves DSPy modules by updating their prompts and adding demonstrations.

    Attributes:
        metric: Evaluation metric function used to measure performance
        max_steps: Maximum number of optimization steps to perform
        max_demos: Maximum number of demonstrations to include
        verbose: Whether to print verbose output during optimization
    """

    def __init__(
        self,
        metric: Callable,
        max_steps: int = 8,
        max_demos: int = 5,
        verbose: bool = True,
    ):
        self.metric = metric
        self.max_steps = max_steps
        self.max_demos = max_demos
        self.verbose = verbose
        self.dspy_optimizer = dspy.SIMBA(
            metric=metric, max_steps=max_steps, max_demos=max_demos
        )

    def optimize(
        self,
        program: dspy.Module,
        trainset: List[dspy.Example],
        devset: Optional[List[dspy.Example]] = None,
        experiment_name: str = "dspy_optimization",
        run_name: Optional[str] = None,
        output_path: Optional[str] = None,
        seed: int = 42,
    ) -> dspy.Module:
        """
        Optimize a DSPy module using SIMBA.

        Args:
            program: The DSPy module to optimize
            trainset: The training dataset
            devset: Optional development dataset for evaluation
            experiment_name: MLflow experiment name
            run_name: Optional MLflow run name
            output_path: Optional path to save the optimized model
            seed: Random seed for reproducibility

        Returns:
            The optimized DSPy module
        """
        mlflow.set_experiment(experiment_name)

        if run_name is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            run_name = f"simba_optimization_{timestamp}"

        with mlflow.start_run(run_name=run_name):
            mlflow.log_params(
                {
                    "optimizer": "SIMBA",
                    "max_steps": self.max_steps,
                    "max_demos": self.max_demos,
                    "train_examples": len(trainset),
                    "dev_examples": len(devset) if devset else 0,
                    "seed": seed,
                }
            )

            # Enable automatic DSPy logging
            mlflow.dspy.autolog(
                log_compiles=True,
                log_traces=True,
                log_evals=True,
                log_traces_from_compile=True,
                log_traces_from_eval=True,
            )

            # Evaluate baseline
            if devset:
                evaluator = Evaluate(
                    devset=devset, metric=self.metric, num_threads=min(4, len(devset))
                )

                logger.info("Evaluating baseline performance...")
                baseline_score = evaluator(program)
                logger.info(f"Baseline score: {baseline_score:.3f}")
                mlflow.log_metric("baseline_score", baseline_score)
            else:
                logger.info("No development set provided, skipping baseline evaluation")
                baseline_score = None

            # Optimize program
            logger.info(f"Starting SIMBA optimization with {self.max_steps} steps...")
            start_time = time.time()

            optimized_program = self.dspy_optimizer.compile(
                program, trainset=trainset, seed=seed
            )

            optimization_time = time.time() - start_time
            logger.info(f"Optimization completed in {optimization_time:.1f} seconds")
            mlflow.log_metric("optimization_time_seconds", optimization_time)

            # Evaluate optimized program
            if devset:
                logger.info("Evaluating optimized performance...")
                optimized_score = evaluator(optimized_program)
                logger.info(f"Optimized score: {optimized_score:.3f}")

                if baseline_score is not None:
                    improvement = optimized_score - baseline_score
                    relative_improvement = (
                        improvement / max(baseline_score, 1e-9)
                    ) * 100
                    logger.info(f"Absolute improvement: {improvement:.3f}")
                    logger.info(f"Relative improvement: {relative_improvement:.1f}%")

                    mlflow.log_metric("optimized_score", optimized_score)
                    mlflow.log_metric("absolute_improvement", improvement)
                    mlflow.log_metric("relative_improvement", relative_improvement)

            # Save the optimized program if path is provided
            if output_path:
                self._save_optimized_program(optimized_program, output_path)
                mlflow.log_artifact(output_path)
                logger.info(f"Saved optimized program to {output_path}")

            return optimized_program

    def _save_optimized_program(self, program: dspy.Module, output_path: str) -> None:
        """Save the optimized program to a file."""
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        # Save the program
        program.save(output_path)

    @staticmethod
    def load_optimized_program(path: str) -> dspy.Module:
        """
        Load an optimized program from a file.

        Args:
            path: Path to the saved program

        Returns:
            The loaded DSPy module
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Optimized program file not found at {path}")

        try:
            return dspy.Program.load(path)
        except Exception as e:
            logger.error(f"Error loading optimized program: {e}")
            raise


def optimize_react_agent(
    agent_class: type,
    signature_class: type,
    tools: List[Callable],
    trainset: List[dspy.Example],
    devset: Optional[List[dspy.Example]] = None,
    metric: Optional[Callable] = None,
    max_steps: int = 8,
    max_demos: int = 5,
    max_iters: int = 5,
    output_path: Optional[str] = None,
    experiment_name: str = "react_optimization",
    seed: int = 42,
) -> dspy.Module:
    """
    Optimize a ReAct agent using SIMBA.

    Args:
        agent_class: The ReAct agent class to optimize (typically dspy.ReAct or TracedReAct)
        signature_class: The signature class for the agent
        tools: List of tools the agent can use
        trainset: Training dataset
        devset: Optional development dataset
        metric: Evaluation metric (defaults to accuracy)
        max_steps: Maximum optimization steps
        max_demos: Maximum demonstrations to include
        max_iters: Maximum iterations for the ReAct agent
        output_path: Path to save the optimized model
        experiment_name: MLflow experiment name
        seed: Random seed for reproducibility

    Returns:
        The optimized ReAct agent
    """
    # Create unoptimized agent
    agent = agent_class(signature_class, tools=tools, max_iters=max_iters)

    # Default to accuracy metric if none provided
    if metric is None:

        def default_metric(example, prediction, trace=None) -> float:
            """Default accuracy metric."""
            gold = getattr(example, "answer", "")
            pred = getattr(prediction, "answer", "")

            if not gold or not pred:
                return 0.0

            return float(gold.lower().strip() == pred.lower().strip())

        metric = default_metric

    # Create optimizer
    optimizer = SIMBAOptimizer(metric=metric, max_steps=max_steps, max_demos=max_demos)

    # Run optimization
    return optimizer.optimize(
        program=agent,
        trainset=trainset,
        devset=devset,
        experiment_name=experiment_name,
        output_path=output_path,
        seed=seed,
    )


def load_optimized_react_agent(
    path: str,
    agent_class: type,
    signature_class: type,
    tools: List[Callable],
    max_iters: int = 5,
) -> dspy.Module:
    """
    Load an optimized ReAct agent or create a new one with the original signature.

    This function tries to load an optimized agent from the given path.
    If the file doesn't exist or loading fails, it creates a new agent with the original signature.

    Args:
        path: Path to the saved optimized agent
        agent_class: The ReAct agent class (typically dspy.ReAct or TracedReAct)
        signature_class: The signature class for the agent
        tools: List of tools the agent can use
        max_iters: Maximum iterations for the ReAct agent

    Returns:
        Either the loaded optimized agent or a new unoptimized agent
    """
    # Check if the optimized file exists
    if os.path.exists(path):
        try:
            logger.info(f"Loading optimized agent from {path}")
            # Try to load the optimized agent
            return dspy.Program.load(path)
        except Exception as e:
            logger.error(
                f"Failed to load optimized agent: {e}. Creating unoptimized agent instead."
            )
    else:
        logger.info(f"No optimized agent found at {path}. Creating unoptimized agent.")

    # Create unoptimized agent
    return agent_class(signature_class, tools=tools, max_iters=max_iters)
