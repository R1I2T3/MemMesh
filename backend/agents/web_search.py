import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def web_search_fallback(state: Dict[str, Any]) -> Dict[str, Any]:
    # Determine the query to use for search
    search_query = state["rewritten_queries"][0] if state.get("rewritten_queries") else state["query"]

    # Mock web search for hermetic tests / offline mode
    if os.environ.get("MOCK_LLM") == "true":
        return {
            "web_search_results": [{
                "text": f"Mock web search result for query: {search_query}",
                "source": "web",
                "url": f"https://html.duckduckgo.com/html/?q={search_query}",
                "score": 0.8
            }]
        }

    try:
        from langchain_community.tools import DuckDuckGoSearchRun
        search = DuckDuckGoSearchRun()
        web_raw = search.run(search_query)
        
        web_chunks = [{
            "text": web_raw,
            "source": "web",
            "url": f"https://html.duckduckgo.com/html/?q={search_query}",
            "score": 0.8
        }]
        return {"web_search_results": web_chunks}
    except Exception as e:
        logger.exception("DuckDuckGo web search failed.")
        return {
            "web_search_results": [{
                "text": f"Web search failed: {e}",
                "source": "web",
                "url": f"https://html.duckduckgo.com/html/?q={search_query}",
                "score": 0.0
            }]
        }
