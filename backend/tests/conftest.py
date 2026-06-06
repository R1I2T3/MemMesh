import os
import shutil
import tempfile

import pytest
from fastapi.testclient import TestClient

# Override config variables before importing anything that uses config
_test_db = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
_test_db.close()  # Close the file descriptor immediately to prevent resource leaks
os.environ["SQLITE_PATH"] = _test_db.name
os.environ["JWT_SECRET"] = "test-secret-key-for-tests"

# Pre-initialize temp directories for ChromaDB and FalkorDB to ensure test isolation
_test_chroma_dir = tempfile.mkdtemp(prefix="test_chroma_")
os.environ["CHROMA_DIR"] = _test_chroma_dir

_test_falkor_dir = tempfile.mkdtemp(prefix="test_falkor_")
os.environ["FALKORDB_DIR"] = _test_falkor_dir

from api.server import create_app  # noqa: E402
from db.sqlite import run_migrations, seed_admin  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _setup_test_db():
    """Create test database with migrations and seed data."""
    run_migrations()
    seed_admin()
    yield
    # Cleanup DB
    try:
        os.unlink(_test_db.name)
    except FileNotFoundError:
        pass
    # Cleanup temporary directories
    shutil.rmtree(_test_chroma_dir, ignore_errors=True)
    shutil.rmtree(_test_falkor_dir, ignore_errors=True)


@pytest.fixture()
def client():
    """FastAPI test client."""
    app = create_app()
    return TestClient(app)
