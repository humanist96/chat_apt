"""Auth API endpoints."""
from typing import Optional
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr

from app.database import get_db
from app.models.user import UserProfile
from app.auth.jwt import get_current_user, AuthenticatedUser


router = APIRouter()


class UserProfileResponse(BaseModel):
    """User profile response schema."""
    id: str
    email: Optional[str] = None
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    membership_tier: str = "free"
    subscription_expires_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class UserProfileUpdate(BaseModel):
    """User profile update schema."""
    name: Optional[str] = None
    avatar_url: Optional[str] = None


@router.get("/me", response_model=UserProfileResponse)
async def get_current_user_profile(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's profile."""
    result = await db.execute(
        select(UserProfile).where(UserProfile.id == UUID(user.id))
    )
    profile = result.scalar_one_or_none()

    if not profile:
        # Create profile if it doesn't exist
        profile = UserProfile(
            id=UUID(user.id),
            email=user.email,
            membership_tier=user.membership_tier,
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)

    return UserProfileResponse(
        id=str(profile.id),
        email=profile.email,
        name=profile.name,
        avatar_url=profile.avatar_url,
        membership_tier=profile.membership_tier,
        subscription_expires_at=profile.subscription_expires_at,
        created_at=profile.created_at,
    )


@router.patch("/me", response_model=UserProfileResponse)
async def update_current_user_profile(
    update_data: UserProfileUpdate,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user's profile."""
    result = await db.execute(
        select(UserProfile).where(UserProfile.id == UUID(user.id))
    )
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    # Update only provided fields
    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(profile, key, value)

    await db.commit()
    await db.refresh(profile)

    return UserProfileResponse(
        id=str(profile.id),
        email=profile.email,
        name=profile.name,
        avatar_url=profile.avatar_url,
        membership_tier=profile.membership_tier,
        subscription_expires_at=profile.subscription_expires_at,
        created_at=profile.created_at,
    )


@router.get("/subscription")
async def get_subscription_status(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's subscription status."""
    result = await db.execute(
        select(UserProfile).where(UserProfile.id == UUID(user.id))
    )
    profile = result.scalar_one_or_none()

    if not profile:
        return {
            "membership_tier": "free",
            "is_active": True,
            "expires_at": None,
        }

    is_active = True
    if profile.subscription_expires_at:
        is_active = profile.subscription_expires_at > datetime.utcnow()

    return {
        "membership_tier": profile.membership_tier,
        "is_active": is_active,
        "expires_at": profile.subscription_expires_at,
    }
