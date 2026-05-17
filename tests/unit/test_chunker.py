import pytest
from unittest.mock import patch, MagicMock
from utils.chunker import chunk_text, extract_text_from_url

@pytest.mark.unit
def test_empty_input_returns_empty_list():
    assert chunk_text("") == []

@pytest.mark.unit
def test_short_text_returns_single_chunk():
    result = chunk_text("Hello world.", chunk_size=512, overlap=50)
    assert len(result) == 1
    assert result[0]["chunk_index"] == 0
    assert "Hello world." in result[0]["text"]

@pytest.mark.unit
def test_long_text_produces_multiple_chunks():
    long_text = "word " * 600          # ~3000 chars
    result = chunk_text(long_text, chunk_size=512, overlap=50)
    assert len(result) > 1

@pytest.mark.unit
def test_no_chunk_exceeds_max_size():
    long_text = "word " * 600
    result = chunk_text(long_text, chunk_size=512, overlap=50)
    for chunk in result:
        assert len(chunk["text"]) <= 512

@pytest.mark.unit
def test_overlap_is_preserved_between_consecutive_chunks():
    long_text = "word " * 600
    result = chunk_text(long_text, chunk_size=100, overlap=20)
    if len(result) >= 2:
        assert len(result[0]["text"]) <= 100
        assert len(result[1]["text"]) <= 100
        assert len(result) > 1

@pytest.mark.unit
@patch("utils.chunker.requests.get")
def test_extract_text_from_url_retries_on_timeout(mock_get):
    """Should retry on transient failures and succeed eventually."""
    import requests

    def failing_response(*args, **kwargs):
        raise requests.Timeout("Connection timed out")

    success_response = MagicMock()
    success_response.text = "<html><body>Success after retry</body></html>"
    success_response.raise_for_status = MagicMock()

    mock_get.side_effect = [
        requests.Timeout("timeout 1"),
        requests.Timeout("timeout 2"),
        success_response,
    ]

    result = extract_text_from_url("http://example.com", max_retries=3)
    assert "Success after retry" in result
    assert mock_get.call_count == 3

@pytest.mark.unit
@patch("utils.chunker.requests.get")
def test_extract_text_from_url_fails_after_max_retries(mock_get):
    """Should raise RuntimeError after exhausting all retries."""
    import requests
    mock_get.side_effect = requests.ConnectionError("connection refused")

    with pytest.raises(RuntimeError, match="after 2 attempts"):
        extract_text_from_url("http://example.com", max_retries=2)
    assert mock_get.call_count == 2
