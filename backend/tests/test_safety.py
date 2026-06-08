import pytest
from backend.agents.safety import validate_query, validate_output, SafetyValidationError

def test_validate_query_toxic_blocked():
    with pytest.raises(SafetyValidationError, match="toxic language"):
        validate_query("This is a toxic and offensive query.")
        
    with pytest.raises(SafetyValidationError, match="toxic language"):
        validate_query("I hate you and want to say hate speech.")

def test_validate_query_pii_email_scrubbed():
    # Test email scrubbing
    query = "My email is test.user@example.com, please contact me."
    scrubbed = validate_query(query)
    assert "test.user@example.com" not in scrubbed
    assert "[EMAIL]" in scrubbed

def test_validate_query_pii_phone_scrubbed():
    # Test phone number scrubbing
    query = "Reach me at 123-456-7890 tomorrow."
    scrubbed = validate_query(query)
    assert "123-456-7890" not in scrubbed
    assert "[PHONE]" in scrubbed

def test_validate_query_clean_passes():
    query = "Who is the lead engineer of Project Titan?"
    result = validate_query(query)
    assert result == query

# Output Safety Tests
def test_validate_output_toxic_blocked():
    with pytest.raises(SafetyValidationError, match="toxic language"):
        validate_output("This response contains toxic and offensive language.")

def test_validate_output_pii_email_scrubbed():
    response = "Contact the admin at superadmin@memmesh.com for details."
    scrubbed = validate_output(response)
    assert "superadmin@memmesh.com" not in scrubbed
    assert "[EMAIL]" in scrubbed

def test_validate_output_clean_passes():
    response = "The team lead of Project Titan is Alice."
    result = validate_output(response)
    assert result == response
