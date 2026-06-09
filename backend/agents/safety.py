import re
import logging
from functools import cache

logger = logging.getLogger(__name__)

class SafetyValidationError(ValueError):
    pass

@cache
def _get_analyzer_engine():
    from presidio_analyzer import AnalyzerEngine
    return AnalyzerEngine()

@cache
def _get_anonymizer_engine():
    from presidio_anonymizer import AnonymizerEngine
    return AnonymizerEngine()

_presidio_available = False
try:
    _get_analyzer_engine()
    _get_anonymizer_engine()
    _presidio_available = True
except Exception:
    logger.warning("Presidio not available. PII detection will use regex fallback.")

TOXIC_PATTERNS = [
    r"\b(kill|die|murder|attack|bomb|terrorist)\b",
    r"\b(hate|stupid|idiot|worthless)\b",
]

PHONE_REGEX = re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b")
EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
SSN_REGEX = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

def _has_toxic_content(text: str) -> bool:
    lower = text.lower()
    for pattern in TOXIC_PATTERNS:
        if re.search(pattern, lower):
            return True
    return False

def _scrub_pii(text: str) -> str:
    if _presidio_available:
        try:
            analyzer = _get_analyzer_engine()
            anonymizer = _get_anonymizer_engine()
            results = analyzer.analyze(text=text, language="en")
            if results:
                return anonymizer.anonymize(text=text, analyzer_results=results).text
        except Exception:
            logger.exception("Presidio failed, falling back to regex")
    text = EMAIL_REGEX.sub("[EMAIL]", text)
    text = PHONE_REGEX.sub("[PHONE]", text)
    text = SSN_REGEX.sub("[SSN]", text)
    return text

def validate_query(query: str) -> str:
    if _has_toxic_content(query):
        raise SafetyValidationError("Query contains potentially harmful content")
    return _scrub_pii(query)

def validate_output(output: str) -> str:
    if _has_toxic_content(output):
        raise SafetyValidationError("Output contains potentially harmful content")
    return _scrub_pii(output)
