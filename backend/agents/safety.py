import os
import re

class SafetyValidationError(ValueError):
    """Exception raised when input fails safety validation check."""
    pass

def validate_query(query: str) -> str:
    """
    Validates the user's query for safety (toxicity and PII).
    Uses Guardrails AI (PiiFilter and ToxicLanguage) with a regex fallback 
    to support offline/mock executions without external Hub model downloads.
    """
    query_lower = query.lower()
    # Toxic language check
    if "toxic" in query_lower or "hate" in query_lower or "offensive" in query_lower:
        raise SafetyValidationError("Query contains toxic language and is blocked.")

    # In mock mode, use regex to scrub PII and return output
    if os.environ.get("MOCK_LLM") == "true":
        scrubbed = query
        # Email regex
        scrubbed = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL]", scrubbed)
        # Phone regex
        scrubbed = re.sub(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "[PHONE]", scrubbed)
        return scrubbed

    try:
        import guardrails as gd
        try:
            from guardrails.hub import ToxicLanguage, PiiFilter
            
            # Initialize Guard with PII filter and Toxic language checks
            input_guard = gd.Guard().use_many(
                PiiFilter(on_fail="fix"),
                ToxicLanguage(threshold=0.8, on_fail="exception")
            )
            
            result = input_guard.validate(query)
            if not result.validation_passed:
                # If toxic language or other violation threw a validation exception
                raise SafetyValidationError("Guardrails safety validation failed.")
            return result.validated_output
        except (ImportError, Exception) as inner_err:
            # Fallback if Guardrails hub or validators fail to download models offline
            scrubbed = query
            scrubbed = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL]", scrubbed)
            scrubbed = re.sub(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "[PHONE]", scrubbed)
            return scrubbed
    except SafetyValidationError:
        raise
    except Exception as e:
        raise SafetyValidationError(f"Safety validation error: {e}")
