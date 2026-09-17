"""Add context JSONB to evaluation_event table.

Revision ID: 003_evaluation_event_context
Revises: 002_user_refresh_token
Create Date: 2026-09-17
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "003_evaluation_event_context"
down_revision = "002_user_refresh_token"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add nullable context column to partitioned evaluation_event table
    op.add_column(
        "evaluation_event",
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("evaluation_event", "context")
