import pytest

@pytest.mark.e2e
def test_user_can_submit_query_and_receive_response(page):
    input_selector = "[data-testid='chat-input']"
    
    page.wait_for_selector(input_selector, state="visible")
    page.locator(input_selector).fill("What is the relationship between LanceDB and Neo4j?")
    page.keyboard.press("Enter")

    # Streaming indicator appears
    page.wait_for_selector("[data-testid='loading-indicator']", timeout=5000, state="visible")

    # Full response should eventually render
    page.wait_for_selector("[data-testid='agent-response']", timeout=20000, state="visible")
    text = page.locator("[data-testid='agent-response']").last.inner_text()
    
    assert len(text) > 10
    assert "error" not in text.lower() # Basic hallucination/fail check
