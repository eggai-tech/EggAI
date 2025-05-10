"""
Simplified COPRO implementation for DSPy optimization.

This module provides a simplified COPRO (Counterfactually-augmented, Optimized Prompting) 
implementation that works with simpler LLMs that may not fully support structured outputs.
It's designed to be robust and maintain privacy protections while optimizing instructions.
"""
import json
import logging
import os
import traceback
from pathlib import Path
from typing import Any, Optional, Union

import dspy
from dspy.teleprompt import COPRO


class SimpleCOPRO(COPRO):
    """
    A simplified COPRO implementation that works with basic LLMs without full structured output.
    
    This implementation:
    1. Uses direct docstring updates instead of creating new module instances
    2. Maintains privacy protections and critical security features
    3. Has robust error handling and fallback mechanisms
    4. Provides a simplified JSON saving approach
    """
    
    def __init__(self, *args, logger=None, **kwargs):
        """
        Initialize SimpleCOPRO with logging support.
        
        Args:
            *args: Arguments to pass to COPRO
            logger: Optional logger instance (will create one if not provided)
            **kwargs: Keyword arguments to pass to COPRO
        """
        super().__init__(*args, **kwargs)
        self.logger = logger or logging.getLogger("simple_copro")
        self.logger.info("Initialized SimpleCOPRO for basic LLMs")
        
    def compile(self, module, trainset, **kwargs):
        """
        Custom compile method that handles simpler LLM outputs.
        
        This method:
        1. Gets original instructions from the module
        2. Generates improved instructions
        3. Updates the module's docstring directly
        4. Has fallback mechanisms when direct updates fail
        
        Args:
            module: DSPy module to optimize
            trainset: Training examples
            **kwargs: Additional arguments
            
        Returns:
            Updated module with optimized instructions
        """
        self.logger.info("Using simplified COPRO compilation process")
        
        # Instead of using COPRO's complex mechanism, we'll use a simpler approach
        # that directly enhances the prompt based on examples
        try:
            # Store the original module state in case we need to revert
            original_module = module
            
            # Get the original instructions
            original_instructions = None
            if hasattr(module, 'signature') and hasattr(module.signature, '__doc__'):
                original_instructions = module.signature.__doc__
                self.logger.info(f"Original docstring length: {len(original_instructions) if original_instructions else 0}")
            else:
                self.logger.warning("Could not get original instructions from module signature")
                return module  # Return original module if we can't get instructions
            
            # Generate improved instructions
            critical_text = kwargs.get('critical_text', None)
            improved = self._generate_improved_instructions(
                original_instructions, 
                trainset,
                critical_text=critical_text
            )
            
            # For this customized version, we'll skip creating a whole new program instance
            # and just update the signature docstring of the existing program
            try:
                self.logger.info("Creating optimized module by updating docstring")
                if hasattr(module, 'signature') and hasattr(module.signature, '__doc__'):
                    # Store the original docstring in case we need to revert
                    original_docstring = module.signature.__doc__
                    
                    # Update the module's signature docstring directly
                    module.signature.__doc__ = improved
                    self.logger.info("Successfully updated module's signature docstring")
                    
                    # Return the same module but with updated docstring
                    return module
            except Exception as update_error:
                self.logger.error(f"Error updating module docstring: {update_error}")
                self.logger.error(f"Update docstring traceback: {traceback.format_exc()}")
                
                # If direct update fails, fall back to the original approach
                try:
                    self.logger.info("Falling back to creating new signature class")
                    SignatureClass = module.signature.__class__
                    
                    class EnhancedSignature(SignatureClass):
                        """Enhanced signature with improved instructions."""
                        # We'll add a save method to make it compatible with COPRO's expectations
                        @classmethod
                        def save(cls, path):
                            """Save the signature to a JSON file."""
                            data = {
                                "instructions": cls.__doc__,
                                "fields": []
                            }
                            with open(path, 'w') as f:
                                json.dump(data, f, indent=2)
                    
                    # Set the docstring to our improved instructions
                    EnhancedSignature.__doc__ = improved
                    
                    # Create a new module with the enhanced signature
                    enhanced_module = module.deepcopy()
                    enhanced_module.signature = EnhancedSignature
                    
                    self.logger.info("Successfully created enhanced module with new signature class")
                    return enhanced_module
                except Exception as fallback_error:
                    self.logger.error(f"Fallback approach also failed: {fallback_error}")
                    self.logger.error(f"Fallback traceback: {traceback.format_exc()}")
                    
                    # Return the original module if both approaches fail
                    return original_module
            
        except Exception as e:
            self.logger.error(f"Error in simplified COPRO compilation: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            # Return the original module on error
            return module
    
    def _generate_improved_instructions(self, original_instructions, examples, critical_text=None):
        """
        Generate improved instructions directly with the LLM.
        
        Args:
            original_instructions: Original instructions to improve
            examples: Training examples for context
            critical_text: Optional critical text that must be preserved in the output
                          (e.g. privacy protection statements)
        
        Returns:
            Improved instructions
        """
        self.logger.info("Generating improved instructions...")
        
        # Guard against None instructions
        if not original_instructions:
            self.logger.error("Original instructions are None or empty")
            return original_instructions
        
        # Take a sample of examples to use as context
        if len(examples) > 2:
            context_examples = examples[:2]
        else:
            context_examples = examples
        
        example_texts = []
        for i, example in enumerate(context_examples):
            try:
                if hasattr(example, 'get') and callable(example.get):
                    example_text = f"Example {i+1}:\nInput: {example.get('chat_history', '')}"
                else:
                    # Handle different example formats
                    chat_history = None
                    for attr_name in ['chat_history', 'conversation', 'input', 'query']:
                        if hasattr(example, attr_name):
                            chat_history = getattr(example, attr_name)
                            break
                    
                    if chat_history:
                        example_text = f"Example {i+1}:\nInput: {chat_history}"
                    else:
                        example_text = f"Example {i+1}:\nInput: {str(example)[:200]}"
                
                example_texts.append(example_text)
            except Exception as ex:
                self.logger.warning(f"Error processing example {i}: {ex}")
                continue
        
        examples_context = "\n\n".join(example_texts)
        
        # Determine critical privacy text
        if not critical_text:
            # Try to auto-detect critical text
            self.logger.info("No critical text provided - attempting to auto-detect")
            privacy_keywords = [
                "NEVER reveal", 
                "privacy", 
                "EXPLICIT", 
                "authentication",
                "policy number",
                "claim number",
                "confidential",
                "personally identifiable"
            ]
            
            critical_sentences = []
            for line in original_instructions.split('\n'):
                for keyword in privacy_keywords:
                    if keyword.lower() in line.lower():
                        critical_sentences.append(line.strip())
                        break
            
            if critical_sentences:
                critical_text = "\n".join(critical_sentences)
                self.logger.info(f"Auto-detected critical text: {critical_text[:50]}...")
            else:
                self.logger.warning("Could not auto-detect critical text")
                critical_text = "Important privacy protections"
        
        # Prepare optimization prompt for basic LLMs with stronger privacy emphasis
        optimization_prompt = f"""You are an expert prompt engineer. Your task is to improve these instructions for a large language model.

ORIGINAL INSTRUCTIONS:
{original_instructions}

EXAMPLES OF CONVERSATIONS THE MODEL SHOULD HANDLE:
{examples_context}

Please create an improved version of these instructions that:
1. Maintains all the privacy protections in the original
2. Clarifies any ambiguous parts
3. Makes the instructions more effective
4. Keeps the same overall structure and intent
5. IMPORTANT: Do not remove any of the security features that prevent revealing data without proper authentication

CRITICAL REQUIREMENT: You MUST preserve ALL privacy and security protections from the original instructions. 
Specifically, you MUST include the following critical text in your improved instructions:
"{critical_text}"

Use the format and structure of the original instructions as a guide. Make sure all of the original privacy protections
and security checks are preserved in your improved version.

IMPROVED INSTRUCTIONS:
"""
        
        # Use the LLM directly to generate improved instructions
        from dspy.predict import Predict
        
        class InstructionImprover(dspy.Signature):
            """Improve instruction prompts for better performance."""
            context = dspy.InputField(desc="Original instructions and examples")
            improved_instructions = dspy.OutputField(desc="Improved instructions that maintain all privacy protections")
        
        improver = Predict(InstructionImprover)
        
        # Generate improved instructions
        try:
            self.logger.info("Calling LLM to generate improved instructions")
            result = improver(context=optimization_prompt)
            
            if hasattr(result, 'improved_instructions') and result.improved_instructions:
                improved = result.improved_instructions
                self.logger.info(f"Successfully generated improved instructions (length: {len(improved)})")
                
                # Check for critical privacy text if provided
                if critical_text and critical_text not in improved:
                    self.logger.warning("Critical privacy text missing - restoring from original")
                    improved = original_instructions
                
                return improved
            else:
                self.logger.warning("No improved instructions generated")
                return original_instructions
        except Exception as e:
            self.logger.error(f"Error generating improved instructions: {e}")
            self.logger.error(f"Instruction generation traceback: {traceback.format_exc()}")
            return original_instructions


def save_optimized_instructions(
    path: Union[str, Path], 
    instructions: str, 
    fallback_instructions: Optional[str] = None,
    logger = None
) -> bool:
    """
    Save optimized instructions to a JSON file with fallback mechanisms.
    
    Args:
        path: Path to save the instructions to
        instructions: Instructions to save
        fallback_instructions: Fallback instructions to use if the primary ones fail
        logger: Optional logger instance
    
    Returns:
        True if successful, False otherwise
    """
    logger = logger or logging.getLogger("dspy_copro")
    path = Path(path) if isinstance(path, str) else path
    
    # Save the instructions
    if instructions:
        try:
            # Create a simple data structure with the instructions
            signature_data = {
                "instructions": instructions,
                "fields": []
            }
            
            # Save as JSON
            with open(str(path), 'w') as f:
                json.dump(signature_data, f, indent=2)
                
            logger.info(f"✅ Successfully saved optimized instructions to {path}")
            return True
        except Exception as save_error:
            logger.error(f"❌ Error saving optimized instructions: {save_error}")
            
            # Create fallback file to prevent loading errors
            try:
                # Use fallback instructions if provided
                instructions_to_save = fallback_instructions if fallback_instructions else instructions
                
                # Use a simpler approach for the fallback
                fallback_data = {
                    "instructions": instructions_to_save,
                    "fields": []
                }
                
                with open(str(path), 'w') as f:
                    json.dump(fallback_data, f, indent=2)
                
                logger.info(f"✅ Created fallback file with available instructions at {path}")
                return True
            except Exception as fallback_error:
                logger.error(f"❌ Even fallback save failed: {fallback_error}")
                return False
    else:
        # If we can't get any instructions, log an error
        logger.error("❌ Could not find any instructions to save")
        
        # Create an emergency fallback
        try:
            # Create a minimal valid JSON file
            emergency_data = {
                "instructions": "You are an assistant. Maintain user privacy at all times.",
                "fields": []
            }
            
            with open(str(path), 'w') as f:
                json.dump(emergency_data, f, indent=2)
            
            logger.info(f"✅ Created emergency fallback file at {path}")
            return True
        except Exception as emergency_error:
            logger.error(f"❌ Emergency fallback failed: {emergency_error}")
            return False


def save_and_log_optimized_instructions(
    path: Union[str, Path],
    optimized_program: Any,
    original_program: Any = None,
    logger = None,
    mlflow = None
) -> bool:
    """
    Save optimized instructions to a JSON file and log to MLflow.
    
    Args:
        path: Path to save the instructions to
        optimized_program: Optimized program with instructions
        original_program: Original program (used as fallback)
        logger: Optional logger instance
        mlflow: Optional mlflow module
    
    Returns:
        True if successful, False otherwise
    """
    logger = logger or logging.getLogger("dspy_copro")
    
    # Get instructions from the optimized program if possible
    instructions_to_save = None
    if hasattr(optimized_program, 'signature') and hasattr(optimized_program.signature, '__doc__'):
        instructions_to_save = optimized_program.signature.__doc__
    else:
        # Fallback to original instructions
        logger.warning("Could not extract instructions from optimized program")
        if original_program and hasattr(original_program, 'signature') and hasattr(original_program.signature, '__doc__'):
            instructions_to_save = original_program.signature.__doc__
    
    # Save the instructions
    save_successful = save_optimized_instructions(
        path,
        instructions_to_save,
        fallback_instructions=original_program.signature.__doc__ if original_program else None,
        logger=logger
    )
    
    # Log to MLflow if available
    if save_successful and mlflow and os.path.exists(str(path)):
        try:
            mlflow.log_artifact(str(path))
            logger.info("✅ Artifacts logged successfully to MLflow")
            return True
        except Exception as mlflow_error:
            logger.error(f"❌ Error logging artifacts to MLflow: {mlflow_error}")
            return False
    elif not os.path.exists(str(path)):
        logger.error(f"❌ Cannot log artifact to MLflow: File {path} does not exist")
        return False
    
    return save_successful