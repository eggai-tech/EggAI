import os


def save_model_id_to_env(model_id: str) -> bool:
    """Save model ID to environment file"""
    try:
        env_file = ".env"
        env_var = f"TRIAGE_CLASSIFIER_V7_MODEL_ID={model_id}"
        
        existing_content = []
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                existing_content = f.readlines()
        
        filtered_content = [line for line in existing_content 
                          if not line.startswith("TRIAGE_CLASSIFIER_V7_MODEL_ID=")]
        
        filtered_content.append(f"{env_var}\n")
        
        with open(env_file, 'w') as f:
            f.writelines(filtered_content)
        
        print(f"Saved to {env_file}")
        return True
        
    except Exception as e:
        print(f"Save failed: {e}")
        return False