#!/usr/bin/env python3
import logging
import os

from agents.triage.baseline_model.utils import setup_logging
from agents.triage.classifier_v7.classifier_v7 import FinetunedClassifier
from agents.triage.data_sets.loader import AGENT_TO_LABEL
from agents.triage.shared.data_utils import create_examples

# Set tokenizers parallelism to avoid warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import mlflow
import torch
from dotenv import load_dotenv

from agents.triage.classifier_v7.config import ClassifierV7Settings
from agents.triage.classifier_v7.training_utils import (
    log_training_parameters,
    perform_fine_tuning,
    setup_mlflow_tracking,
    show_training_info,
)

load_dotenv()
v7_settings = ClassifierV7Settings()

os.environ["DSPY_CACHEDIR"] = "./dspy_cache"
logger = logging.getLogger(__name__)


def train_finetune_model(sample_size: int, model_name: str) -> str:
    run_name = setup_mlflow_tracking(model_name)
    
    with mlflow.start_run(run_name=run_name):
        # Verify we're in the correct experiment
        current_exp = mlflow.get_experiment(mlflow.active_run().info.experiment_id)
        logger.info(f"Active experiment: {current_exp.name} (ID: {current_exp.experiment_id})")
        
        trainset = create_examples(sample_size, phase="train")
        logger.info(f"Loaded {len(trainset)} training examples")
        # load test set for evaluation (configurable size)
        eval_sample_size = int(os.getenv("EVALUATION_SAMPLE_SIZE", "-1"))
        testset = create_examples(eval_sample_size, phase="test")
        logger.info(f"Loaded {len(testset)} test examples")

        log_training_parameters(sample_size, eval_sample_size, model_name, len(trainset), len(testset))
        
        if not model_name:
            model_name = v7_settings.get_model_name()

        logger.info(f"Using base model: {model_name}")

        logger.info("Starting fine-tuning with debugging enabled...")
        
        model, tokenizer = perform_fine_tuning(trainset, testset)
        
        # Get classifier weights after training
        if hasattr(model, 'classifier'):
            post_training_cls_weights = model.classifier.weight.data.clone()
            logger.info(f"Post-training classifier weights shape: {post_training_cls_weights.shape}")
        elif hasattr(model, 'base_model') and hasattr(model.base_model, 'classifier'):
            post_training_cls_weights = model.base_model.classifier.weight.data.clone()
            logger.info(f"Post-training base_model classifier weights shape: {post_training_cls_weights.shape}")
        else:
            post_training_cls_weights = None
            logger.warning("Could not find classifier weights after training")
        
        # Save the fine-tuned PEFT model to mlflow with both approaches
        # First approach: Save artifacts from output directory
        mlflow.log_artifacts(v7_settings.output_dir, artifact_path="model")
        
        # Second approach: Test model loading and create comprehensive artifacts
        import tempfile
        
        with tempfile.TemporaryDirectory() as temp_model_dir:
            # Save the PEFT model locally first
            logger.info(f"Saving PEFT model to {temp_model_dir}")
            
            # Check if we need to save classifier weights explicitly
            if hasattr(model, 'modules_to_save') and 'classifier' in model.modules_to_save:
                logger.info("Found classifier in modules_to_save - should save classifier weights")
            else:
                logger.warning("Classifier not found in modules_to_save - this could be the issue")
                
            # Check the actual structure before saving
            logger.info(f"Model type: {type(model)}")
            if hasattr(model, 'base_model'):
                logger.info(f"Base model type: {type(model.base_model)}")
                if hasattr(model.base_model, 'model'):
                    logger.info(f"Base model.model type: {type(model.base_model.model)}")
            
            # Try to save the model with explicit state dict preservation
            try:
                model.save_pretrained(temp_model_dir)
                
                # Also explicitly save the classifier state if it exists
                if hasattr(model, 'classifier'):
                    classifier_state_path = os.path.join(temp_model_dir, 'classifier_state.pt')
                    torch.save(model.classifier.state_dict(), classifier_state_path)
                    logger.info(f"Explicitly saved classifier state to {classifier_state_path}")
                elif hasattr(model, 'base_model') and hasattr(model.base_model, 'classifier'):
                    classifier_state_path = os.path.join(temp_model_dir, 'classifier_state.pt')
                    torch.save(model.base_model.classifier.state_dict(), classifier_state_path)
                    logger.info(f"Explicitly saved base_model classifier state to {classifier_state_path}")
                    
            except Exception as e:
                logger.error(f"Error saving PEFT model: {e}")
                
            tokenizer.save_pretrained(temp_model_dir)
            
            # Debug: Check if adapter files are created
            files_created = os.listdir(temp_model_dir)
            logger.info(f"Files created in temp directory: {files_created}")
            
            # Log the entire directory as artifacts
            mlflow.log_artifacts(temp_model_dir, artifact_path="model_peft")

            # Test the model loading within the same MLflow run context
            logger.info("Testing model loading from artifacts...")
            try:
                # Test loading the PEFT model from the saved artifacts
                from transformers import AutoTokenizer
                base_model_name = v7_settings.get_model_name()
                test_tokenizer = AutoTokenizer.from_pretrained(base_model_name)
                if test_tokenizer.pad_token is None:
                    test_tokenizer.pad_token = test_tokenizer.eos_token
                    
                from agents.triage.classifier_v7.gemma3_wrapper import (
                    Gemma3TextForSequenceClassification,
                )
                base_model = Gemma3TextForSequenceClassification.from_pretrained(
                    base_model_name,
                    num_labels=len(AGENT_TO_LABEL),
                    torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
                    attn_implementation="eager"
                )
                base_cls_weights = base_model.classifier.weight.data
                
                from peft import PeftModel
                test_model = PeftModel.from_pretrained(base_model, temp_model_dir)
                
                # WORKAROUND: Manually load the classifier state since PEFT isn't doing it correctly
                classifier_state_path = os.path.join(temp_model_dir, 'classifier_state.pt')
                if os.path.exists(classifier_state_path):
                    logger.info("Loading classifier state manually from explicit save...")
                    classifier_state = torch.load(classifier_state_path, map_location='cpu')
                    logger.info(f"Loaded classifier state keys: {list(classifier_state.keys())}")
                    
                    # Try different approaches to load the classifier state
                    try:
                        if hasattr(test_model.classifier, 'modules_to_save') and 'default' in test_model.classifier.modules_to_save:
                            test_model.classifier.modules_to_save['default'].load_state_dict(classifier_state)
                            logger.info("Loaded classifier state into modules_to_save['default']")
                        elif hasattr(test_model.classifier, 'original_module'):
                            test_model.classifier.original_module.load_state_dict(classifier_state)
                            logger.info("Loaded classifier state into original_module")
                        else:
                            test_model.classifier.load_state_dict(classifier_state)
                            logger.info("Loaded classifier state into classifier directly")
                    except Exception as e:
                        logger.warning(f"Failed to load classifier state: {e}. Trying weight assignment...")
                        # Direct weight assignment as last resort
                        if 'weight' in classifier_state:
                            if hasattr(test_model.classifier, 'weight'):
                                test_model.classifier.weight.data = classifier_state['weight']
                                logger.info("Directly assigned classifier weight")
                            elif hasattr(test_model.classifier, 'original_module') and hasattr(test_model.classifier.original_module, 'weight'):
                                test_model.classifier.original_module.weight.data = classifier_state['weight']
                                logger.info("Directly assigned original_module weight")
                
                # Debug: Check the structure of the loaded model
                logger.info(f"Loaded test_model type: {type(test_model)}")
                logger.info(f"Loaded test_model has classifier: {hasattr(test_model, 'classifier')}")
                if hasattr(test_model, 'classifier'):
                    logger.info(f"test_model.classifier type: {type(test_model.classifier)}")
                    logger.info(f"test_model.classifier has original_module: {hasattr(test_model.classifier, 'original_module')}")
                
                # Try to get the classifier weights from the loaded model
                try:
                    # After manual loading, check the actual classifier weights (not original_module)
                    if hasattr(test_model.classifier, 'weight'):
                        peft_cls_weight = test_model.classifier.weight.data  
                        logger.info("Using test_model.classifier.weight.data (manually loaded)")
                    elif hasattr(test_model.classifier, 'original_module'):
                        peft_cls_weight = test_model.classifier.original_module.weight.data
                        logger.info("Using test_model.classifier.original_module.weight.data (PEFT default)")
                    else:
                        logger.error("Cannot find classifier weights in loaded PEFT model")
                        peft_cls_weight = None
                        
                    if peft_cls_weight is not None:
                        # compare base_model.classifier weights with test_model.classifier weights
                        if torch.allclose(base_cls_weights, peft_cls_weight, atol=1e-5):
                            logger.warning("Base model classifier weights match PEFT classifier weights. Something is wrong!")
                            logger.warning("This indicates the classifier weights were not properly saved or loaded from the PEFT adapter")
                        else:
                            logger.info("Base model classifier weights differ from PEFT classifier weights. Model loaded successfully.")
                            
                except Exception as e:
                    logger.error(f"Error comparing classifier weights: {e}")
                
                # Create classifier and test
                test_classifier = FinetunedClassifier(model=test_model, tokenizer=test_tokenizer)
                test_result = test_classifier.classify("User: I want to know my policy due date.")
                logger.info(f"✅ Model test successful: {test_result.target_agent}")
                
            except Exception as e:
                logger.warning(f"Model test failed: {e}")

        # Return model uri from the primary artifacts
        run_id = mlflow.active_run().info.run_id
        model_uri = f"runs:/{run_id}/model"
        logger.info(f"Model URI: {model_uri}")
        return model_uri


if __name__ == "__main__":
    setup_logging()
    sample_size = int(os.getenv("FINETUNE_SAMPLE_SIZE", "-1"))
    eval_sample_size = int(os.getenv("EVALUATION_SAMPLE_SIZE", "-1"))
    logger.info(f"Training sample size: {sample_size}, Evaluation sample size: {eval_sample_size}")
    model_name = os.getenv("FINETUNE_BASE_MODEL", None)
    if model_name is None:
        model_name = v7_settings.get_model_name()
    show_training_info()
    
    model_uri = train_finetune_model(sample_size, model_name)
    logger.info(f"Fine-tuned model saved to mlflow. URI: {model_uri}")
    logger.info("Training and MLflow logging completed successfully!")

