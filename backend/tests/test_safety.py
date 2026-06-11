import pytest
from backend.agents.safety import validate_query, validate_output, SafetyValidationError

def test_pii_scrubbing_email():
    result = validate_query("Contact me at test@example.com")
    assert "[EMAIL]" in result
    assert "test@example.com" not in result

def test_pii_scrubbing_phone():
    result = validate_query("Call 555-123-4567")
    assert "[PHONE]" in result

def test_toxic_query_blocked():
    with pytest.raises(SafetyValidationError):
        validate_query("I will kill you")

def test_safe_query_passes():
    result = validate_query("What is the capital of France?")
    assert result == "What is the capital of France?"

def test_output_pii_scrubbing():
    result = validate_output("My email is user@example.com and phone is 555-987-6543")
    assert "[EMAIL]" in result
    assert "[PHONE]" in result

def test_output_toxic_blocked():
    with pytest.raises(SafetyValidationError):
        validate_output("You are an idiot")
