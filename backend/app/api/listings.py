"""Listings API endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.models.apartment import Listing


router = APIRouter()


class ListingResponse(BaseModel):
    """Listing response schema."""
    id: int
    apartment_id: int
    article_no: Optional[str] = None
    trade_type: Optional[str] = None
    price: int
    area: Optional[float] = None
    floor: Optional[int] = None
    direction: Optional[str] = None
    description: Optional[str] = None
    realtor_name: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


class ListingCreate(BaseModel):
    """Listing creation schema."""
    apartment_id: int
    article_no: Optional[str] = None
    trade_type: Optional[str] = None
    price: int
    area: Optional[float] = None
    floor: Optional[int] = None
    direction: Optional[str] = None
    description: Optional[str] = None
    realtor_name: Optional[str] = None
    realtor_phone: Optional[str] = None


@router.get("/", response_model=List[ListingResponse])
async def list_listings(
    apartment_id: Optional[int] = Query(None, description="Filter by apartment ID"),
    is_active: bool = Query(True, description="Filter by active status"),
    min_price: Optional[int] = Query(None, description="Minimum price filter"),
    max_price: Optional[int] = Query(None, description="Maximum price filter"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List listings with optional filters."""
    query = select(Listing).where(Listing.is_active == is_active)

    if apartment_id:
        query = query.where(Listing.apartment_id == apartment_id)
    if min_price:
        query = query.where(Listing.price >= min_price)
    if max_price:
        query = query.where(Listing.price <= max_price)

    query = query.order_by(Listing.price.asc())
    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    listings = result.scalars().all()

    return listings


@router.get("/{listing_id}", response_model=ListingResponse)
async def get_listing(
    listing_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get listing by ID."""
    result = await db.execute(
        select(Listing).where(Listing.id == listing_id)
    )
    listing = result.scalar_one_or_none()

    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    return listing


@router.post("/", response_model=ListingResponse)
async def create_listing(
    data: ListingCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new listing."""
    listing = Listing(**data.model_dump())
    db.add(listing)
    await db.flush()
    await db.refresh(listing)

    return listing


@router.patch("/{listing_id}/deactivate")
async def deactivate_listing(
    listing_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Deactivate a listing."""
    result = await db.execute(
        select(Listing).where(Listing.id == listing_id)
    )
    listing = result.scalar_one_or_none()

    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    listing.is_active = False
    await db.flush()

    return {"message": "Listing deactivated", "id": listing_id}
