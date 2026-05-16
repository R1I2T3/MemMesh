import re

class QueryRouter:
    """
    Dynamic Query Routing to decide whether to hit Vector, Graph, or Both.
    """

    @staticmethod
    def classify_query(query: str) -> str:
        """
        Classifies the query.
        Returns: 'graph', 'vector', or 'hybrid'
        """
        lower_query = query.lower()

        # Heuristics for Graph (Relationships, Connectivity, "who", "relates to")
        graph_keywords = ['relationship', 'connect', 'who is', 'related to', 'network', 'depends on']

        # Heuristics for Vector (Semantic similarity, "what did we talk about", "summarize")
        vector_keywords = ['what did we talk about', 'summarize', 'details about', 'explain', 'concept']

        graph_score = sum(1 for kw in graph_keywords if kw in lower_query)
        vector_score = sum(1 for kw in vector_keywords if kw in lower_query)

        routing = 'hybrid' # Default

        if graph_score > vector_score and graph_score > 0:
            routing = 'graph'
        elif vector_score > graph_score and vector_score > 0:
            routing = 'vector'

        return routing
