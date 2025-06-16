import os

from libraries.logger import get_console_logger

logger = get_console_logger("policies_agent.rag")

def get_policy_content(policy: str):
    current_dir = os.path.dirname(__file__)
    policy_path = os.path.abspath(os.path.join(current_dir, "policies", policy + ".md"))
    with open(policy_path, "r") as f:
        return f.read()


if __name__ == "__main__":
    # Index building is now handled by the ingestion workflow
    pass
