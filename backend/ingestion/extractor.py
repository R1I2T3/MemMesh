import re
import json
import logging

from backend.config import settings

logger = logging.getLogger(__name__)

def extract_heuristic(text: str) -> tuple[list[dict], list[dict]]:
    # Extract capitalized terms as potential entity names
    pattern = re.compile(r'\b[A-Z][a-zA-Z0-9_]{1,30}(?:\s+[A-Z][a-zA-Z0-9_]{1,30})*\b')
    matches = pattern.findall(text)
    stop_words = {"The", "A", "An", "This", "That", "These", "Those", "It", "They", "We", "I"}
    entities = []
    seen_ids = set()
    for match in matches:
        cleaned = match.strip()
        if cleaned in stop_words or len(cleaned) < 2:
            continue
        entity_id = re.sub(r'[^a-zA-Z0-9_]', '_', cleaned.lower())
        if entity_id not in seen_ids:
            seen_ids.add(entity_id)
            entities.append({"id": entity_id, "name": cleaned, "type": "Concept"})
    # Do NOT generate false relationships — return empty relations list
    return entities, []

def extract_entities_and_relationships(text: str) -> tuple[list[dict], list[dict]]:
    api_key = settings.GEMINI_API_KEY
    if not api_key or "placeholder" in api_key.lower() or api_key in ("mock", "test"):
        logger.info("Using heuristic extraction (Gemini API key missing/mock)")
        return extract_heuristic(text)

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        # Initialize LLM with Gemini
        llm = ChatGoogleGenerativeAI(model=settings.GEMINI_MODEL, google_api_key=api_key)
        prompt = (
            "Extract entities and relations from the following text.\n"
            "Respond ONLY with a valid JSON block containing "
            "'entities': [{'id': string, 'name': string, 'type': string}] and "
            "'relationships': [{'source_id': string, 'target_id': string, 'type': string}].\n\n"
            f"Text: {text}"
        )
        response = llm.invoke(prompt)
        content = response.content.strip()
        
        # Strip markdown code blocks if any
        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join(lines[1:-1])
                
        data = json.loads(content)
        return data.get("entities", []), data.get("relationships", [])
    except Exception as e:
        logger.warning("Gemini extraction failed: %s. Falling back to heuristic.", e)
        return extract_heuristic(text)
