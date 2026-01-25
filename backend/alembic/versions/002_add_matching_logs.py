"""Add matching_logs table for monitoring match quality.

Revision ID: 002_add_matching_logs
Revises: 001_initial_schema
Create Date: 2026-01-25
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "002_add_matching_logs"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create matching_logs table."""
    op.create_table(
        "matching_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("match_type", sa.String(50), nullable=False),
        sa.Column("source_id", sa.String(100), nullable=False),
        sa.Column("source_name", sa.String(200), nullable=True),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("target_name", sa.String(200), nullable=True),
        sa.Column("name_score", sa.Numeric(5, 3), nullable=True),
        sa.Column("address_score", sa.Numeric(5, 3), nullable=True),
        sa.Column("area_score", sa.Numeric(5, 3), nullable=True),
        sa.Column("match_score", sa.Numeric(5, 3), nullable=True),
        sa.Column("match_method", sa.String(50), nullable=True),
        sa.Column("confidence", sa.String(20), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, default=False),
        sa.Column("failure_reason", sa.String(500), nullable=True),
        sa.Column("dong_code", sa.String(10), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    # Indexes for querying
    op.create_index(
        "idx_matching_logs_type_created",
        "matching_logs",
        ["match_type", "created_at"],
    )
    op.create_index(
        "idx_matching_logs_success",
        "matching_logs",
        ["success", "created_at"],
    )
    op.create_index(
        "idx_matching_logs_dong_code",
        "matching_logs",
        ["dong_code", "created_at"],
    )


def downgrade() -> None:
    """Drop matching_logs table."""
    op.drop_index("idx_matching_logs_dong_code", "matching_logs")
    op.drop_index("idx_matching_logs_success", "matching_logs")
    op.drop_index("idx_matching_logs_type_created", "matching_logs")
    op.drop_table("matching_logs")
