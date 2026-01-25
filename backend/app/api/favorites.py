"""Favorites API endpoints."""
from typing import List, Optional
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from pydantic import BaseModel

from app.database import get_db
from app.models.user import UserFavoriteListing, UserFavoriteRegion, UserProfile
from app.models.apartment import Listing, Apartment
from app.auth.jwt import get_current_user, AuthenticatedUser


router = APIRouter()


# Response schemas
class FavoriteListingResponse(BaseModel):
    """Favorite listing response schema."""
    id: int
    listing_id: int
    apartment_name: Optional[str] = None
    price: Optional[int] = None
    area: Optional[float] = None
    floor: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class FavoriteRegionResponse(BaseModel):
    """Favorite region response schema."""
    id: int
    dong_code: Optional[str] = None
    region_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AddFavoriteListingRequest(BaseModel):
    """Add favorite listing request schema."""
    listing_id: int


class AddFavoriteRegionRequest(BaseModel):
    """Add favorite region request schema."""
    dong_code: str
    region_name: Optional[str] = None


# Listing favorites endpoints
@router.get("/listings", response_model=List[FavoriteListingResponse])
async def get_favorite_listings(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Get user's favorite listings."""
    # Query with join to get listing and apartment details
    query = (
        select(UserFavoriteListing, Listing, Apartment)
        .join(Listing, UserFavoriteListing.listing_id == Listing.id)
        .join(Apartment, Listing.apartment_id == Apartment.id)
        .where(UserFavoriteListing.user_id == UUID(user.id))
        .order_by(UserFavoriteListing.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(query)
    rows = result.all()

    return [
        FavoriteListingResponse(
            id=fav.id,
            listing_id=fav.listing_id,
            apartment_name=apt.name if apt else None,
            price=listing.price if listing else None,
            area=listing.area if listing else None,
            floor=listing.floor if listing else None,
            created_at=fav.created_at,
        )
        for fav, listing, apt in rows
    ]


@router.post("/listings", status_code=status.HTTP_201_CREATED)
async def add_favorite_listing(
    request: AddFavoriteListingRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a listing to favorites."""
    user_id = UUID(user.id)

    # Check if listing exists
    listing_result = await db.execute(
        select(Listing).where(Listing.id == request.listing_id)
    )
    listing = listing_result.scalar_one_or_none()
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found",
        )

    # Check if already favorited
    existing = await db.execute(
        select(UserFavoriteListing).where(
            UserFavoriteListing.user_id == user_id,
            UserFavoriteListing.listing_id == request.listing_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Listing already in favorites",
        )

    # Check favorite limit for free tier
    if user.membership_tier == "free":
        count_result = await db.execute(
            select(func.count(UserFavoriteListing.id))
            .where(UserFavoriteListing.user_id == user_id)
        )
        count = count_result.scalar() or 0
        if count >= 10:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Free tier limited to 10 favorite listings. Upgrade to add more.",
            )

    # Add favorite
    favorite = UserFavoriteListing(
        user_id=user_id,
        listing_id=request.listing_id,
    )
    db.add(favorite)
    await db.commit()

    return {"message": "Added to favorites", "listing_id": request.listing_id}


@router.delete("/listings/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite_listing(
    listing_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a listing from favorites."""
    result = await db.execute(
        delete(UserFavoriteListing).where(
            UserFavoriteListing.user_id == UUID(user.id),
            UserFavoriteListing.listing_id == listing_id,
        )
    )
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Favorite not found",
        )


@router.get("/listings/{listing_id}/status")
async def check_favorite_status(
    listing_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check if a listing is in favorites."""
    result = await db.execute(
        select(UserFavoriteListing).where(
            UserFavoriteListing.user_id == UUID(user.id),
            UserFavoriteListing.listing_id == listing_id,
        )
    )
    favorite = result.scalar_one_or_none()

    return {"is_favorite": favorite is not None}


# Region favorites endpoints
@router.get("/regions", response_model=List[FavoriteRegionResponse])
async def get_favorite_regions(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's favorite regions."""
    result = await db.execute(
        select(UserFavoriteRegion)
        .where(UserFavoriteRegion.user_id == UUID(user.id))
        .order_by(UserFavoriteRegion.created_at.desc())
    )
    regions = result.scalars().all()

    return [
        FavoriteRegionResponse(
            id=r.id,
            dong_code=r.dong_code,
            region_name=r.region_name,
            created_at=r.created_at,
        )
        for r in regions
    ]


@router.post("/regions", status_code=status.HTTP_201_CREATED)
async def add_favorite_region(
    request: AddFavoriteRegionRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a region to favorites."""
    user_id = UUID(user.id)

    # Check if already favorited
    existing = await db.execute(
        select(UserFavoriteRegion).where(
            UserFavoriteRegion.user_id == user_id,
            UserFavoriteRegion.dong_code == request.dong_code,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Region already in favorites",
        )

    # Check favorite limit for free tier
    if user.membership_tier == "free":
        count_result = await db.execute(
            select(func.count(UserFavoriteRegion.id))
            .where(UserFavoriteRegion.user_id == user_id)
        )
        count = count_result.scalar() or 0
        if count >= 3:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Free tier limited to 3 favorite regions. Upgrade to add more.",
            )

    # Add favorite
    favorite = UserFavoriteRegion(
        user_id=user_id,
        dong_code=request.dong_code,
        region_name=request.region_name,
    )
    db.add(favorite)
    await db.commit()

    return {"message": "Added to favorites", "dong_code": request.dong_code}


@router.delete("/regions/{dong_code}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite_region(
    dong_code: str,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a region from favorites."""
    result = await db.execute(
        delete(UserFavoriteRegion).where(
            UserFavoriteRegion.user_id == UUID(user.id),
            UserFavoriteRegion.dong_code == dong_code,
        )
    )
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Favorite not found",
        )
