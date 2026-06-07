import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.db.mysql import Base
from backend.models import User, Team, TeamMember, ParentDocument, Message, UserFeedback

def test_models_create_all_tables():
    """Verify all models produce valid DDL and tables are created."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        u = User(user_id=str(uuid.uuid4()), email="test@test.com", password_hash="hash", global_role="user")
        session.add(u)
        session.commit()
        result = session.query(User).filter_by(email="test@test.com").first()
        assert result is not None
        assert result.global_role == "user"

def test_message_tree_structure():
    """Verify parent-child message relationships work."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        parent_id = str(uuid.uuid4())
        child_id = str(uuid.uuid4())
        session.add(Message(message_id=parent_id, session_id="s1", parent_message_id=None, role="user", content="Hello"))
        session.add(Message(message_id=child_id, session_id="s1", parent_message_id=parent_id, role="assistant", content="Hi"))
        session.commit()
        child = session.query(Message).filter_by(message_id=child_id).first()
        assert child.parent_message_id == parent_id
