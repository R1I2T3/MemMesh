import pytest
import httpx
from tests.e2e.conftest import API_URL

@pytest.mark.e2e
def test_new_session_generates_unique_id():
    r1 = httpx.post(f"{API_URL}/session/new").json()["session_id"]
    r2 = httpx.post(f"{API_URL}/session/new").json()["session_id"]
    assert r1 != r2

@pytest.mark.e2e
def test_new_session_clears_chat_history_in_ui(page):
    # Skip test execution natively if frontend missing
    page.locator("[data-testid='chat-input']").fill("Hello")
    page.keyboard.press("Enter")
    page.wait_for_selector("[data-testid='agent-response']", timeout=15000)

    # Click new session
    page.locator("[data-testid='new-session-btn']").click()
    page.wait_for_timeout(1000) # Give React/Vue state time to clear

    messages = page.locator("[data-testid='chat-message']").count()
    assert messages == 0
