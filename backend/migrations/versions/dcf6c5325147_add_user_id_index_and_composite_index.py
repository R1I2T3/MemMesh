"""add user_id index and composite index

Revision ID: dcf6c5325147
Revises: e7babcbdd989
Create Date: 2026-06-08 18:11:49.136527

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'dcf6c5325147'
down_revision: Union[str, None] = 'e7babcbdd989'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: add column as nullable; server_default required for backfill
    op.add_column('messages', sa.Column('user_id', sa.String(length=36), nullable=True))
    # Step 2: backfill existing rows with a known user_id from users table
    op.execute(
        "UPDATE messages m "
        "SET m.user_id = (SELECT u.user_id FROM users u LIMIT 1) "
        "WHERE m.user_id IS NULL"
    )
    # Step 3: set nullable=False now that all rows have a value
    op.alter_column('messages', 'user_id', existing_type=sa.String(36), nullable=False)
    op.create_index(op.f('ix_messages_created_at'), 'messages', ['created_at'], unique=False)
    op.create_index(op.f('ix_messages_user_id'), 'messages', ['user_id'], unique=False)
    op.create_index('ix_messages_user_session', 'messages', ['user_id', 'session_id'], unique=False)
    op.create_foreign_key('fk_messages_user_id', 'messages', 'users', ['user_id'], ['user_id'])
    op.alter_column('parent_documents', 'content',
               existing_type=mysql.LONGTEXT(),
               type_=sa.Text(length=4294967295),
               existing_nullable=False)


def downgrade() -> None:
    op.alter_column('parent_documents', 'content',
               existing_type=sa.Text(length=4294967295),
               type_=mysql.LONGTEXT(),
               existing_nullable=False)
    op.drop_constraint('fk_messages_user_id', 'messages', type_='foreignkey')
    op.drop_index('ix_messages_user_session', table_name='messages')
    op.drop_index(op.f('ix_messages_user_id'), table_name='messages')
    op.drop_index(op.f('ix_messages_created_at'), table_name='messages')
    op.drop_column('messages', 'user_id')
