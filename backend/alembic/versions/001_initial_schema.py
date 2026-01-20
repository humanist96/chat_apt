"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Apartments table
    op.create_table(
        'apartments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('address', sa.String(500), nullable=True),
        sa.Column('dong_code', sa.String(20), nullable=True),
        sa.Column('complex_no', sa.String(50), nullable=True),
        sa.Column('latitude', sa.Numeric(10, 7), nullable=True),
        sa.Column('longitude', sa.Numeric(10, 7), nullable=True),
        sa.Column('total_units', sa.Integer(), nullable=True),
        sa.Column('built_year', sa.Integer(), nullable=True),
        sa.Column('avg_area', sa.Numeric(10, 2), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_apartments_dong_code', 'apartments', ['dong_code'])
    op.create_index('idx_apartments_complex_no', 'apartments', ['complex_no'], unique=True)

    # Transactions table
    op.create_table(
        'transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('apartment_id', sa.Integer(), nullable=False),
        sa.Column('deal_amount', sa.Integer(), nullable=False),
        sa.Column('area', sa.Numeric(10, 2), nullable=True),
        sa.Column('floor', sa.Integer(), nullable=True),
        sa.Column('deal_year', sa.Integer(), nullable=False),
        sa.Column('deal_month', sa.Integer(), nullable=False),
        sa.Column('deal_day', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['apartment_id'], ['apartments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_transactions_apartment', 'transactions', ['apartment_id'])
    op.create_index('idx_transactions_date', 'transactions', ['deal_year', 'deal_month'])

    # Listings table
    op.create_table(
        'listings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('apartment_id', sa.Integer(), nullable=False),
        sa.Column('article_no', sa.String(50), nullable=True),
        sa.Column('trade_type', sa.String(20), nullable=True),
        sa.Column('price', sa.Integer(), nullable=False),
        sa.Column('rent_price', sa.Integer(), nullable=True),
        sa.Column('area', sa.Numeric(10, 2), nullable=True),
        sa.Column('floor', sa.Integer(), nullable=True),
        sa.Column('direction', sa.String(20), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('realtor_name', sa.String(100), nullable=True),
        sa.Column('realtor_phone', sa.String(20), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('first_seen_at', sa.DateTime(), nullable=True),
        sa.Column('last_seen_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['apartment_id'], ['apartments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_listings_apartment', 'listings', ['apartment_id'])
    op.create_index('idx_listings_article_no', 'listings', ['article_no'], unique=True)
    op.create_index('idx_listings_active', 'listings', ['is_active'])

    # User profiles table
    op.create_table(
        'user_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('name', sa.String(100), nullable=True),
        sa.Column('membership_tier', sa.String(20), default='free'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_user_profiles_email', 'user_profiles', ['email'], unique=True)

    # Subscriptions table
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('plan', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), default='active'),
        sa.Column('billing_key', sa.String(100), nullable=True),
        sa.Column('current_period_start', sa.DateTime(), nullable=True),
        sa.Column('current_period_end', sa.DateTime(), nullable=True),
        sa.Column('cancel_at_period_end', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_subscriptions_user', 'subscriptions', ['user_id'])
    op.create_index('idx_subscriptions_status', 'subscriptions', ['status'])

    # Payment history table
    op.create_table(
        'payment_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('subscription_id', sa.Integer(), nullable=True),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(3), default='KRW'),
        sa.Column('status', sa.String(20), nullable=True),
        sa.Column('payment_key', sa.String(100), nullable=True),
        sa.Column('order_id', sa.String(100), nullable=True),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user_profiles.id']),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_payment_history_user', 'payment_history', ['user_id'])

    # Favorites table
    op.create_table(
        'favorites',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('apartment_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['apartment_id'], ['apartments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_favorites_user', 'favorites', ['user_id', 'apartment_id'], unique=True)

    # Similar apartments table
    op.create_table(
        'similar_apartments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('apartment_id', sa.Integer(), nullable=False),
        sa.Column('similar_apartment_id', sa.Integer(), nullable=False),
        sa.Column('similarity_score', sa.Numeric(5, 2), nullable=True),
        sa.Column('location_score', sa.Numeric(5, 2), nullable=True),
        sa.Column('area_score', sa.Numeric(5, 2), nullable=True),
        sa.Column('correlation_score', sa.Numeric(5, 2), nullable=True),
        sa.Column('calculated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['apartment_id'], ['apartments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['similar_apartment_id'], ['apartments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_similar_apartments', 'similar_apartments', ['apartment_id'])

    # Analysis results table
    op.create_table(
        'analysis_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('listing_id', sa.Integer(), nullable=False),
        sa.Column('recommendation_score', sa.Numeric(5, 2), nullable=True),
        sa.Column('discount_rate', sa.Numeric(5, 2), nullable=True),
        sa.Column('similar_avg_price', sa.Integer(), nullable=True),
        sa.Column('is_undervalued', sa.Boolean(), default=False),
        sa.Column('calculated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['listing_id'], ['listings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_analysis_results_listing', 'analysis_results', ['listing_id'], unique=True)
    op.create_index('idx_analysis_results_score', 'analysis_results', ['recommendation_score'])

    # Monthly price cache table
    op.create_table(
        'monthly_price_cache',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('apartment_id', sa.Integer(), nullable=False),
        sa.Column('year_month', sa.String(7), nullable=False),
        sa.Column('avg_price', sa.Integer(), nullable=True),
        sa.Column('avg_price_per_pyeong', sa.Integer(), nullable=True),
        sa.Column('transaction_count', sa.Integer(), nullable=True),
        sa.Column('calculated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['apartment_id'], ['apartments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_monthly_price_cache', 'monthly_price_cache', ['apartment_id', 'year_month'], unique=True)


def downgrade() -> None:
    op.drop_table('monthly_price_cache')
    op.drop_table('analysis_results')
    op.drop_table('similar_apartments')
    op.drop_table('favorites')
    op.drop_table('payment_history')
    op.drop_table('subscriptions')
    op.drop_table('user_profiles')
    op.drop_table('listings')
    op.drop_table('transactions')
    op.drop_table('apartments')
