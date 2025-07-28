
import os
import re
from typing import Optional


def extract_model_id_from_dspy(classify_ft) -> Optional[str]:
    try:
        if hasattr(classify_ft, 'lm') and hasattr(classify_ft.lm, 'model'):
            model_name = classify_ft.lm.model
            if model_name.startswith('ft:'):
                return model_name
        
        if hasattr(classify_ft, 'lm'):
            lm = classify_ft.lm
            if hasattr(lm, 'kwargs') and 'model' in lm.kwargs:
                model_name = lm.kwargs['model']
                if model_name.startswith('ft:'):
                    return model_name
                    
        return None
    except Exception:
        return None


def parse_model_id_from_output(captured_output: str) -> Optional[str]:
    try:
        # Look for: "Model retrieved: ft:model-id"
        pattern = r'Model retrieved:\s+(ft:[\w-]+:[\w-]+::[\w]+)'
        match = re.search(pattern, captured_output)
        if match:
            return match.group(1)
        
        # Alternative: any ft: model ID
        pattern = r'(ft:gpt-4o-mini-2024-07-18:[\w-]+::[\w]+)'
        match = re.search(pattern, captured_output)
        if match:
            return match.group(1)
            
        return None
    except Exception:
        return None


def save_model_id_to_env(model_id: str) -> bool:
    try:
        env_file = ".env"
        env_var = f"TRIAGE_CLASSIFIER_V6_MODEL_ID={model_id}"
        
        existing_content = []
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                existing_content = f.readlines()
        
        filtered_content = [line for line in existing_content 
                          if not line.startswith("TRIAGE_CLASSIFIER_V6_MODEL_ID=")]
        
        filtered_content.append(f"{env_var}\n")
        
        with open(env_file, 'w') as f:
            f.writelines(filtered_content)
        
        print(f"Saved to {env_file}")
        return True
        
    except Exception as e:
        print(f"Save failed: {e}")
        return False