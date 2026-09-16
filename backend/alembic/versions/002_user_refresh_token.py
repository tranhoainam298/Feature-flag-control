"""Add refresh_token_hash to user table.

Revision ID: 002_user_refresh_token
Revises: 001_initial_schema
Create Date: 2026-09-16
"""

import sqlalchemy as sa

from alembic import op

revision = "002_user_refresh_token"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user", sa.Column("refresh_token_hash", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("user", "refresh_token_hash")
