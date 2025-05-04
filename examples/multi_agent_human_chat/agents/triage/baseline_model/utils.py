import json
import logging

import mlflow
import numpy as np
import pandas as pd
from omegaconf import DictConfig, OmegaConf

CATEGORY_LABEL_MAP = {
    "BILLING": 0,
    "POLICY": 1,
    "CLAIM": 2,
    "ESCALATION": 3,
    "GENERAL": 4,
}

AGENT_TO_CLASS = {
    "BillingAgent": 0,
    "PolicyAgent": 1,
    "ClaimsAgent": 2,
    "EscalationAgent": 3,
    "ChattyAgent": 4,
}


def _replace_agent(msg: str) -> str:
    # replace names of the agents from AGENT_TO_CLASS with "Agent"
    for agent in AGENT_TO_CLASS.keys():
        if agent in msg:
            msg = msg.replace(agent, "Agent")
    return msg


def replace_agent_name(conversation: str) -> str:
    conversation = [_replace_agent(msg) for msg in conversation.split("\n")]
    conversation = "\n".join(conversation)
    return conversation


def sample_training_examples(dataset: dict[str, int], n_examples: int, seed: int) -> tuple[list[str], list[int]]:
    """
    Sample n_examples examples per class.

    Args:
        dataset: Dataset containing the training data. The dataset should be a dictionary where the keys are
            the instruction strings and the values are the corresponding class labels.
        n_examples: Number of examples per class.
        seed: Random seed for sampling.

    Returns:
        A tuple containing:
        X_sampled: Sampled training data.
        y_sampled: Sampled training labels.
    """
    if n_examples is None:
        # return all examples
        return list(dataset.keys()), list(dataset.values())
    rs = np.random.RandomState(seed)
    X_sampled = []
    y_sampled = []
    # sample n_examples examples per class
    for label in set(dataset.values()):
        # get all examples for the current class
        examples = [key for key, value in dataset.items() if value == label]
        # sample n_examples examples
        sampled_examples = rs.choice(examples, size=n_examples, replace=False)
        # add the sampled examples to the list
        X_sampled.extend(sampled_examples)
        y_sampled.extend([label] * n_examples)
    return X_sampled, y_sampled


def load_json_dataset(file_path: str) -> dict[str, int]:
    """
    Loads the dataset from a JSON file.

    """

    with open(file_path, "r") as file:
        data = file.readlines()
        dataset = [json.loads(line) for line in data]
        # filter items with None target_agent
        dataset = [item for item in dataset if item["target_agent"] is not None]

        return {
            replace_agent_name(item["conversation"]): AGENT_TO_CLASS[item["target_agent"]] for item in dataset
        }


def load_csv_dataset(file_path: str, version="v2") -> dict[str, int]:
    """
    Loads the dataset from a CSV file.

    """
    df = pd.read_csv(file_path)
    # convert to a dictionary
    return {row["instruction"]: CATEGORY_LABEL_MAP[row["category"].strip()] for _, row in df.iterrows()}


def load_dataset(file_path: str, version="v2") -> dict[str, int]:
    """
    Loads the dataset from a file. Supports JSON and CSV formats.
    Args:
        file_path (str): Path to the dataset file.
        version (str): Version of the dataset. Default is "v2".

    Returns:
        dict[str, int]: A dictionary where the keys are the instructions and the values are the corresponding labels.
    """
    if file_path.endswith(".jsonl"):
        return load_json_dataset(file_path)
    elif file_path.endswith(".csv"):
        return load_csv_dataset(file_path, version)
    else:
        raise ValueError("Unsupported file format. Please provide a .jsonl or .csv file.")


def load_datasets(file_paths: list[str], version="v2") -> dict[str, int]:
    """
    Loads multiple datasets from a list of file paths. Supports JSON and CSV formats.
    Args:
        file_paths (list[str]): List of paths to the dataset files.
        version (str): Version of the dataset. Default is "v2".

    Returns:
        dict[str, int]: A dictionary where the keys are the instructions and the values are the corresponding labels.
    """
    dataset = {}
    for file_path in file_paths:
        dataset.update(load_dataset(file_path, version))
    return dataset


def setup_logging(log_level: str = "INFO"):
    """
    Set up logging configuration.
    """
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


def init_mlflow(cfg: DictConfig):
    """
    Initialize MLflow tracking.
    """
    # Set the tracking URI and experiment name
    mlflow.set_tracking_uri(cfg.mlflow.tracking_uri)
    mlflow.set_experiment(cfg.mlflow.experiment_name)
    run_name = cfg.mlflow.get("run_name", None)
    mlflow.start_run(run_name=run_name)
    # log the config
    conf_dict = OmegaConf.to_container(cfg, resolve=True)
    mlflow.log_params(conf_dict)
