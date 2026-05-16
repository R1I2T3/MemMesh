import os
from typing import List, Dict, Any
from google import genai
from dotenv import load_dotenv

load_dotenv()

MODEL = "text-embedding-004"

def embed_chunks(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not chunks:
        return []

    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    
    try:
        # We can extract text from each chunk
        texts = [chunk["text"] for chunk in chunks]
        
        # Depending on how genai library allows batch embeddings. 
        # Usually client.models.embed_content accepts list of strings or single string
        # Let's fallback to embedding one by one if batch fails. But usually google.genai lists are fine.
        response = client.models.embed_content(
            model=MODEL,
            contents=texts,
        )
        
        # genai models embed_content response usually has a list of embeddings.
        for i, chunk in enumerate(chunks):
            chunk["embedding"] = response.embeddings[i].values
            
    except Exception as e:
        raise RuntimeError(f"Embedding failed: {e}") from e

    return chunks
