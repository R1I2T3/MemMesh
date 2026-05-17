import pytest
import os
import tempfile

from db.session_store import SessionStore


@pytest.fixture
def session_store():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    store = SessionStore(path)
    yield store
    store.close()
    os.unlink(path)


def test_save_and_load_messages(session_store):
    session_store.save_message("sess-1", "user-1", "team-1", "user", "Hello")
    session_store.save_message("sess-1", "user-1", "team-1", "assistant", "Hi there")

    messages = session_store.get_session_history("sess-1", "team-1", limit=10)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "Hi there"


def test_respects_limit(session_store):
    for i in range(15):
        session_store.save_message("sess-1", "user-1", "team-1", "user", f"msg-{i}")

    messages = session_store.get_session_history("sess-1", "team-1", limit=5)
    assert len(messages) == 5
    assert messages[0]["content"] == "msg-10"


def test_filters_by_team(session_store):
    session_store.save_message("sess-1", "user-1", "team-1", "user", "team1 msg")
    session_store.save_message("sess-1", "user-2", "team-2", "user", "team2 msg")

    messages = session_store.get_session_history("sess-1", "team-1", limit=10)
    assert len(messages) == 1
    assert messages[0]["content"] == "team1 msg"


def test_empty_session_returns_empty(session_store):
    messages = session_store.get_session_history("nonexistent", "team-1", limit=10)
    assert messages == []


def test_cleanup_old_messages(session_store):
    session_store.save_message("sess-1", "user-1", "team-1", "user", "old msg")
    session_store.conn.execute(
        "UPDATE session_messages SET created_at = datetime('now', '-60 days')"
    )
    session_store.conn.commit()

    session_store.save_message("sess-1", "user-1", "team-1", "user", "new msg")

    session_store.cleanup_expired(days=30)

    messages = session_store.get_session_history("sess-1", "team-1", limit=10)
    assert len(messages) == 1
    assert messages[0]["content"] == "new msg"
