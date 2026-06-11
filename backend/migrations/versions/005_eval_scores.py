"""Add eval_scores table

Revision ID: 005
Revises: 004
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"

def upgrade():
    op.create_table("eval_scores",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("feedback_id", sa.String(36), sa.ForeignKey("user_feedbacks.feedback_id"), nullable=False),
        sa.Column("faithfulness_score", sa.Float(), nullable=True),
        sa.Column("hallucination_score", sa.Float(), nullable=True),
        sa.Column("answer_relevancy_score", sa.Float(), nullable=True),
        sa.Column("model_version", sa.String(50), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(), server_default=sa.func.now()),
    )

def downgrade():
    op.drop_table("eval_scores")
