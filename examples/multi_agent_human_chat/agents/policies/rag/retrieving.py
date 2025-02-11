import os

from ragatouille import RAGPretrainedModel

from agents.policies.rag.indexing import ensure_index_built

_INDEX_LOADED = False
_RAG = None


def retrieve_policies(query, category=None):
    global _INDEX_LOADED, _RAG

    ensure_index_built()

    if not _INDEX_LOADED:
        current_dir = os.path.dirname(__file__)
        index_path = os.path.abspath(os.path.join(current_dir, ".ragatouille", "colbert", "indexes", "policies_index"))
        _RAG = RAGPretrainedModel.from_index(index_path)

    results = _RAG.search(query, index_name="policies_index")
    if category:
        return [r for r in results if r["document_metadata"]["category"] == category]
    return results

if __name__ == "__main__":
    res = retrieve_policies("Is Fire Damage Coverage included?")
    print(res)

