"""Transactions API endpoints."""
from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.models.apartment import Transaction


router = APIRouter()


class TransactionResponse(BaseModel):
    """Transaction response schema."""
    id: int
    apartment_id: int
    deal_amount: int
    deal_date: date
    floor: Optional[int] = None
    area: Optional[float] = None

    class Config:
        from_attributes = True


class TransactionCreate(BaseModel):
    """Transaction creation schema."""
    apartment_id: int
    deal_amount: int
    deal_date: date
    floor: Optional[int] = None
    area: Optional[float] = None


@router.get("/", response_model=List[TransactionResponse])
async def list_transactions(
    apartment_id: Optional[int] = Query(None, description="Filter by apartment ID"),
    start_date: Optional[date] = Query(None, description="Start date filter"),
    end_date: Optional[date] = Query(None, description="End date filter"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List transactions with optional filters."""
    query = select(Transaction)

    if apartment_id:
        query = query.where(Transaction.apartment_id == apartment_id)
    if start_date:
        query = query.where(Transaction.deal_date >= start_date)
    if end_date:
        query = query.where(Transaction.deal_date <= end_date)

    query = query.order_by(Transaction.deal_date.desc())
    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    transactions = result.scalars().all()

    return transactions


@router.post("/", response_model=TransactionResponse)
async def create_transaction(
    data: TransactionCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new transaction record."""
    transaction = Transaction(**data.model_dump())
    db.add(transaction)
    await db.flush()
    await db.refresh(transaction)

    return transaction


@router.get("/stats/{apartment_id}")
async def get_transaction_stats(
    apartment_id: int,
    months: int = Query(12, ge=1, le=60, description="Number of months to analyze"),
    db: AsyncSession = Depends(get_db),
):
    """Get transaction statistics for an apartment."""
    from datetime import timedelta
    from sqlalchemy import func

    cutoff_date = date.today() - timedelta(days=months * 30)

    query = select(
        func.count(Transaction.id).label("count"),
        func.avg(Transaction.deal_amount).label("avg_price"),
        func.min(Transaction.deal_amount).label("min_price"),
        func.max(Transaction.deal_amount).label("max_price"),
    ).where(
        Transaction.apartment_id == apartment_id,
        Transaction.deal_date >= cutoff_date,
    )

    result = await db.execute(query)
    row = result.one()

    return {
        "apartment_id": apartment_id,
        "period_months": months,
        "transaction_count": row.count,
        "avg_price": int(row.avg_price) if row.avg_price else None,
        "min_price": row.min_price,
        "max_price": row.max_price,
    }
