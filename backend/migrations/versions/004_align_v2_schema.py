"""Add V2 spec tables

Revision ID: 004
Revises: f35f180d9100
"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "f35f180d9100"

def upgrade():
    op.create_table("sessions",
        sa.Column("session_id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("consolidated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("idx_sess_team_user", "sessions", ["team_id", "user_id"])
    op.create_index("idx_sess_created", "sessions", ["created_at"])

    op.create_table("turns",
        sa.Column("turn_id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(4294967295), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_turn_sess_created", "turns", ["session_id", "created_at"])

    op.create_table("source_docs",
        sa.Column("doc_id", sa.String(36), primary_key=True),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_ref", sa.String(1024), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_format", sa.String(50), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("uploaded_by", sa.String(36), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("version_number", sa.Integer(), server_default="1"),
        sa.Column("previous_version_id", sa.String(36), nullable=True),
        sa.Column("crawled_at", sa.DateTime(), nullable=True),
        sa.Column("modified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_doc_team_hash", "source_docs", ["team_id", "content_hash"])
    op.create_index("idx_doc_status", "source_docs", ["status"])

    op.create_table("vector_chunks",
        sa.Column("chunk_id", sa.String(36), primary_key=True),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=False),
        sa.Column("doc_id", sa.String(36), sa.ForeignKey("source_docs.doc_id", ondelete="CASCADE"), nullable=False),
        sa.Column("importance_score", sa.Float(), server_default="0.5"),
        sa.Column("last_accessed_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section_heading", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_chunk_decay", "vector_chunks", ["importance_score", "last_accessed_at"])

    op.create_table("router_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("query_hash", sa.String(64), nullable=False),
        sa.Column("route", sa.String(20), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_rlog_team_route", "router_log", ["team_id", "route"])

    op.create_table("entity_resolution_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_node_id", sa.String(100), nullable=False),
        sa.Column("target_node_id", sa.String(100), nullable=False),
        sa.Column("merge_reason", sa.Text(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table("crawl_jobs",
        sa.Column("job_id", sa.String(36), primary_key=True),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=False),
        sa.Column("triggered_by", sa.String(36), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("source_url", sa.String(1024), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("pages_found", sa.Integer(), server_default="0"),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )

def downgrade():
    op.drop_table("crawl_jobs")
    op.drop_table("entity_resolution_log")
    op.drop_table("router_log")
    op.drop_table("vector_chunks")
    op.drop_table("source_docs")
    op.drop_table("turns")
    op.drop_table("sessions")
