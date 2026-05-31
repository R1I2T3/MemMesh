# backend/tests/conftest.py
"""Shared test fixtures for the backend test suite."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Override SQLITE_PATH before importing anything that uses config
_test_db = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
_test_db.close()  # Close the file descriptor immediately to prevent resource leaks
os.environ["SQLITE_PATH"] = _test_db.name
os.environ["JWT_SECRET"] = "test-secret-key-for-tests"

from api.server import create_app  # noqa: E402
from db.sqlite import run_migrations, seed_admin  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _setup_test_db():
    """Create test database with migrations and seed data."""
    run_migrations()
    seed_admin()
    yield
    try:
        os.unlink(_test_db.name)
    except FileNotFoundError:
        pass


@pytest.fixture()
def client():
    """FastAPI test client."""
    app = create_app()
    return TestClient(app)
