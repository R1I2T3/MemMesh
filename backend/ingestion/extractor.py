import re
import json
import logging

from backend.config import settings

logger = logging.getLogger(__name__)

def extract_heuristic(text: str) -> tuple[list[dict], list[dict]]:
    # Find word groups starting with capitalized letters
    pattern = re.compile(r'\b[A-Z][a-zA-Z0-9_]{1,30}(?:\s+[A-Z][a-zA-Z0-9_]{1,30})*\b')
    matches = pattern.findall(text)
    
    stop_words = {
        "The", "A", "An", "This", "That", "These", "Those", "It", "They", "We", "I", "You",
        "He", "She", "In", "On", "At", "By", "For", "To", "With", "About", "Against", "Between",
        "Into", "Through", "During", "Before", "After", "Above", "Below", "To", "From", "Up",
        "Down", "In", "Out", "Off", "Over", "Under", "Again", "Further", "Then", "Once", "Here",
        "There", "When", "Where", "Why", "How", "All", "Any", "Both", "Each", "Few", "More",
        "Most", "Other", "Some", "Such", "No", "Nor", "Not", "Only", "Own", "Same", "So", "Than",
        "Too", "Very", "S", "T", "Can", "Will", "Just", "Don", "Should", "Now"
    }
    
    entities = []
    seen_ids = set()
    for match in matches:
        match_cleaned = match.strip()
        if match_cleaned in stop_words or len(match_cleaned) < 2:
            continue
        entity_id = re.sub(r'[^a-zA-Z0-9_]', '_', match_cleaned.lower())
        if entity_id not in seen_ids:
            seen_ids.add(entity_id)
            entities.append({
                "id": entity_id,
                "name": match_cleaned,
                "type": "Concept"
            })
            
    relationships = []
    for i in range(len(entities) - 1):
        relationships.append({
            "source_id": entities[i]["id"],
            "target_id": entities[i+1]["id"],
            "type": "RELATES_TO"
        })
        
    return entities, relationships

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
            if lines[0].startswith("```json"):
                content = "\n".join(lines[1:-1])
            else:
                content = "\n".join(lines[1:-1])
                
        data = json.loads(content)
        return data.get("entities", []), data.get("relationships", [])
    except Exception as e:
        logger.warning("Gemini extraction failed: %s. Falling back to heuristic.", e)
        return extract_heuristic(text)
