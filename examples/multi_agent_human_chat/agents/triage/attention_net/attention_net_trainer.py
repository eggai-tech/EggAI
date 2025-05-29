import logging
import sys
from pathlib import Path

import mlflow
import numpy as np
import torch
import torch.nn as nn
from torch.optim.lr_scheduler import LambdaLR
from tqdm import tqdm
from transformers import get_cosine_schedule_with_warmup

from agents.triage.attention_net.attention_based_classifier import (
    AttentionBasedClassifier,
    AttentionBasedClassifierWrapper,
)
from agents.triage.attention_net.config import settings
from agents.triage.baseline_model.utils import (
    init_mlflow,
    load_dataset,
    setup_logging,
    unroll_dataset,
)
from libraries.device_utils import get_device

logger = logging.getLogger("attention_net_trainer")


class Trainer:
    """
    A class for training and evaluating a model.
    """

    def __init__(
        self,
        model: AttentionBasedClassifier,
        optimizer: torch.optim.Optimizer,
        loss: nn.Module,
        scheduler: LambdaLR,
        max_num_epochs: int,
        patience: int,
        checkpoint_dir: str,
        train_dataset: dict[str, int],
        val_dataset: dict[str, int],
    ):
        self.optimizer = optimizer
        self.loss = loss
        self.scheduler = scheduler
        self.max_num_epochs = max_num_epochs
        self.patience = patience
        self.checkpoint_dir = Path(checkpoint_dir)
        self.train_dataset = train_dataset
        self.val_dataset = val_dataset
        self.num_iterations = 0
        self.current_patience = 0
        self.best_loss = float("inf")
        # create model wrapper
        self.model_wrapper = AttentionBasedClassifierWrapper(attention_net=model)
        # create random state for shuffling
        self.rs = np.random.RandomState(47)

    def train_epoch(self):
        """
        Train the model for one epoch.
        """
        self.model_wrapper.attention_net.train()
        # init train losses
        train_losses = []
        # shuffle training dataset
        keys = list(self.train_dataset.keys())
        self.rs.shuffle(keys)
        # iterate over training dataset
        for chat in tqdm(keys):
            # IMPORTANT: the model expects the chat history to be a list of strings, each string being a message in the chat
            chat_history = chat.split("\n")
            label = self.train_dataset[chat]
            # convert label to tensor
            target = torch.LongTensor([label]).to(get_device())

            # Forward pass
            output = self.model_wrapper(chat_history)
            loss = self.loss(output, target)
            train_losses.append(loss.item())

            # Backward pass
            self.optimizer.zero_grad()
            loss.backward()
            self.optimizer.step()

            self.num_iterations += 1

        # log training loss to mlflow
        avg_loss = np.mean(train_losses).item()
        mlflow.log_metric("train_loss", avg_loss, step=self.num_iterations)

    def train(self):
        """
        Train the model for a number of epochs.
        """
        # create checkpoint_dir if it does not exist
        if not self.checkpoint_dir.exists():
            self.checkpoint_dir.mkdir(parents=True)

        for _ in tqdm(range(self.max_num_epochs)):
            self.train_epoch()
            logger.info("Validating model...")
            # evaluate on validation dataset
            loss, acc = self.validate()
            logger.info(f"Validation loss: {loss:.4f}, accuracy: {acc:.4f}")
            model = self.model_wrapper.attention_net
            # Save checkpoint
            torch.save(
                model.state_dict(),
                self.checkpoint_dir / f"checkpoint_{self.num_iterations}.pth",
            )
            # Save best model if loss is lower than previous best
            if loss < self.best_loss:
                logger.info(
                    f"Saving new best model with loss: {loss:.4f}, accuracy: {acc:.4f}"
                )
                # Save best model
                torch.save(model.state_dict(), self.checkpoint_dir / "best_model.pth")
                self.best_loss = loss
                # reset patience
                self.current_patience = 0
            else:
                self.current_patience += 1
                if self.current_patience >= self.patience:
                    logger.info("Early stopping triggered!")
                    break

            # log current learning rate to mlflow
            mlflow.log_metric(
                "learning_rate",
                self.optimizer.param_groups[0]["lr"],
                step=self.num_iterations,
            )
            self.scheduler.step()

    def validate(self) -> tuple[float, float]:
        """
        Validate the model on the validation dataset.

        Returns:
            A tuple containing the validation loss and accuracy.
        """
        self.model_wrapper.attention_net.eval()
        # init validation losses and accuracy
        val_losses = []
        val_acc = []

        with torch.inference_mode():
            # iterate over validation dataset
            for chat in tqdm(self.val_dataset.keys()):
                # split chat by new line
                chat_history = chat.split("\n")
                label = self.val_dataset[chat]
                # convert label to tensor
                target = torch.LongTensor([label]).to(get_device())

                # Forward pass
                probs, logits, _, _ = self.model_wrapper.predict_probab(
                    chat_history, return_logits=True
                )
                loss = self.loss(logits, target)
                val_losses.append(loss.item())

                # compute accuracy
                pred = probs.argmax(dim=1).item()
                acc = int(pred == label)
                val_acc.append(acc)

        # log validation loss to mlflow
        avg_loss = np.mean(val_losses).item()
        mlflow.log_metric("val_loss", avg_loss, step=self.num_iterations)
        # log validation accuracy to mlflow
        avg_acc = np.mean(val_acc).item()
        mlflow.log_metric("val_acc", avg_acc, step=self.num_iterations)

        return avg_loss, avg_acc


