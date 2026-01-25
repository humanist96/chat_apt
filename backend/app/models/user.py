"""User-related models."""
from datetime import datetime, date
from typing import Optional, List
from uuid import UUID

from sqlalchemy import String, Integer, Text, ForeignKey, Index, UniqueConstraint, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.database import Base


class UserProfile(Base):
    """User profile table (extends Supabase auth.users)."""
    __tablename__ = "user_profiles"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    email: Mapped[Optional[str]] = mapped_column(String(255))
    name: Mapped[Optional[str]] = mapped_column(String(100))
    avatar_url: Mapped[Optional[str]] = mapped_column(Text)
    membership_tier: Mapped[str] = mapped_column(String(20), default="free")
    subscription_expires_at: Mapped[Optional[datetime]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    favorite_regions: Mapped[List["UserFavoriteRegion"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    favorite_listings: Mapped[List["UserFavoriteListing"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    api_usages: Mapped[List["UserApiUsage"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    subscriptions: Mapped[List["Subscription"]] = relationship(
        "Subscription", back_populates="user", cascade="all, delete-orphan"
    )


class UserFavoriteRegion(Base):
    """User favorite regions table."""
    __tablename__ = "user_favorite_regions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="CASCADE"),
        index=True
    )
    dong_code: Mapped[Optional[str]] = mapped_column(String(10))
    region_name: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    user: Mapped["UserProfile"] = relationship(back_populates="favorite_regions")


class UserFavoriteListing(Base):
    """User favorite listings table."""
    __tablename__ = "user_favorite_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="CASCADE"),
        index=True
    )
    listing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("listings.id")
    )
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    user: Mapped["UserProfile"] = relationship(back_populates="favorite_listings")

    __table_args__ = (
        UniqueConstraint("user_id", "listing_id", name="uq_user_favorite_listing"),
    )


class UserApiUsage(Base):
    """User API usage tracking table."""
    __tablename__ = "user_api_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("user_profiles.id"),
        index=True
    )
    endpoint: Mapped[str] = mapped_column(String(100))
    request_count: Mapped[int] = mapped_column(Integer, default=1)
    usage_date: Mapped[date] = mapped_column(Date, default=date.today)

    # Relationships
    user: Mapped["UserProfile"] = relationship(back_populates="api_usages")

    __table_args__ = (
        UniqueConstraint("user_id", "endpoint", "usage_date", name="uq_user_api_usage_daily"),
        Index("idx_user_api_usage_user_date", "user_id", "usage_date"),
    )


# Import here to avoid circular imports
from app.models.payment import Subscription
