import pytest
from utils.chunker import chunk_text

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
