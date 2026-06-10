from sqlalchemy import Column, String, ForeignKey, Text, Integer, BigInteger, Double, Float, Index, DateTime, func, JSON
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

class Session(Base):
    __tablename__ = "sessions"
    session_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    team_id = Column(String(36), ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    consolidated_at = Column(DateTime, nullable=True)

class Turn(Base):
    __tablename__ = "turns"
    turn_id = Column(String(36), primary_key=True)
    session_id = Column(String(36), ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False, index=True)
    team_id = Column(String(36), ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text(4294967295), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

class SourceDoc(Base):
    __tablename__ = "source_docs"
    doc_id = Column(String(36), primary_key=True)
    team_id = Column(String(36), ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=False, index=True)
    source_type = Column(String(20), nullable=False)
    source_ref = Column(String(1024), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_format = Column(String(50), nullable=False)
    content_hash = Column(String(64), nullable=False)
    uploaded_by = Column(String(36), ForeignKey("users.user_id"), nullable=False)
    status = Column(String(20), default="pending")
    error_message = Column(Text, nullable=True)
    version_number = Column(Integer, default=1)
    previous_version_id = Column(String(36), nullable=True)
    crawled_at = Column(DateTime, nullable=True)
    modified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    __table_args__ = (Index("idx_doc_team_hash", "team_id", "content_hash"), Index("idx_doc_status", "status"))

class VectorChunk(Base):
    __tablename__ = "vector_chunks"
    chunk_id = Column(String(36), primary_key=True)
    team_id = Column(String(36), ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=False)
    doc_id = Column(String(36), ForeignKey("source_docs.doc_id", ondelete="CASCADE"), nullable=False)
    importance_score = Column(Double, default=0.5)
    last_accessed_at = Column(DateTime, server_default=func.now())
    page_number = Column(Integer, nullable=True)
    section_heading = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    __table_args__ = (Index("idx_chunk_decay", "importance_score", "last_accessed_at"),)

class RouterLog(Base):
    __tablename__ = "router_log"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    team_id = Column(String(36), ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False)
    query_hash = Column(String(64), nullable=False)
    route = Column(String(20), nullable=False)
    latency_ms = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

class EntityResolutionLog(Base):
    __tablename__ = "entity_resolution_log"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    team_id = Column(String(36), ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=False)
    source_node_id = Column(String(100), nullable=False)
    target_node_id = Column(String(100), nullable=False)
    merge_reason = Column(Text, nullable=False)
    resolved_at = Column(DateTime, server_default=func.now())

class CrawlJob(Base):
    __tablename__ = "crawl_jobs"
    job_id = Column(String(36), primary_key=True)
    team_id = Column(String(36), ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=False)
    triggered_by = Column(String(36), ForeignKey("users.user_id"), nullable=False)
    source_url = Column(String(1024), nullable=False)
    status = Column(String(20), nullable=False)
    pages_found = Column(Integer, default=0)
    started_at = Column(DateTime, server_default=func.now())
    finished_at = Column(DateTime, nullable=True)

class EvalScore(Base):
    __tablename__ = "eval_scores"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    feedback_id = Column(String(36), ForeignKey("user_feedbacks.feedback_id", ondelete="CASCADE"), nullable=False)
    faithfulness_score = Column(Float, nullable=True)
    hallucination_score = Column(Float, nullable=True)
    answer_relevancy_score = Column(Float, nullable=True)
    model_version = Column(String(50), nullable=True)
    evaluated_at = Column(DateTime, server_default=func.now())
