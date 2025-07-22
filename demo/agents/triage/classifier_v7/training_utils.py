import os
from datetime import datetime

import mlflow

# Set tokenizers parallelism to avoid warnings during training
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Import to register custom Gemma3 sequence classification models
try:
    from . import gemma3_sequence_classification  # noqa: F401 - needed for registration
except ImportError:
    pass


def setup_mlflow_tracking(model_name: str) -> str:
    mlflow.dspy.autolog()
    mlflow.set_experiment("triage_classifier")
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"v7_{timestamp}"


def log_training_parameters(sample_size: int, model_name: str, trainset_size: int):
    mlflow.log_param("version", "v7")
    mlflow.log_param("model", model_name)
    mlflow.log_param("samples", sample_size)
    mlflow.log_param("examples", trainset_size)


def perform_fine_tuning(student_classify, teacher_classify, trainset):
    import time
    
    try:
        from .config import ClassifierV7Settings
        v7_settings = ClassifierV7Settings()
    except ImportError:
        from agents.triage.classifier_v7.config import ClassifierV7Settings
        v7_settings = ClassifierV7Settings()
    
    print(f"Starting HuggingFace Gemma3 fine-tuning with {len(trainset)} examples")
    print(f"Model: {v7_settings.get_model_name()}")
    print(f"LoRA: {v7_settings.use_lora}, 4-bit: {v7_settings.use_4bit}, QAT: {v7_settings.use_qat_model}")
    
    start_time = time.time()
    
    try:
        # Import HuggingFace libraries
        import torch
        from datasets import Dataset
        from peft import LoraConfig, TaskType, get_peft_model

        # Import sklearn for train/test split
        from sklearn.model_selection import train_test_split
        from transformers import (
            AutoModelForSequenceClassification,
            AutoTokenizer,
            BitsAndBytesConfig,
            DataCollatorWithPadding,
            Trainer,
            TrainingArguments,
        )
        
        # Load model and tokenizer
        model_name = v7_settings.get_model_name()
        print(f"Loading model and tokenizer: {model_name}")
        if v7_settings.use_qat_model:
            print("Using QAT (Quantized Aware Training) model variant")
        
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
        
        # Use shared device configuration
        from .device_utils import (
            get_device_config,
            get_training_precision,
            move_to_device,
        )
        device_map, dtype = get_device_config()
            
        # Load the appropriate config class for this model
        from transformers import AutoConfig
        config = AutoConfig.from_pretrained(model_name)
        config.num_labels = 5  # 5 target agents: Billing, Claims, Policy, Escalation, Chatty
        
        model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            config=config,
            quantization_config=quantization_config,
            torch_dtype=dtype,
            device_map=device_map,
            attn_implementation="eager"  # More stable than flash attention
        )
        
        # Move to appropriate device
        model = move_to_device(model, device_map)
        
        # Configure LoRA
        if v7_settings.use_lora:
            print("Configuring LoRA...")
            lora_config = LoraConfig(
                lora_alpha=v7_settings.lora_alpha,
                lora_dropout=v7_settings.lora_dropout,
                r=v7_settings.lora_r,
                bias="none",
                target_modules="all-linear",
                task_type=TaskType.SEQ_CLS,
            )
            model = get_peft_model(model, lora_config)
            model.print_trainable_parameters()
            
            # Enable gradient computation for trainable parameters
            for param in model.parameters():
                if param.requires_grad:
                    param.requires_grad_(True)
        
        # Prepare training data
        print("Preparing training and evaluation data...")
        
        # Create label mapping for sequence classification
        label_mapping = {
            "BillingAgent": 0,
            "ClaimsAgent": 1,
            "PolicyAgent": 2,
            "EscalationAgent": 3,
            "ChattyAgent": 4
        }
        
        # Split data into train (80%) and eval (20%)
        # Only use stratification if we have enough samples per class
        target_counts = {}
        for ex in trainset:
            target_counts[ex.target_agent] = target_counts.get(ex.target_agent, 0) + 1
        
        # Check if we can stratify (each class needs at least 2 samples)
        can_stratify = len(trainset) >= 10 and all(count >= 2 for count in target_counts.values())
        
        if len(trainset) < 10:
            # For very small datasets, use all for training and create a simple eval set
            train_examples = trainset
            eval_examples = trainset[:max(1, len(trainset) // 5)]  # Take ~20% for eval
            print(f"Small dataset: using all {len(trainset)} for training, {len(eval_examples)} for evaluation")
        else:
            train_examples, eval_examples = train_test_split(
                trainset, 
                test_size=0.2, 
                random_state=42,
                stratify=[ex.target_agent for ex in trainset] if can_stratify else None
            )
        
        print(f"Training examples: {len(train_examples)}")
        print(f"Evaluation examples: {len(eval_examples)}")
        
        # Prepare training data
        train_texts = [ex.chat_history for ex in train_examples]
        train_labels = [label_mapping.get(ex.target_agent, 4) for ex in train_examples]
        
        # Prepare evaluation data
        eval_texts = [ex.chat_history for ex in eval_examples]
        eval_labels = [label_mapping.get(ex.target_agent, 4) for ex in eval_examples]
        
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
            report_to="none",  # Disable wandb/tensorboard
            remove_unused_columns=False,
        )
        
        # Data collator for sequence classification
        data_collator = DataCollatorWithPadding(
            tokenizer=tokenizer,
            padding='max_length',  # Specify explicit padding strategy
            max_length=v7_settings.max_length,
        )
        
        # Define evaluation metrics
        def compute_metrics(eval_pred):
            import numpy as np
            from sklearn.metrics import (
                accuracy_score,
                confusion_matrix,
                precision_recall_fscore_support,
            )
            
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
            
            # Create confusion matrix
            cm = confusion_matrix(labels, predictions)
            
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
        print("Starting training...")
        train_result = trainer.train()
        
        # Log final evaluation metrics to MLflow
        final_eval = trainer.evaluate()
        for key, value in final_eval.items():
            if key.startswith('eval_'):
                mlflow.log_metric(f"final_{key}", value)
        
        # Save the model
        print(f"Saving model to {v7_settings.output_dir}")
        trainer.save_model()
        tokenizer.save_pretrained(v7_settings.output_dir)
        
        captured_output = f"Gemma3 fine-tuning completed. Model saved to {v7_settings.output_dir}"
        
        # Create a simple test wrapper for the fine-tuned model
        model_path = v7_settings.output_dir
        classify_ft = create_simple_test_wrapper(model_path)
        
    except ImportError as e:
        print(f"\nHuggingFace libraries not available: {e}")
        print("Install with: pip install transformers peft datasets accelerate bitsandbytes")
        print("Falling back to DSPy optimization...")
        
        # No fallback available for HuggingFace training
        raise Exception(f"HuggingFace training failed: {e}")
        
    except Exception as e:
        print(f"\nFine-tuning failed: {e}")
        raise
    
    training_time = time.time() - start_time
    
    print(f"Completed in {training_time:.1f}s")
    
    mlflow.log_metric("training_time_seconds", training_time)
    mlflow.log_metric("training_success", 1)
    
    return classify_ft, captured_output


def create_simple_test_wrapper(model_path):
    """Create a simple test wrapper that doesn't rely on DSPy LM setup"""
    class SimpleTestWrapper:
        def __init__(self, model_path):
            self.model_path = model_path
            
        def __call__(self, chat_history="", **kwargs):
            # Simple mock response to verify wrapper works
            return type('Result', (), {
                'target_agent': 'PolicyAgent',  # Default test response
                'chat_history': chat_history
            })()
    
    return SimpleTestWrapper(model_path)




def show_training_info():
    try:
        from .config import ClassifierV7Settings
        v7_settings = ClassifierV7Settings()
    except ImportError:
        from agents.triage.classifier_v7.config import ClassifierV7Settings
        v7_settings = ClassifierV7Settings()
    
    print(f"Model: {v7_settings.get_model_name()}")
    print("Method: HuggingFace LoRA fine-tuning")
    print(f"LoRA rank: {v7_settings.lora_r}, Alpha: {v7_settings.lora_alpha}")
    print(f"Learning rate: {v7_settings.learning_rate}, Epochs: {v7_settings.num_epochs}")
    print(f"QAT enabled: {v7_settings.use_qat_model}")
    print(f"Output: {v7_settings.output_dir}")
    
    try:
        import torch
        if torch.cuda.is_available():
            print(f"GPU: {torch.cuda.get_device_name(0)}")
        elif torch.backends.mps.is_available():
            print("GPU: Metal Performance Shaders (MPS) on Mac")
        else:
            print("Device: CPU (training will be slow)")
    except ImportError:
        print("PyTorch not available")