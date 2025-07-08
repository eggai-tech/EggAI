from datetime import datetime
from typing import Any, Dict, Optional

import mlflow


class MLflowTracker:

    def __init__(
        self,
        experiment_name: str,
        run_name: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None
    ):
        self.experiment_name = experiment_name
        self.run_name = run_name
        self.params = params

    def __enter__(self):
        mlflow.set_experiment(self.experiment_name)
        if self.run_name is None:
            self.run_name = (
                f"test_run_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
            )

        self.run = mlflow.start_run(run_name=self.run_name)

        if self.params:
            for key, value in self.params.items():
                mlflow.log_param(key, value)

        return self.run

    def __exit__(self, exc_type, exc_val, exc_tb):
        mlflow.end_run()
        return False  # Don't suppress exceptions


def setup_mlflow_tracking(
    experiment_name: str,
    run_name: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None
) -> MLflowTracker:
    return MLflowTracker(experiment_name, run_name, params)