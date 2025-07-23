import logging
import os
import time
from datetime import datetime

import mlflow
import torch
from triage.classifier_v7.config import ClassifierV7Settings
from triage.classifier_v7.device_utils import (
    get_device_config,
    get_training_precision,
    move_to_mps,
)
from triage.data_sets.loader import AGENT_STR_TO_LABEL

# Set tokenizers parallelism to avoid warnings during training
os.environ["TOKENIZERS_PARALLELISM"] = "false"
logger = logging.getLogger(__name__)
import numpy as np
from datasets import Dataset
from peft import LoraConfig, TaskType, get_peft_model
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
)
from transformers import (
    AutoConfig,
    AutoModelForSequenceClassification,
    AutoTokenizer,
    BitsAndBytesConfig,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
)


def setup_mlflow_tracking(model_name: str) -> str:
    mlflow.dspy.autolog()
    mlflow.set_experiment("triage_classifier")
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"{model_name}_{timestamp}"


def log_training_parameters(sample_size: int, model_name: str, trainset_size: int, testset_size: int):
    mlflow.log_param("version", "v7")
    mlflow.log_param("model", model_name)
    mlflow.log_param("samples", sample_size)
    mlflow.log_param("train_examples", trainset_size)
    mlflow.log_param("test_examples", testset_size)


def compute_metrics(eval_pred):
    predictions, labels = eval_pred
    predictions = np.argmax(predictions, axis=1)

    # Basic metrics
    accuracy = accuracy_score(labels, predictions)
    precision, recall, f1, _ = precision_recall_fscore_support(labels, predictions, average='weighted', zero_division=0)

    # Per-class metrics
    agent_names = ["BillingAgent", "ClaimsAgent", "PolicyAgent", "EscalationAgent", "ChattyAgent"]
    precision_per_class, recall_per_class, f1_per_class, support = precision_recall_fscore_support(
        labels, predictions, average=None, zero_division=0
    )

    metrics = {
        'accuracy': accuracy,
        'f1': f1,
        'precision': precision,
        'recall': recall,
    }

    # Add per-class metrics
    for i, agent_name in enumerate(agent_names):
        if i < len(precision_per_class):
            metrics[f'{agent_name.lower()}_precision'] = precision_per_class[i]
            metrics[f'{agent_name.lower()}_recall'] = recall_per_class[i]
            metrics[f'{agent_name.lower()}_f1'] = f1_per_class[i]
            metrics[f'{agent_name.lower()}_support'] = support[i]

    return metrics

