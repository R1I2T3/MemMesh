from collections.abc import Generator
from typing import Optional
import pytest
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from backend.db.mysql import Base


@pytest.fixture(scope="session")
def mysql_container() -> Generator[Optional[object], None, None]:
    use_testcontainers = os.environ.get("USE_TESTCONTAINERS", "0") == "1"
    if use_testcontainers:
        from testcontainers.mysql import MySqlContainer
        with MySqlContainer("mysql:8.0") as mysql:
            yield mysql
    else:
        yield None


@pytest.fixture
def db_session(mysql_container) -> Generator[Session, None, None]:
    if mysql_container:
        url = mysql_container.get_connection_url()
    else:
        # Use SQLite for local dev
        url = "sqlite:///:memory:"
    engine = create_engine(url, pool_pre_ping=True)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)
