import logging
import sys

import hydra
import mlflow
from dotenv import load_dotenv
from omegaconf import DictConfig

from agents.triage.baseline_model.few_shots_classifier import FewShotsClassifier
from agents.triage.baseline_model.utils import load_datasets, init_mlflow, setup_logging

logger = logging.getLogger("fewshot_trainer")

load_dotenv()

@hydra.main(config_path="configs", config_name="fewshot_trainer_config")
def main(cfg: DictConfig) -> int:
    # print current working directory
    logger.info(f"Current working directory: {hydra.utils.get_original_cwd()}")
    init_mlflow(cfg)

    # load triage dataset
    logger.info(f"Loading dataset from {cfg.dataset.paths}")
    dataset = load_datasets(cfg.dataset.paths)

    if isinstance(cfg.model.seed, int):
        seeds = [cfg.model.seed]
    else:
        assert len(cfg.model.seed) > 1
        seeds = cfg.model.seed

    # create few-shot classifier
    fewshot_classifier = FewShotsClassifier(
        n_classes=cfg.model.n_classes,
        n_examples=cfg.model.n_examples,
        seeds=seeds,
    )

    # train the classifier
    logger.info(f"Training few-shot classifier with {cfg.model.n_examples} examples")
    fewshot_classifier.fit(dataset)

    # save the model locally
    logger.info(f"Saving classifier to {cfg.model.checkpoint_dir}")
    model_path = fewshot_classifier.save(cfg.model.checkpoint_dir, cfg.model.name)

    # save the model in the model registry
    logger.info(f"Saving model to MLflow model registry")
    mlflow.sklearn.log_model(
        sk_model=fewshot_classifier,
        artifact_path="model",
        registered_model_name=model_path.stem,
    )
    return 0


if __name__ == "__main__":
    setup_logging()
    sys.exit(main())