def perform_fine_tuning(trainset: list, testset: list):
    v7_settings = ClassifierV7Settings()
    
    logger.info(f"Starting HuggingFace Gemma3 fine-tuning with {len(trainset)} examples")
    logger.info(f"Model: {v7_settings.get_model_name()}")
    logger.info(f"LoRA: {v7_settings.use_lora}, 4-bit: {v7_settings.use_4bit}, QAT: {v7_settings.use_qat_model}")
    
    start_time = time.time()

    # Load model and tokenizer
    model_name = v7_settings.get_model_name()
    logger.info(f"Loading model and tokenizer: {model_name}")
    if v7_settings.use_qat_model:
        logger.info("Using QAT (Quantized Aware Training) model variant")

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Configure quantization
    quantization_config = None
    if v7_settings.use_4bit and not v7_settings.use_qat_model and torch.cuda.is_available():
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.get_device_capability()[0] >= 8 else torch.float16,
            bnb_4bit_use_double_quant=True,
        )

    device_map, dtype = get_device_config()

    # Load the appropriate config class for this model
    config = AutoConfig.from_pretrained(model_name)
    config.num_labels = v7_settings.n_classes  # Set number of classes for classification

    model = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        config=config,
        quantization_config=quantization_config,
        torch_dtype=dtype,
        device_map=device_map,
        attn_implementation="eager"  # More stable than flash attention
    )

    # Move to appropriate device
    model = move_to_mps(model, device_map)

    # Configure LoRA
    if v7_settings.use_lora:
        logger.info("Using LoRA for fine-tuning")
        # IMPORTANT: we need to save the classifier layer together with the LoRA adapters, see Gemma3TextForSequenceClassification
        assert hasattr(model, "classifier")
        modules_to_save = ["classifier"]
        lora_config = LoraConfig(
            lora_alpha=v7_settings.lora_alpha,
            lora_dropout=v7_settings.lora_dropout,
            r=v7_settings.lora_r,
            bias="none",
            target_modules="all-linear",
            task_type=TaskType.SEQ_CLS,
            modules_to_save=modules_to_save,  # Save the classifier layer together with the LoRA adapters
        )
        mlflow.log_params(lora_config.to_dict())
        model = get_peft_model(model, lora_config)
        model.print_trainable_parameters()

    logger.info(f"Num train examples: {len(trainset)}")
    logger.info(f"Num eval examples: {len(testset)}")

    # Prepare training data
    train_texts = [ex.chat_history for ex in trainset]
    train_labels = [AGENT_STR_TO_LABEL[ex.target_agent] for ex in trainset]

    # Prepare evaluation data
    eval_texts = [ex.chat_history for ex in testset]
    eval_labels = [AGENT_STR_TO_LABEL[ex.target_agent] for ex in testset]

    def tokenize_function(examples):
        # Tokenize the text
        model_inputs = tokenizer(
            examples["text"],
            truncation=True,
            padding=False,
            max_length=v7_settings.max_length,
            return_tensors=None
        )
        # For sequence classification, labels are the class IDs
        model_inputs["labels"] = examples["labels"]
        return model_inputs

    # Create datasets
    train_dataset = Dataset.from_dict({"text": train_texts, "labels": train_labels})
    eval_dataset = Dataset.from_dict({"text": eval_texts, "labels": eval_labels})

    tokenized_train_dataset = train_dataset.map(tokenize_function, batched=True, remove_columns=["text"])
    tokenized_eval_dataset = eval_dataset.map(tokenize_function, batched=True, remove_columns=["text"])

    # Training arguments with evaluation
    training_args = TrainingArguments(
        output_dir=v7_settings.output_dir,
        num_train_epochs=v7_settings.num_epochs,
        per_device_train_batch_size=v7_settings.batch_size,
        per_device_eval_batch_size=v7_settings.batch_size,
        gradient_accumulation_steps=v7_settings.gradient_accumulation_steps,
        optim="adamw_torch",
        learning_rate=v7_settings.learning_rate,
        lr_scheduler_type="constant",
        warmup_ratio=0.03,
        **get_training_precision(),
        logging_steps=10,
        save_steps=100,
        save_total_limit=2,
        # Evaluation configuration
        eval_strategy="epoch",  # Evaluate after each epoch
        eval_steps=1,  # How often to evaluate (in epochs)
        save_strategy="epoch",  # Save after each epoch
        load_best_model_at_end=True,  # Load best model at end
        metric_for_best_model="eval_accuracy",  # Use accuracy to determine best model
        greater_is_better=True,  # Higher accuracy is better
        # Training configuration
        gradient_checkpointing=False,  # Disable to avoid gradient issues
        dataloader_pin_memory=False,
        report_to="mlflow",
        remove_unused_columns=False,
    )

    # Data collator for sequence classification
    data_collator = DataCollatorWithPadding(
        tokenizer=tokenizer,
        padding='max_length',  # Specify explicit padding strategy
        max_length=v7_settings.max_length,
    )

    # Use standard Trainer with evaluation
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_train_dataset,
        eval_dataset=tokenized_eval_dataset,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
    )

    # Train the model
    logger.info("Starting training...")
    trainer.train()

    # Log final evaluation metrics to MLflow
    final_eval = trainer.evaluate()
    for key, value in final_eval.items():
        if key.startswith('eval_'):
            mlflow.log_metric(f"final_{key}", value)

    # Save the model
    logger.info(f"Saving model to {v7_settings.output_dir}")
    trainer.save_model()

    logger.info(f"Gemma3 fine-tuning completed. Model saved to {v7_settings.output_dir}")

    training_time = time.time() - start_time
    logger.info(f"Training completed in {training_time:.1f}s")
    mlflow.log_metric("training_time_seconds", training_time)
    
    return trainer.model, tokenizer

def show_training_info():
    v7_settings = ClassifierV7Settings()
    
    print(f"Model: {v7_settings.get_model_name()}")
    print("Method: HuggingFace LoRA fine-tuning")
    print(f"LoRA rank: {v7_settings.lora_r}, Alpha: {v7_settings.lora_alpha}")
    print(f"Learning rate: {v7_settings.learning_rate}, Epochs: {v7_settings.num_epochs}")
    print(f"QAT enabled: {v7_settings.use_qat_model}")
    print(f"Output: {v7_settings.output_dir}")
    
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
    elif torch.backends.mps.is_available():
        print("GPU: Metal Performance Shaders (MPS) on Mac")
    else:
        print("Device: CPU (training will be slow)")