def main() -> int:
    init_mlflow(settings.mlflow_config_dict)

    logger.info(f"Loading training dataset from {settings.train_dataset_path}")
    train_dataset = load_dataset(settings.train_dataset_path)
    # load test dataset
    logger.info(f"Loading test dataset from {settings.test_dataset_path}")
    test_dataset = load_dataset(settings.test_dataset_path)
    # unroll datasets
    train_dataset = unroll_dataset(train_dataset)
    test_dataset = unroll_dataset(test_dataset)

    # sample test data
    if settings.n_test_samples > 0:
        logger.info(
            f"Sampling {settings.n_test_samples} out of {len(test_dataset)} test samples for validation"
        )
        keys = list(test_dataset.keys())
        rs = np.random.RandomState(47)
        keys = rs.choice(keys, size=settings.n_test_samples, replace=False)
        test_dataset = {k: test_dataset[k] for k in keys}

    logger.info(f"Using device: {get_device()}")
    # create attention based classifier
    model = AttentionBasedClassifier(
        embedding_dim=settings.embedding_dim,
        hidden_dims=settings.hidden_dims,
        n_classes=settings.n_classes,
        dropout=settings.dropout_rate,
    )
    # print the model
    logger.info(f"Attention-based model architecture: {model}")
    # print number of parameters
    num_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info(f"Number of trainable parameters in the model: {num_params}")

    model = model.to(get_device())
    # create optimizer
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=settings.learning_rate,
        betas=settings.betas,
        weight_decay=settings.weight_decay,
    )

    # create loss function
    loss = nn.CrossEntropyLoss()

    max_num_epochs = settings.max_num_epochs
    num_warmup_steps = settings.num_warmup_steps
    scheduler = get_cosine_schedule_with_warmup(
        optimizer,
        num_warmup_steps=num_warmup_steps,
        num_training_steps=max_num_epochs,
    )

    trainer = Trainer(
        model=model,
        optimizer=optimizer,
        loss=loss,
        scheduler=scheduler,
        max_num_epochs=max_num_epochs,
        patience=settings.patience,
        checkpoint_dir=settings.checkpoint_dir,
        train_dataset=train_dataset,
        val_dataset=test_dataset,
    )

    logger.info("Starting training...")
    # lift off
    trainer.train()

    logger.info("Training completed!")
    # load best model
    best_model_path = Path(settings.checkpoint_dir) / "best_model.pth"
    logger.info(f"Loading best model from {best_model_path}")
    best_model_state = torch.load(best_model_path)
    best_model = AttentionBasedClassifier(
        embedding_dim=settings.embedding_dim,
        hidden_dims=settings.hidden_dims,
        n_classes=settings.n_classes,
        dropout=settings.dropout_rate,
    )
    best_model.load_state_dict(best_model_state)
    # save the model in the model registry
    logger.info("Saving model to MLflow model registry")
    mlflow.pytorch.log_model(
        pytorch_model=best_model,
        artifact_path="model",
        registered_model_name=settings.model_name_template.format(
            dropout_rate=settings.dropout_rate, learning_rate=settings.learning_rate
        ),
    )
    return 0


if __name__ == "__main__":
    setup_logging()
    sys.exit(main())
