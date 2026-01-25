"""Apartment-related models."""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    String, Integer, BigInteger, Boolean, Text,
    ForeignKey, Index, UniqueConstraint, DECIMAL, Date
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Apartment(Base):
    """Apartment master table."""
    __tablename__ = "apartments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    naver_complex_no: Mapped[Optional[str]] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(String(200))
    dong_code: Mapped[Optional[str]] = mapped_column(String(10), index=True)
    total_units: Mapped[Optional[int]] = mapped_column(Integer)
    built_year: Mapped[Optional[int]] = mapped_column(Integer)
    latitude: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 7))
    longitude: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 7))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    transactions: Mapped[List["Transaction"]] = relationship(back_populates="apartment")
    listings: Mapped[List["Listing"]] = relationship(back_populates="apartment")
    monthly_prices: Mapped[List["MonthlyPriceCache"]] = relationship(back_populates="apartment")

    __table_args__ = (
        Index("idx_apartments_name", "name"),
    )


class Transaction(Base):
    """Real transaction history table."""
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    apartment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("apartments.id"), index=True
    )
    deal_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    deal_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    floor: Mapped[Optional[int]] = mapped_column(Integer)
    area: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2), index=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    apartment: Mapped["Apartment"] = relationship(back_populates="transactions")

    __table_args__ = (
        UniqueConstraint(
            "apartment_id", "deal_date", "floor", "area", "deal_amount",
            name="uq_transactions_unique_deal"
        ),
    )


class Listing(Base):
    """Property listing (호가) table."""
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    apartment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("apartments.id"), index=True
    )
    article_no: Mapped[Optional[str]] = mapped_column(String(30), unique=True)
    naver_complex_no: Mapped[Optional[str]] = mapped_column(String(20))
    trade_type: Mapped[Optional[str]] = mapped_column(String(10))
    price: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    area: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2))
    floor: Mapped[Optional[int]] = mapped_column(Integer)
    direction: Mapped[Optional[str]] = mapped_column(String(20))
    description: Mapped[Optional[str]] = mapped_column(Text)
    realtor_name: Mapped[Optional[str]] = mapped_column(String(50))
    realtor_phone: Mapped[Optional[str]] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    apartment: Mapped["Apartment"] = relationship(back_populates="listings")
    analysis_results: Mapped[List["AnalysisResult"]] = relationship(back_populates="listing")
    comparison_analyses: Mapped[List["ComparisonAnalysis"]] = relationship(back_populates="listing")


class AnalysisResult(Base):
    """Analysis result table."""
    __tablename__ = "analysis_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("listings.id"), index=True
    )
    avg_transaction_price: Mapped[Optional[int]] = mapped_column(BigInteger)
    price_gap: Mapped[Optional[int]] = mapped_column(BigInteger)
    discount_rate: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(5, 2))
    recommendation_score: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(5, 2), index=True)
    analyzed_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    listing: Mapped["Listing"] = relationship(back_populates="analysis_results")


class SimilarApartment(Base):
    """Similar apartment mapping table."""
    __tablename__ = "similar_apartments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    apartment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("apartments.id"), index=True
    )
    similar_apartment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("apartments.id")
    )
    similarity_score: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(5, 2), index=True)
    location_score: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(5, 2))
    area_score: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(5, 2))
    correlation_score: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(5, 2))
    scale_score: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(5, 2))
    age_score: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(5, 2))
    calculated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "apartment_id", "similar_apartment_id",
            name="uq_similar_apartments_pair"
        ),
    )


class ComparisonAnalysis(Base):
    """Similar property comparison analysis result table."""
    __tablename__ = "comparison_analysis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("listings.id"), index=True
    )
    similar_apartment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("apartments.id")
    )
    target_price_per_pyeong: Mapped[Optional[int]] = mapped_column(BigInteger)
    similar_price_per_pyeong: Mapped[Optional[int]] = mapped_column(BigInteger)
    price_gap_percent: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(5, 2))
    analyzed_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    listing: Mapped["Listing"] = relationship(back_populates="comparison_analyses")


class MonthlyPriceCache(Base):
    """Monthly average price cache for correlation calculation."""
    __tablename__ = "monthly_price_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    apartment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("apartments.id"), index=True
    )
    area_pyeong: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(5, 1))
    year_month: Mapped[str] = mapped_column(String(7))  # YYYY-MM
    avg_price: Mapped[Optional[int]] = mapped_column(BigInteger)
    avg_price_per_pyeong: Mapped[Optional[int]] = mapped_column(BigInteger)
    transaction_count: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    apartment: Mapped["Apartment"] = relationship(back_populates="monthly_prices")

    __table_args__ = (
        UniqueConstraint(
            "apartment_id", "area_pyeong", "year_month",
            name="uq_monthly_price_cache_unique"
        ),
        Index("idx_monthly_price_cache_apartment_month", "apartment_id", "year_month"),
    )
