"""Apartments API endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.models.apartment import Apartment


router = APIRouter()


class ApartmentResponse(BaseModel):
    """Apartment response schema."""
    id: int
    naver_complex_no: Optional[str] = None
    name: str
    address: Optional[str] = None
    dong_code: Optional[str] = None
    total_units: Optional[int] = None
    built_year: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    class Config:
        from_attributes = True


class ApartmentCreate(BaseModel):
    """Apartment creation schema."""
    naver_complex_no: Optional[str] = None
    name: str
    address: Optional[str] = None
    dong_code: Optional[str] = None
    total_units: Optional[int] = None
    built_year: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


@router.get("/", response_model=List[ApartmentResponse])
async def list_apartments(
    dong_code: Optional[str] = Query(None, description="Filter by dong code"),
    name: Optional[str] = Query(None, description="Search by name"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List apartments with optional filters."""
    query = select(Apartment)

    if dong_code:
        query = query.where(Apartment.dong_code == dong_code)
    if name:
        query = query.where(Apartment.name.ilike(f"%{name}%"))

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    apartments = result.scalars().all()

    return apartments


@router.get("/{apartment_id}", response_model=ApartmentResponse)
async def get_apartment(
    apartment_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get apartment by ID."""
    result = await db.execute(
        select(Apartment).where(Apartment.id == apartment_id)
    )
    apartment = result.scalar_one_or_none()

    if not apartment:
        raise HTTPException(status_code=404, detail="Apartment not found")

    return apartment


@router.post("/", response_model=ApartmentResponse)
async def create_apartment(
    data: ApartmentCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new apartment."""
    apartment = Apartment(**data.model_dump())
    db.add(apartment)
    await db.flush()
    await db.refresh(apartment)

    return apartment
