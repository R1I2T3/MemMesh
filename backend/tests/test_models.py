import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.db.mysql import Base
from backend.models import User, Team, TeamMember, ParentDocument, Message, UserFeedback

def test_models_create_all_tables():
    """Verify all models produce DDL and tables can be written to."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        # Create user
        user_id = str(uuid.uuid4())
        u = User(user_id=user_id, email="test@test.com", password_hash="hash")
        session.add(u)

        # Create team
        team_id = str(uuid.uuid4())
        t = Team(team_id=team_id, name="Test Team")
        session.add(t)

        # Flush parents to DB so children's FKs will resolve
        session.flush()

        # Create team member
        tm = TeamMember(team_id=team_id, user_id=user_id, role="admin")
        session.add(tm)

        # Create parent document
        doc_id = str(uuid.uuid4())
        doc = ParentDocument(parent_id=doc_id, filename="doc.pdf", content="Extracted text...", team_id=team_id)
        session.add(doc)

        # Create user feedback
        fb_id = str(uuid.uuid4())
        fb = UserFeedback(feedback_id=fb_id, query="What is A?", response="A is...", rating=1, trace_id="trace-123")
        session.add(fb)

        session.commit()

        # Assert default values and inserts
        db_user = session.query(User).filter_by(user_id=user_id).first()
        assert db_user.global_role == "user"  # default
        assert db_user.created_at is not None

        db_tm = session.query(TeamMember).filter_by(team_id=team_id, user_id=user_id).first()
        assert db_tm.role == "admin"

        db_doc = session.query(ParentDocument).filter_by(parent_id=doc_id).first()
        assert db_doc.filename == "doc.pdf"

        db_fb = session.query(UserFeedback).filter_by(feedback_id=fb_id).first()
        assert db_fb.rating == 1

def test_message_tree_structure():
    """Verify parent-child message relationships work."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        user_id = str(uuid.uuid4())
        parent_id = str(uuid.uuid4())
        child_id = str(uuid.uuid4())
        session.add(User(user_id=user_id, email="test@test.com", password_hash="hash"))
        session.commit()
        session.add(Message(message_id=parent_id, session_id="s1", parent_message_id=None, user_id=user_id, role="user", content="Hello"))
        session.add(Message(message_id=child_id, session_id="s1", parent_message_id=parent_id, user_id=user_id, role="assistant", content="Hi"))
        session.commit()
        child = session.query(Message).filter_by(message_id=child_id).first()
        assert child.parent_message_id == parent_id

def test_cascade_delete_team():
    """Verify deleting a team deletes its members and parent documents (cascades)."""
    # SQLite requires enabling foreign keys explicitly
    engine = create_engine("sqlite:///:memory:")
    
    # Enable FKs in SQLite for test correctness
    from sqlalchemy import event
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        u_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())
        doc_id = str(uuid.uuid4())

        session.add(User(user_id=u_id, email="cascade@test.com", password_hash="hash"))
        session.add(Team(team_id=t_id, name="Cascade Team"))
        
        # Flush parents to DB so children's FKs will resolve
        session.flush()

        session.add(TeamMember(team_id=t_id, user_id=u_id))
        session.add(ParentDocument(parent_id=doc_id, filename="doc.pdf", content="Text", team_id=t_id))
        session.commit()

        # Delete team
        team = session.query(Team).filter_by(team_id=t_id).first()
        session.delete(team)
        session.commit()

        # Verify cascades
        assert session.query(TeamMember).filter_by(team_id=t_id).first() is None
        assert session.query(ParentDocument).filter_by(parent_id=doc_id).first() is None
        # User should still exist
        assert session.query(User).filter_by(user_id=u_id).first() is not None
