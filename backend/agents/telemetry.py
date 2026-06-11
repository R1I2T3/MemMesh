from typing import Any, Dict, List
import json
import time

class TelemetryEvent:
    def __init__(self, stage: str, status: str, **kwargs):
        self.payload = {
            "type": "telemetry",
            "stage": stage,
            "status": status,
            "timestamp": time.time(),
            **kwargs
        }

    def to_sse(self) -> str:
        return f"data: {json.dumps(self.payload)}\n\n"

class TextChunkEvent:
    def __init__(self, content: str):
        self.payload = {"type": "text_chunk", "content": content}

    def to_sse(self) -> str:
        return f"data: {json.dumps(self.payload)}\n\n"

class CitationEvent:
    def __init__(self, source: str, doc_name: str = "", page: int = 0, url: str = "", triple: List[str] = None):
        payload = {"type": "citation", "source": source}
        if doc_name: payload["doc_name"] = doc_name
        if page: payload["page"] = page
        if url: payload["url"] = url
        if triple: payload["triple"] = triple
        self.payload = payload

    def to_sse(self) -> str:
        return f"data: {json.dumps(self.payload)}\n\n"

class SessionEvent:
    def __init__(self, session_id: str):
        self.payload = {"type": "session", "session_id": session_id}

    def to_sse(self) -> str:
        return f"data: {json.dumps(self.payload)}\n\n"

class DoneEvent:
    def to_sse(self) -> str:
        return "data: {\"type\": \"done\"}\n\n"

class ErrorEvent:
    def __init__(self, detail: str):
        self.payload = {"type": "error", "detail": detail}

    def to_sse(self) -> str:
        return f"data: {json.dumps(self.payload)}\n\n"
