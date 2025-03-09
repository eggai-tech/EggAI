import os
from ragatouille import RAGPretrainedModel
from agents.tracing import trace_function, create_tracer

from agents.policies.rag.indexing import ensure_index_built

tracer = create_tracer("policies_agent", "rag")

_INDEX_LOADED = False
_RAG = None


@trace_function(
    func=lambda query, category=None: None,  # Placeholder for type signature
    name="retrieve_policies",
    tracer=tracer
)
def retrieve_policies(query, category=None):
    global _INDEX_LOADED, _RAG

    ensure_index_built()

    if not _INDEX_LOADED:
        index_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".ragatouille"))
        index_path = os.path.abspath(os.path.join(index_root, "colbert", "indexes", "policies_index"))
        _RAG = RAGPretrainedModel.from_index(index_path)

    results = _RAG.search(query, index_name="policies_index")
    if category:
        return [r for r in results if r["document_metadata"]["category"] == category]
    return results

if __name__ == "__main__":
    res = retrieve_policies("Is Fire Damage Coverage included?")
    print(res)

