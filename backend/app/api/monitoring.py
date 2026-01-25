"""Monitoring API for matching quality tracking.

Provides endpoints for:
- Matching statistics by date/region
- Recent matching failures for debugging
- Quality metrics and trends
"""
from datetime import date, datetime, timedelta
from typing import Optional, List
from pydantic import BaseModel

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.apartment import MatchingLog


router = APIRouter()


# Response Models
class MatchingStatsResponse(BaseModel):
    """Daily matching statistics."""
    date: str
    total_matches: int
    successful_matches: int
    failed_matches: int
    success_rate: float
    avg_match_score: Optional[float]
    high_confidence_count: int
    medium_confidence_count: int
    low_confidence_count: int


class MatchingFailureResponse(BaseModel):
    """Matching failure details."""
    id: int
    match_type: str
    source_id: str
    source_name: Optional[str]
    failure_reason: Optional[str]
    dong_code: Optional[str]
    created_at: datetime


class RegionalQualityResponse(BaseModel):
    """Regional matching quality metrics."""
    dong_code: str
    total_matches: int
    success_rate: float
    avg_score: Optional[float]
    avg_name_score: Optional[float]
    avg_address_score: Optional[float]


class MatchingQualityOverview(BaseModel):
    """Overall matching quality overview."""
    total_matches_today: int
    success_rate_today: float
    total_matches_week: int
    success_rate_week: float
    top_failure_reasons: List[dict]
    confidence_distribution: dict


@router.get("/matching/stats", response_model=List[MatchingStatsResponse])
async def get_matching_stats(
    start_date: date = Query(
        default=None,
        description="Start date for statistics (defaults to 7 days ago)"
    ),
    end_date: date = Query(
        default=None,
        description="End date for statistics (defaults to today)"
    ),
    region: Optional[str] = Query(
        default=None,
        description="Filter by dong_code prefix (e.g., '11680' for 강남구)"
    ),
    match_type: Optional[str] = Query(
        default=None,
        description="Filter by match type ('complex' or 'listing')"
    ),
    db: AsyncSession = Depends(get_db),
) -> List[MatchingStatsResponse]:
    """Get daily matching statistics.

    Returns aggregated statistics for matching operations including:
    - Success/failure counts
    - Average match scores
    - Confidence level distribution
    """
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=7)

    # Base query with date grouping
    query = (
        select(
            func.date(MatchingLog.created_at).label("date"),
            func.count().label("total"),
            func.sum(case((MatchingLog.success.is_(True), 1), else_=0)).label("success"),
            func.avg(MatchingLog.match_score).label("avg_score"),
            func.sum(
                case((MatchingLog.confidence == "high", 1), else_=0)
            ).label("high_conf"),
            func.sum(
                case((MatchingLog.confidence == "medium", 1), else_=0)
            ).label("medium_conf"),
            func.sum(
                case((MatchingLog.confidence == "low", 1), else_=0)
            ).label("low_conf"),
        )
        .where(
            and_(
                func.date(MatchingLog.created_at) >= start_date,
                func.date(MatchingLog.created_at) <= end_date,
            )
        )
        .group_by(func.date(MatchingLog.created_at))
        .order_by(func.date(MatchingLog.created_at).desc())
    )

    # Apply filters
    if region:
        query = query.where(MatchingLog.dong_code.like(f"{region}%"))
    if match_type:
        query = query.where(MatchingLog.match_type == match_type)

    result = await db.execute(query)
    rows = result.all()

    return [
        MatchingStatsResponse(
            date=row.date.isoformat() if row.date else "",
            total_matches=row.total or 0,
            successful_matches=row.success or 0,
            failed_matches=(row.total or 0) - (row.success or 0),
            success_rate=round(
                (row.success or 0) / row.total * 100, 1
            ) if row.total else 0,
            avg_match_score=round(float(row.avg_score), 3) if row.avg_score else None,
            high_confidence_count=row.high_conf or 0,
            medium_confidence_count=row.medium_conf or 0,
            low_confidence_count=row.low_conf or 0,
        )
        for row in rows
    ]


@router.get("/matching/failures", response_model=List[MatchingFailureResponse])
async def get_recent_failures(
    limit: int = Query(default=100, le=500, description="Maximum results"),
    match_type: Optional[str] = Query(
        default=None, description="Filter by match type"
    ),
    region: Optional[str] = Query(
        default=None, description="Filter by dong_code prefix"
    ),
    db: AsyncSession = Depends(get_db),
) -> List[MatchingFailureResponse]:
    """Get recent matching failures for debugging.

    Returns details about failed matching attempts including
    source information and failure reasons.
    """
    query = (
        select(MatchingLog)
        .where(MatchingLog.success.is_(False))
        .order_by(MatchingLog.created_at.desc())
        .limit(limit)
    )

    if match_type:
        query = query.where(MatchingLog.match_type == match_type)
    if region:
        query = query.where(MatchingLog.dong_code.like(f"{region}%"))

    result = await db.execute(query)
    logs = result.scalars().all()

    return [
        MatchingFailureResponse(
            id=log.id,
            match_type=log.match_type,
            source_id=log.source_id,
            source_name=log.source_name,
            failure_reason=log.failure_reason,
            dong_code=log.dong_code,
            created_at=log.created_at,
        )
        for log in logs
    ]


