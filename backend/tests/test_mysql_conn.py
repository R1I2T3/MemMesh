import pytest
from sqlalchemy import text
from backend.db.mysql import engine

def test_db_ping():
    with engine.connect() as conn:
        val = conn.execute(text("SELECT 1")).scalar()
        assert val == 1
