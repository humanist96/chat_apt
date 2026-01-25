"""Payment-related models."""
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import String, Integer, Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, GUID

if TYPE_CHECKING:
    from app.models.user import UserProfile


class Subscription(Base):
    """Subscription information table."""
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("user_profiles.id", ondelete="CASCADE"),
        index=True
    )
    plan: Mapped[str] = mapped_column(String(20), nullable=False)  # basic, premium
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, cancelled, expired
    billing_key: Mapped[Optional[str]] = mapped_column(String(100))
    current_period_start: Mapped[Optional[datetime]] = mapped_column()
    current_period_end: Mapped[Optional[datetime]] = mapped_column()
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user: Mapped["UserProfile"] = relationship(back_populates="subscriptions")
    payments: Mapped[list["PaymentHistory"]] = relationship(
        back_populates="subscription", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_subscriptions_status", "status"),
    )


class PaymentHistory(Base):
    """Payment history table."""
    __tablename__ = "payment_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("user_profiles.id"),
        index=True
    )
    subscription_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("subscriptions.id"),
        index=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="KRW")
    status: Mapped[Optional[str]] = mapped_column(String(20))  # success, failed, refunded
    payment_key: Mapped[Optional[str]] = mapped_column(String(100))
    order_id: Mapped[Optional[str]] = mapped_column(String(100))
    paid_at: Mapped[Optional[datetime]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    subscription: Mapped[Optional["Subscription"]] = relationship(back_populates="payments")
