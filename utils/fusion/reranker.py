from typing import List, Dict, Any
from sentence_transformers import CrossEncoder

class HybridRetriever:
    """
    Fuses results from Vector Search and Graph Search using a Cross-Encoder Reranker.
    """
    def __init__(self, model_name="cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.reranker = CrossEncoder(model_name)

    def rerank_results(self, query: str, graph_results: List[str], vector_results: List[str], top_k: int = 5) -> List[str]:
        """
        Takes top N graph relations and top M vector chunks,
        computes unified semantic relevance, and returns the top K.
        """
        all_results = list(dict.fromkeys(graph_results + vector_results))

        if not all_results:
            return []

        pairs = [[query, doc] for doc in all_results]

        scores = self.reranker.predict(pairs)

        scored_docs = sorted(zip(all_results, scores), key=lambda x: x[1], reverse=True)
        return [doc for doc, score in scored_docs][:top_k]
