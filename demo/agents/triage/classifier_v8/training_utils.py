import logging

import dspy
import mlflow
from datasets import Dataset
from peft import LoraConfig, TaskType, get_peft_model
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from transformers import (
    AutoConfig,
    AutoTokenizer,
    DataCollatorWithPadding,
    RobertaForSequenceClassification,
    Trainer,
    TrainingArguments,
)

from agents.triage.classifier_v8.config import ClassifierV8Settings
from agents.triage.data_sets.loader import ID2LABEL, LABEL2ID

logger = logging.getLogger(__name__)
v8_settings = ClassifierV8Settings()


def log_training_parameters():
    try:
        mlflow.log_params({
            "model_name": v8_settings.model_name,
            "train_sample_size": v8_settings.train_sample_size,
            "eval_sample_size": v8_settings.eval_sample_size,
            "learning_rate": v8_settings.learning_rate,
            "num_epochs": v8_settings.num_epochs,
            "batch_size": v8_settings.batch_size,
            "gradient_accumulation_steps": v8_settings.gradient_accumulation_steps,
            "lora_r": v8_settings.lora_r,
            "lora_alpha": v8_settings.lora_alpha,
            "lora_dropout": v8_settings.lora_dropout
        })
    except Exception as e:
        logger.warning(f"Could not log parameters to MLflow: {e}")


def compute_metrics(eval_pred):
    predictions, labels = eval_pred
    predictions = predictions.argmax(axis=-1)

    precision, recall, f1, _ = precision_recall_fscore_support(labels, predictions, average='weighted')
    accuracy = accuracy_score(labels, predictions)

    return {
        'accuracy': accuracy,
        'f1': f1,
        'precision': precision,
        'recall': recall
    }


def perform_fine_tuning(trainset: list[dspy.Example], testset: list[dspy.Example]):
    model_name = v8_settings.model_name
    logger.info(f"Loading base model: {model_name}")

    tokenizer = AutoTokenizer.from_pretrained(model_name)

    # Load the appropriate config class for this model
    config = AutoConfig.from_pretrained(model_name)
    # set the label mapping
    config.label2id = LABEL2ID
    config.id2label = ID2LABEL
    config.num_labels = len(ID2LABEL)

    model = RobertaForSequenceClassification.from_pretrained(
        model_name,
        config=config,
    )

    # Move model to specified device
    device = v8_settings.device
    model = model.to(device)
    logger.info(f"Model moved to device: {device}")

    lora_config = LoraConfig(
        task_type=TaskType.SEQ_CLS,
        r=v8_settings.lora_r,
        lora_alpha=v8_settings.lora_alpha,
        lora_dropout=v8_settings.lora_dropout,
        target_modules=v8_settings.lora_target_modules
    )

    # get PEFT model with LoRA configuration
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    model.train()

    # Prepare training data
    train_texts = [ex.chat_history for ex in trainset]
    train_labels = [LABEL2ID[ex.target_agent] for ex in trainset]

    # Prepare evaluation data
    eval_texts = [ex.chat_history for ex in testset]
    eval_labels = [LABEL2ID[ex.target_agent] for ex in testset]

    # Create datasets
    train_dataset = Dataset.from_dict({"text": train_texts, "labels": train_labels})
    eval_dataset = Dataset.from_dict({"text": eval_texts, "labels": eval_labels})

    def preprocess(examples):
        tokenized = tokenizer(examples['text'], truncation=True, padding=True)
        return tokenized

    tokenized_train_dataset = train_dataset.map(preprocess, batched=True, remove_columns=["text"])
    tokenized_eval_dataset = eval_dataset.map(preprocess, batched=True, remove_columns=["text"])
    data_collator = DataCollatorWithPadding(tokenizer=tokenizer, return_tensors="pt")

    training_args = TrainingArguments(
        output_dir=v8_settings.output_dir,
        num_train_epochs=v8_settings.num_epochs,
        per_device_train_batch_size=v8_settings.batch_size,
        per_device_eval_batch_size=v8_settings.batch_size,
        gradient_accumulation_steps=v8_settings.gradient_accumulation_steps,
        optim="adamw_torch",
        learning_rate=v8_settings.learning_rate,
        warmup_ratio=0.1,
        logging_steps=50,
        save_total_limit=1,  # max of two checkpoints might be saved: # 1 for the best model, 1 for the last checkpoint
        # Evaluation configuration
        eval_strategy="epoch",  # Evaluate after each epoch
        eval_steps=1,  # How often to evaluate (in epochs)
        save_strategy="epoch",  # Save after each epoch
        load_best_model_at_end=True,  # Load best model at end
        metric_for_best_model="eval_accuracy",  # Use accuracy to determine best model
        greater_is_better=True,  # Higher accuracy is better
        gradient_checkpointing=False,  # Disable to avoid gradient issues
        report_to="mlflow",
        label_names=["labels"]
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_train_dataset,
        eval_dataset=tokenized_eval_dataset,
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
    )

    logger.info("Starting LoRA fine-tuning...")
    trainer.train()

    logger.info("Finished training. Evaluating model...")
    eval_results = trainer.evaluate()

    mlflow.log_metrics({
        "final_accuracy": eval_results["eval_accuracy"],
        "final_f1": eval_results["eval_f1"],
        "final_precision": eval_results["eval_precision"],
        "final_recall": eval_results["eval_recall"],
    })

    # save the model
    logger.info(f"Saving the merged model (base_model + lora_adapters) to {v8_settings.output_dir}")
    # get the best model from the trainer
    best_model = trainer.model
    # merge LoRA adapters into the base model
    best_model = best_model.merge_and_unload()
    # save the merged model
    best_model.save_pretrained(v8_settings.output_dir)
    # save the tokenizer
    tokenizer.save_pretrained(v8_settings.output_dir)

    logger.info(f"Model saved to {v8_settings.output_dir}")
    logger.info(f"Final evaluation results: {eval_results}")

    return trainer.model, tokenizer


def show_training_info():
    logger.info("=" * 50)
    logger.info("CLASSIFIER V8 TRAINING CONFIGURATION")
    logger.info("=" * 50)
    logger.info(f"Base Model: {v8_settings.model_name}")
    logger.info(f"Output Directory: {v8_settings.output_dir}")
    logger.info(f"Learning Rate: {v8_settings.learning_rate}")
    logger.info(f"Epochs: {v8_settings.num_epochs}")
    logger.info(f"Batch Size: {v8_settings.batch_size}")
    logger.info(f"Gradient Accumulation: {v8_settings.gradient_accumulation_steps}")
    logger.info(f"LoRA r: {v8_settings.lora_r}")
    logger.info(f"LoRA alpha: {v8_settings.lora_alpha}")
    logger.info(f"LoRA dropout: {v8_settings.lora_dropout}")
    logger.info(f"LoRA target modules: {v8_settings.lora_target_modules}")
    logger.info(f"Device: {v8_settings.device}")
    logger.info("=" * 50)