@router.get("/matching/quality", response_model=MatchingQualityOverview)
async def get_quality_metrics(
    db: AsyncSession = Depends(get_db),
) -> MatchingQualityOverview:
    """Get overall matching quality metrics.

    Returns an overview of matching performance including:
    - Today's and weekly metrics
    - Top failure reasons
    - Confidence level distribution
    """
    today = date.today()
    week_ago = today - timedelta(days=7)

    # Today's stats
    today_query = (
        select(
            func.count().label("total"),
            func.sum(case((MatchingLog.success.is_(True), 1), else_=0)).label("success"),
        )
        .where(func.date(MatchingLog.created_at) == today)
    )
    today_result = await db.execute(today_query)
    today_row = today_result.first()

    today_total = today_row.total or 0
    today_success = today_row.success or 0
    today_rate = round(today_success / today_total * 100, 1) if today_total else 0

    # Week stats
    week_query = (
        select(
            func.count().label("total"),
            func.sum(case((MatchingLog.success.is_(True), 1), else_=0)).label("success"),
        )
        .where(func.date(MatchingLog.created_at) >= week_ago)
    )
    week_result = await db.execute(week_query)
    week_row = week_result.first()

    week_total = week_row.total or 0
    week_success = week_row.success or 0
    week_rate = round(week_success / week_total * 100, 1) if week_total else 0

    # Top failure reasons (last 7 days)
    failure_query = (
        select(
            MatchingLog.failure_reason,
            func.count().label("count"),
        )
        .where(
            and_(
                MatchingLog.success.is_(False),
                func.date(MatchingLog.created_at) >= week_ago,
                MatchingLog.failure_reason.isnot(None),
            )
        )
        .group_by(MatchingLog.failure_reason)
        .order_by(func.count().desc())
        .limit(5)
    )
    failure_result = await db.execute(failure_query)
    top_failures = [
        {"reason": row.failure_reason, "count": row.count}
        for row in failure_result.all()
    ]

    # Confidence distribution (last 7 days)
    conf_query = (
        select(
            MatchingLog.confidence,
            func.count().label("count"),
        )
        .where(
            and_(
                MatchingLog.success.is_(True),
                func.date(MatchingLog.created_at) >= week_ago,
            )
        )
        .group_by(MatchingLog.confidence)
    )
    conf_result = await db.execute(conf_query)
    confidence_dist = {
        row.confidence: row.count
        for row in conf_result.all()
        if row.confidence
    }

    return MatchingQualityOverview(
        total_matches_today=today_total,
        success_rate_today=today_rate,
        total_matches_week=week_total,
        success_rate_week=week_rate,
        top_failure_reasons=top_failures,
        confidence_distribution=confidence_dist,
    )


@router.get("/matching/regions", response_model=List[RegionalQualityResponse])
async def get_regional_quality(
    days: int = Query(default=7, le=30, description="Days to analyze"),
    min_matches: int = Query(default=10, description="Minimum matches to include"),
    db: AsyncSession = Depends(get_db),
) -> List[RegionalQualityResponse]:
    """Get matching quality metrics by region.

    Returns regional breakdown of matching performance
    to identify areas with poor matching rates.
    """
    cutoff = date.today() - timedelta(days=days)

    query = (
        select(
            func.substr(MatchingLog.dong_code, 1, 5).label("dong_prefix"),
            func.count().label("total"),
            func.sum(case((MatchingLog.success.is_(True), 1), else_=0)).label("success"),
            func.avg(MatchingLog.match_score).label("avg_score"),
            func.avg(MatchingLog.name_score).label("avg_name"),
            func.avg(MatchingLog.address_score).label("avg_addr"),
        )
        .where(
            and_(
                func.date(MatchingLog.created_at) >= cutoff,
                MatchingLog.dong_code.isnot(None),
            )
        )
        .group_by(func.substr(MatchingLog.dong_code, 1, 5))
        .having(func.count() >= min_matches)
        .order_by(func.count().desc())
    )

    result = await db.execute(query)
    rows = result.all()

    return [
        RegionalQualityResponse(
            dong_code=row.dong_prefix or "",
            total_matches=row.total or 0,
            success_rate=round(
                (row.success or 0) / row.total * 100, 1
            ) if row.total else 0,
            avg_score=round(float(row.avg_score), 3) if row.avg_score else None,
            avg_name_score=round(float(row.avg_name), 3) if row.avg_name else None,
            avg_address_score=round(float(row.avg_addr), 3) if row.avg_addr else None,
        )
        for row in rows
    ]
