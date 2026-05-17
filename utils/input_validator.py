import re
from fastapi import HTTPException

MAX_QUERY_LENGTH = 5000

INJECTION_PATTERNS = [
    r"ignore\s+(previous\s+)?instructions",
    r"ignore\s+above",
    r"disregard\s+(previous\s+)?instructions",
    r"<system>",
    r"</system>",
    r"system\s*:",
    r"you\s+are\s+now",
    r"pretend\s+you\s+are",
    r"act\s+as",
    r"output\s+your\s+prompt",
    r"repeat\s+the\s+instructions",
    r"show\s+your\s+system",
]

PII_PATTERNS = [
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
    r"\b\d{3}-\d{2}-\d{4}\b",
    r"\b(?:\d{4}[-\s]?){3}\d{1,4}\b",
    r"\b\d{13,19}\b",
]

_injection_re = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)
_pii_re = re.compile("|".join(PII_PATTERNS))


def validate_query(text: str) -> str:
    if len(text) > MAX_QUERY_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Query exceeds maximum length of {MAX_QUERY_LENGTH} characters",
        )

    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)

    if _injection_re.search(text):
        raise HTTPException(
            status_code=400,
            detail="Query contains disallowed patterns",
        )

    if _pii_re.search(text):
        raise HTTPException(
            status_code=400,
            detail="Query contains potential personal information",
        )

    return text
