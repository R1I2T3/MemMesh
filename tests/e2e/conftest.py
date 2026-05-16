import pytest
import os
from playwright.sync_api import sync_playwright, Browser, Page

# Use environment variables to allow CI/CD overrides for Enterprise Scaling
BASE_URL = os.getenv("E2E_FRONTEND_URL", "http://localhost:3000")
API_URL  = os.getenv("E2E_API_URL", "http://localhost:7777")

@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
        yield b
        b.close()

@pytest.fixture
def page(browser: Browser) -> Page:
    pg = browser.new_page()
    try:
        pg.goto(BASE_URL, timeout=10000) # Quick timeout for fast failure if frontend isn't up
        pg.wait_for_load_state("networkidle", timeout=5000)
    except Exception as e:
        pytest.skip(f"Frontend not reachable at {BASE_URL}. Start stack before E2E testing.")
    yield pg
    pg.close()
