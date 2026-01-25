"""Listings API endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload
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
    naver_complex_no: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
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


def listing_to_response(listing: Listing) -> ListingResponse:
    """Convert Listing model to response with apartment's complex_no and coordinates fallback."""
    # Use listing's naver_complex_no, fallback to apartment's
    complex_no = listing.naver_complex_no
    latitude = None
    longitude = None

    if listing.apartment:
        if not complex_no:
            complex_no = listing.apartment.naver_complex_no
        # Get coordinates from apartment
        latitude = float(listing.apartment.latitude) if listing.apartment.latitude else None
        longitude = float(listing.apartment.longitude) if listing.apartment.longitude else None

    return ListingResponse(
        id=listing.id,
        apartment_id=listing.apartment_id,
        article_no=listing.article_no,
        naver_complex_no=complex_no,
        latitude=latitude,
        longitude=longitude,
        trade_type=listing.trade_type,
        price=listing.price,
        area=float(listing.area) if listing.area else None,
        floor=listing.floor,
        direction=listing.direction,
        description=listing.description,
        realtor_name=listing.realtor_name,
        is_active=listing.is_active,
    )


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
    query = (
        select(Listing)
        .options(selectinload(Listing.apartment))
        .where(Listing.is_active == is_active)
    )

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

    return [listing_to_response(listing) for listing in listings]


@router.get("/{listing_id}", response_model=ListingResponse)
async def get_listing(
    listing_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get listing by ID."""
    result = await db.execute(
        select(Listing)
        .options(selectinload(Listing.apartment))
        .where(Listing.id == listing_id)
    )
    listing = result.scalar_one_or_none()

    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    return listing_to_response(listing)


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
