from sqlalchemy import Column, String, ForeignKey, Text, Integer, Index, DateTime, func, JSON
from backend.db.mysql import Base

class User(Base):
    __tablename__ = "users"
    user_id = Column(String(36), primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    global_role = Column(String(20), default="user", index=True)
    created_at = Column(DateTime, server_default=func.now())

class Team(Base):
    __tablename__ = "teams"
    team_id = Column(String(36), primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

class TeamMember(Base):
    __tablename__ = "team_members"
    team_id = Column(String(36), ForeignKey("teams.team_id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True, index=True)
    role = Column(String(20), default="member")

class ParentDocument(Base):
    __tablename__ = "parent_documents"
    parent_id = Column(String(36), primary_key=True)
    filename = Column(String(255), nullable=False)
    content = Column(Text(4294967295), nullable=False)  # LONGTEXT for large PDFs
    team_id = Column(String(36), ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())

class Message(Base):
    __tablename__ = "messages"
    message_id = Column(String(36), primary_key=True)
    session_id = Column(String(36), nullable=False)
    parent_message_id = Column(String(36), ForeignKey("messages.message_id"), nullable=True, index=True)
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    citations = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)
    __table_args__ = (
        Index('ix_messages_session_parent', 'session_id', 'parent_message_id'),
        Index('ix_messages_user_session', 'user_id', 'session_id'),
    )

class UserFeedback(Base):
    __tablename__ = "user_feedbacks"
    feedback_id = Column(String(36), primary_key=True)
    query = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    rating = Column(Integer, nullable=False, index=True)  # 1 = Up, -1 = Down
    trace_id = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())
