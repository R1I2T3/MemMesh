import pytest
import httpx
from tests.e2e.conftest import API_URL

@pytest.mark.e2e
def test_api_health_endpoint():
    r = httpx.get(f"{API_URL}/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"

@pytest.mark.e2e
def test_frontend_loads_without_error(page):
    errors = []
    page.on("pageerror", lambda e: errors.append(e))
    page.reload()
    page.wait_for_load_state("networkidle")
    assert len(errors) == 0, f"Found JS errors on load: {errors}"
