"""Search API endpoints using OpenSearch."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.services.opensearch import (
    OpenSearchClient,
    ApartmentSearchService,
    ListingSearchService,
    TransactionAnalyticsService,
    get_opensearch_client,
)

router = APIRouter()


# Request/Response models
class SearchFilters(BaseModel):
    """Common search filters."""
    dong_code: Optional[str] = None
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    min_area: Optional[float] = None
    max_area: Optional[float] = None


class ApartmentSearchResponse(BaseModel):
    """Apartment search response."""
    id: int
    name: str
    address: Optional[str] = None
    dong_code: Optional[str] = None
    total_units: Optional[int] = None
    built_year: Optional[int] = None


class ListingSearchResponse(BaseModel):
    """Listing search response."""
    id: int
    apartment_id: int
    apartment_name: Optional[str] = None
    price: int
    area: Optional[float] = None
    floor: Optional[int] = None
    trade_type: Optional[str] = None
    discount_rate: Optional[float] = None
    recommendation_score: Optional[float] = None


class PriceStats(BaseModel):
    """Price statistics."""
    avg: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    count: Optional[int] = None


class SearchResults(BaseModel):
    """Search results wrapper."""
    total: int
    items: List[dict]
    took_ms: int = 0


class PriceTrendItem(BaseModel):
    """Price trend data point."""
    year: int
    avg_price: Optional[float] = None
    max_price: Optional[float] = None
    min_price: Optional[float] = None
    count: Optional[int] = None


# Dependency to get OpenSearch client
async def get_opensearch():
    """Get connected OpenSearch client."""
    client = get_opensearch_client()
    try:
        await client.connect()
        yield client
    finally:
        await client.close()


@router.get("/apartments")
async def search_apartments(
    q: str = Query(..., description="Search query"),
    dong_code: Optional[str] = Query(None, description="Region code"),
    size: int = Query(20, ge=1, le=100),
    client: OpenSearchClient = Depends(get_opensearch),
):
    """Search apartments by name.

    - **q**: Search term (apartment name)
    - **dong_code**: Optional region filter
    - **size**: Number of results (default 20, max 100)
    """
    service = ApartmentSearchService(client)

    try:
        result = await service.search_by_name(
            name=q,
            dong_code=dong_code,
            size=size
        )

        return SearchResults(
            total=result.total,
            items=result.hits,
            took_ms=result.took_ms
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/apartments/nearby")
async def search_apartments_nearby(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    distance_km: float = Query(1.0, ge=0.1, le=10.0, description="Search radius in km"),
    size: int = Query(20, ge=1, le=100),
    client: OpenSearchClient = Depends(get_opensearch),
):
    """Search apartments near a location.

    - **lat**: Latitude
    - **lon**: Longitude
    - **distance_km**: Search radius (default 1km, max 10km)
    """
    service = ApartmentSearchService(client)

    try:
        result = await service.search_by_location(
            lat=lat,
            lon=lon,
            distance_km=distance_km,
            size=size
        )

        return SearchResults(
            total=result.total,
            items=result.hits,
            took_ms=result.took_ms
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/listings")
async def search_listings(
    dong_code: Optional[str] = Query(None, description="Region code"),
    min_price: Optional[int] = Query(None, description="Minimum price (만원)"),
    max_price: Optional[int] = Query(None, description="Maximum price (만원)"),
    min_area: Optional[float] = Query(None, description="Minimum area (㎡)"),
    max_area: Optional[float] = Query(None, description="Maximum area (㎡)"),
    trade_type: Optional[str] = Query(None, description="Trade type (A1: 매매, B1: 전세)"),
    only_active: bool = Query(True, description="Only active listings"),
    min_discount_rate: Optional[float] = Query(None, description="Minimum discount rate (negative = discount)"),
    sort_by: str = Query("recommendation_score", description="Sort field"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    client: OpenSearchClient = Depends(get_opensearch),
):
    """Search listings with filters.

    - **dong_code**: Region filter
    - **min_price/max_price**: Price range (unit: 만원)
    - **min_area/max_area**: Area range (unit: ㎡)
    - **trade_type**: A1=매매, B1=전세
    - **min_discount_rate**: Filter by discount (e.g., -5.0 for 5% discount)
    - **sort_by**: recommendation_score, price_asc, price_desc, discount_rate, newest
    """
    service = ListingSearchService(client)

    try:
        result = await service.search_listings(
            dong_code=dong_code,
            min_price=min_price,
            max_price=max_price,
            min_area=min_area,
            max_area=max_area,
            trade_type=trade_type,
            only_active=only_active,
            min_discount_rate=min_discount_rate,
            sort_by=sort_by,
            size=size,
            from_=(page - 1) * size
        )

        return SearchResults(
            total=result.total,
            items=result.hits,
            took_ms=result.took_ms
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/listings/undervalued")
async def get_undervalued_listings(
    dong_code: Optional[str] = Query(None, description="Region code"),
    min_discount_rate: float = Query(-5.0, description="Minimum discount rate"),
    size: int = Query(20, ge=1, le=100),
    client: OpenSearchClient = Depends(get_opensearch),
):
    """Get undervalued listings (discounted compared to similar properties).

    - **dong_code**: Region filter
    - **min_discount_rate**: Discount threshold (default -5.0 = 5% discount)
    """
    service = ListingSearchService(client)

    try:
        result = await service.get_undervalued_listings(
            dong_code=dong_code,
            min_discount_rate=min_discount_rate,
            size=size
        )

        return SearchResults(
            total=result.total,
            items=result.hits,
            took_ms=result.took_ms
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/analytics/price-distribution/{dong_code}")
async def get_price_distribution(
    dong_code: str,
    interval: int = Query(10000, description="Price interval (만원)"),
    client: OpenSearchClient = Depends(get_opensearch),
):
    """Get price distribution histogram for a region.

    - **dong_code**: Region code
    - **interval**: Price bucket size (default 10000 = 1억)
    """
    service = ListingSearchService(client)

    try:
        result = await service.get_price_distribution(
            dong_code=dong_code,
            interval=interval
        )

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analytics failed: {str(e)}")


@router.get("/analytics/price-trend/{apartment_id}")
async def get_price_trend(
    apartment_id: int,
    years: int = Query(5, ge=1, le=10, description="Number of years"),
    client: OpenSearchClient = Depends(get_opensearch),
):
    """Get price trend for an apartment.

    - **apartment_id**: Apartment ID
    - **years**: Historical period (default 5 years)
    """
    service = TransactionAnalyticsService(client)

    try:
        result = await service.get_price_trend(
            apartment_id=apartment_id,
            years=years
        )

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analytics failed: {str(e)}")


@router.get("/analytics/region-stats/{dong_code}")
async def get_region_stats(
    dong_code: str,
    year: Optional[int] = Query(None, description="Filter by year"),
    client: OpenSearchClient = Depends(get_opensearch),
):
    """Get transaction statistics for a region.

    - **dong_code**: Region code
    - **year**: Optional year filter
    """
    service = TransactionAnalyticsService(client)

    try:
        result = await service.get_region_price_stats(
            dong_code=dong_code,
            year=year
        )

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analytics failed: {str(e)}")


@router.get("/analytics/compare")
async def compare_apartments(
    apartment_ids: str = Query(..., description="Comma-separated apartment IDs"),
    year: Optional[int] = Query(None, description="Filter by year"),
    client: OpenSearchClient = Depends(get_opensearch),
):
    """Compare transaction data for multiple apartments.

    - **apartment_ids**: Comma-separated list (e.g., "1,2,3")
    - **year**: Optional year filter
    """
    try:
        ids = [int(x.strip()) for x in apartment_ids.split(",")]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid apartment IDs")

    if len(ids) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 apartments allowed")

    service = TransactionAnalyticsService(client)

    try:
        result = await service.compare_similar_apartments(
            apartment_ids=ids,
            year=year
        )

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analytics failed: {str(e)}")
