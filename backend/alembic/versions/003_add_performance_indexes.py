"""Add performance indexes

Revision ID: 003
Revises: 002
Create Date: 2024-01-25

This migration adds indexes to improve query performance for:
- Fire sale detection (apartment_id + deal_amount combination)
- Listing queries (is_active + price combination)
- Area-based searches (rounded area for grouping)
- Price trend queries (apartment_id + year_month)

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add performance indexes."""

    # Composite index for transaction lookups by apartment and amount
    # Used heavily in fire sale detection queries
    op.create_index(
        'idx_transactions_apt_amount',
        'transactions',
        ['apartment_id', 'deal_amount'],
        if_not_exists=True
    )

    # Composite index for active listings by price
    # Used in listing search and filtering
    op.create_index(
        'idx_listings_active_price',
        'listings',
        ['is_active', 'price'],
        if_not_exists=True
    )

    # Index for transaction area lookups (rounded for grouping)
    # Used in fire sale area matching
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_apt_area_rounded
        ON transactions (apartment_id, ROUND(area, 0))
    """)

    # Composite index for monthly price cache queries
    # Used in price trend and comparison analysis
    op.create_index(
        'idx_monthly_price_apt_month',
        'monthly_price_cache',
        ['apartment_id', 'year_month'],
        if_not_exists=True
    )

    # Index for similar apartments by similarity score
    # Used in comparison reports
    op.create_index(
        'idx_similar_apt_score',
        'similar_apartments',
        ['apartment_id', 'similarity_score'],
        if_not_exists=True
    )

    # Index for listings by apartment_id and article_no
    # Used in crawler duplicate detection
    op.create_index(
        'idx_listings_apt_article',
        'listings',
        ['apartment_id', 'article_no'],
        if_not_exists=True
    )

    # Partial index for active listings only
    # Improves query performance when filtering by is_active=true
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_listings_active_only
        ON listings (apartment_id, price, area)
        WHERE is_active = true
    """)

    # Index for transaction date queries
    # Used in time-weighted price calculations
    op.create_index(
        'idx_transactions_apt_date',
        'transactions',
        ['apartment_id', 'deal_date'],
        if_not_exists=True
    )


def downgrade() -> None:
    """Remove performance indexes."""

    op.drop_index('idx_transactions_apt_amount', table_name='transactions')
    op.drop_index('idx_listings_active_price', table_name='listings')
    op.execute("DROP INDEX IF EXISTS idx_transactions_apt_area_rounded")
    op.drop_index('idx_monthly_price_apt_month', table_name='monthly_price_cache')
    op.drop_index('idx_similar_apt_score', table_name='similar_apartments')
    op.drop_index('idx_listings_apt_article', table_name='listings')
    op.execute("DROP INDEX IF EXISTS idx_listings_active_only")
    op.drop_index('idx_transactions_apt_date', table_name='transactions')
