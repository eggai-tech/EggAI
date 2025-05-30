import os

from ragatouille import RAGPretrainedModel

from libraries.logger import get_console_logger

logger = get_console_logger("policies_agent.rag")

_INDEX_BUILT = False


def get_policy_content(policy: str):
    current_dir = os.path.dirname(__file__)
    policy_path = os.path.abspath(os.path.join(current_dir, "policies", policy + ".md"))
    with open(policy_path, "r") as f:
        return f.read()


def ensure_index_built():
    global _INDEX_BUILT
    if _INDEX_BUILT:
        return
    index_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), ".ragatouille")
    )
    index_path = os.path.abspath(
        os.path.join(index_root, "colbert", "indexes", "policies_index")
    )

    if not os.path.exists(index_path):
        r = RAGPretrainedModel.from_pretrained(
            "colbert-ir/colbertv2.0", index_root=index_root
        )
        policies_ids = ["health", "auto", "home", "life"]
        document_metadata = [
            {
                "category": policy_id,
                "type": "policy",
            }
            for policy_id in policies_ids
        ]
        my_policies_content = [
            get_policy_content(policy_id) for policy_id in policies_ids
        ]
        r.index(
            index_name="policies_index",
            collection=my_policies_content,
            document_ids=policies_ids,
            document_metadatas=document_metadata,
        )
    else:
        logger.info("Index already BUILT")
    _INDEX_BUILT = True


if __name__ == "__main__":
    ensure_index_built()
