"""네이버 부동산 호가 데이터 수집 스크립트.

모바일 API를 사용하여 호가 데이터를 수집합니다.
SQLite에 저장된 아파트 정보와 매칭하여 저장합니다.

개선 사항:
- 세션 초기화 (쿠키 획득)로 차단 회피
- 지역 순서 랜덤화로 패턴 회피
- 보수적인 요청 간격 설정
- 개선된 매칭 모듈 사용 (이름+주소+면적 복합 매칭)
- 매칭 품질 로깅

Usage:
    python scripts/collect_naver_listings.py
"""
import asyncio
import sqlite3
import sys
import logging
import random
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import List, Dict, Optional
from difflib import SequenceMatcher

# Add backend directory to path
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.crawler.naver import NaverRealEstateCrawler, NaverListing
from app.crawler.anti_abuse import AntiAbuseManager, RequestDelay
from app.matching import MatchingService, MatchingConfig, MatchResult
from app.matching.name_matcher import NameMatcher
from app.models.apartment import MatchingLog

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# SQLite database URL
DATABASE_URL = "sqlite+aiosqlite:///./chat_apt.db"

# 서울 주요 지역 좌표 범위 (dong_code -> bounds)
REGION_BOUNDS = {
    # 강남구
    "11680": {"btm": 37.4700, "lft": 127.0200, "top": 37.5200, "rgt": 127.0900, "cortarNo": "1168000000"},
    # 서초구
    "11650": {"btm": 37.4600, "lft": 126.9800, "top": 37.5100, "rgt": 127.0500, "cortarNo": "1165000000"},
    # 송파구
    "11710": {"btm": 37.4800, "lft": 127.0800, "top": 37.5400, "rgt": 127.1500, "cortarNo": "1171000000"},
    # 강동구
    "11740": {"btm": 37.5200, "lft": 127.1100, "top": 37.5700, "rgt": 127.1700, "cortarNo": "1174000000"},
    # 마포구
    "11440": {"btm": 37.5300, "lft": 126.8900, "top": 37.5800, "rgt": 126.9600, "cortarNo": "1144000000"},
    # 용산구
    "11170": {"btm": 37.5200, "lft": 126.9600, "top": 37.5500, "rgt": 127.0100, "cortarNo": "1117000000"},
}


# Initialize matching service with improved configuration
MATCHING_CONFIG = MatchingConfig(
    name_weight=0.5,
    address_weight=0.3,
    area_weight=0.2,
    high_confidence_threshold=0.85,
    medium_confidence_threshold=0.7,
    min_match_threshold=0.6,
    name_min_score=0.6,
)
MATCHING_SERVICE = MatchingService(config=MATCHING_CONFIG)


# Legacy functions kept for backwards compatibility
def normalize_name(name: str) -> str:
    """Normalize apartment name for comparison (legacy)."""
    return MATCHING_SERVICE.name_matcher.normalize_name(name)


def similarity_score(name1: str, name2: str) -> float:
    """Calculate similarity between two apartment names (legacy)."""
    return MATCHING_SERVICE.name_matcher.calculate_similarity(name1, name2)


async def get_apartments_by_dong(session: AsyncSession, dong_code: str) -> List[Dict]:
    """Get apartments for a specific dong code."""
    result = await session.execute(
        text("""
            SELECT id, name, naver_complex_no, dong_code
            FROM apartments
            WHERE dong_code = :dong_code
        """),
        {"dong_code": dong_code}
    )
    return [
        {"id": row[0], "name": row[1], "naver_complex_no": row[2], "dong_code": row[3]}
        for row in result.fetchall()
    ]


async def save_listing(
    session: AsyncSession,
    apartment_id: int,
    listing: NaverListing
) -> bool:
    """Save a listing to database. Returns True if new."""
    # Check if listing exists
    result = await session.execute(
        text("SELECT id FROM listings WHERE article_no = :article_no"),
        {"article_no": listing.article_no}
    )
    existing = result.scalar_one_or_none()

    if existing:
        await session.execute(
            text("""
                UPDATE listings SET
                    price = :price,
                    naver_complex_no = :naver_complex_no,
                    is_active = 1,
                    updated_at = :updated_at
                WHERE article_no = :article_no
            """),
            {
                "price": listing.price,
                "naver_complex_no": listing.complex_no,
                "updated_at": datetime.utcnow(),
                "article_no": listing.article_no,
            }
        )
        return False

    # Parse floor
    floor = None
    if listing.floor:
        try:
            floor_str = listing.floor.split('/')[0]
            floor = int(floor_str)
        except (ValueError, IndexError):
            pass

    await session.execute(
        text("""
            INSERT INTO listings
            (apartment_id, article_no, naver_complex_no, trade_type, price, area, floor,
             direction, description, realtor_name, is_active, created_at, updated_at)
            VALUES
            (:apartment_id, :article_no, :naver_complex_no, :trade_type, :price, :area, :floor,
             :direction, :description, :realtor_name, 1, :created_at, :updated_at)
        """),
        {
            "apartment_id": apartment_id,
            "article_no": listing.article_no,
            "naver_complex_no": listing.complex_no,
            "trade_type": listing.trade_type,
            "price": listing.price,
            "area": listing.area_exclusive,
            "floor": floor,
            "direction": listing.direction,
            "description": listing.description,
            "realtor_name": listing.realtor_name,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
    )
    return True


async def match_listing_to_apartment(
    listing: NaverListing,
    apartments: List[Dict],
    dong_code: str,
) -> tuple[Optional[int], Optional[MatchResult]]:
    """Match a listing to an apartment using improved matching.

    Returns:
        Tuple of (apartment_id, match_result)
    """
    best_match = None
    best_result = None
    best_score = 0.0

    for apt in apartments:
        result = MATCHING_SERVICE.match(
            source_name=listing.complex_name,
            target_name=apt["name"],
            source_dong_code=dong_code,
            target_dong_code=apt.get("dong_code"),
            source_area=listing.area_exclusive,
            target_apartment_id=apt["id"],
        )

        if result.total_score > best_score:
            best_score = result.total_score
            best_match = apt["id"]
            best_result = result

    if best_result and best_result.total_score >= MATCHING_CONFIG.min_match_threshold:
        return (best_match, best_result)

    return (None, best_result)


async def log_matching_result(
    session: AsyncSession,
    listing: NaverListing,
    dong_code: str,
    match_result: Optional[MatchResult],
    success: bool,
    failure_reason: Optional[str] = None,
):
    """Log matching result for monitoring."""
    try:
        await session.execute(
            text("""
                INSERT INTO matching_logs
                (match_type, source_id, source_name, target_id, target_name,
                 name_score, address_score, area_score, match_score,
                 match_method, confidence, success, failure_reason, dong_code, created_at)
                VALUES
                (:match_type, :source_id, :source_name, :target_id, :target_name,
                 :name_score, :address_score, :area_score, :match_score,
                 :match_method, :confidence, :success, :failure_reason, :dong_code, :created_at)
            """),
            {
                "match_type": "listing",
                "source_id": listing.article_no,
                "source_name": listing.complex_name,
                "target_id": match_result.apartment_id if match_result else None,
                "target_name": match_result.target_name if match_result else None,
                "name_score": match_result.name_score if match_result else None,
                "address_score": match_result.address_score if match_result else None,
                "area_score": match_result.area_score if match_result else None,
                "match_score": match_result.total_score if match_result else None,
                "match_method": match_result.match_method if match_result else None,
                "confidence": match_result.confidence.value if match_result else None,
                "success": success,
                "failure_reason": failure_reason,
                "dong_code": dong_code,
                "created_at": datetime.utcnow(),
            }
        )
    except Exception as e:
        logger.debug(f"Failed to log matching result: {e}")


async def main():
    """Main collection job."""
    logger.info("=" * 60)
    logger.info("네이버 부동산 호가 데이터 수집 (모바일 API)")
    logger.info("=" * 60)

    # Initialize database
    engine = create_async_engine(DATABASE_URL, echo=False)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Create listings table if not exists
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                apartment_id INTEGER NOT NULL,
                article_no VARCHAR(30) UNIQUE,
                naver_complex_no VARCHAR(20),
                trade_type VARCHAR(10),
                price INTEGER NOT NULL,
                area DECIMAL(10, 2),
                floor INTEGER,
                direction VARCHAR(20),
                description TEXT,
                realtor_name VARCHAR(50),
                realtor_phone VARCHAR(20),
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY(apartment_id) REFERENCES apartments(id)
            )
        """))

        # Create matching_logs table for monitoring
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS matching_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_type VARCHAR(50) NOT NULL,
                source_id VARCHAR(100) NOT NULL,
                source_name VARCHAR(200),
                target_id INTEGER,
                target_name VARCHAR(200),
                name_score DECIMAL(5, 3),
                address_score DECIMAL(5, 3),
                area_score DECIMAL(5, 3),
                match_score DECIMAL(5, 3),
                match_method VARCHAR(50),
                confidence VARCHAR(20),
                success BOOLEAN NOT NULL DEFAULT 0,
                failure_reason VARCHAR(500),
                dong_code VARCHAR(10),
                created_at DATETIME NOT NULL
            )
        """))

    total_stats = {"listings_new": 0, "listings_updated": 0, "matched": 0, "unmatched": 0}

    # Configure anti-abuse with more conservative settings
    delay_config = RequestDelay(
        min_delay=5.0,
        max_delay=10.0,
        mean=7.0,
        std_dev=2.0
    )
    anti_abuse = AntiAbuseManager(request_delay=delay_config)

    # Randomize region order to avoid pattern detection
    dong_codes = list(REGION_BOUNDS.keys())
    random.shuffle(dong_codes)
    logger.info(f"지역 순서 랜덤화: {dong_codes}")

    async with session_maker() as session:
        async with NaverRealEstateCrawler(anti_abuse=anti_abuse) as crawler:
            # Initialize session first (get cookies)
            if not await crawler.init_session():
                logger.error("세션 초기화 실패. 중단합니다.")
                await engine.dispose()
                return

            for dong_code in dong_codes:
                bounds_info = REGION_BOUNDS[dong_code]
                logger.info(f"\n{'='*40}")
                logger.info(f"지역: {dong_code} (cortarNo: {bounds_info['cortarNo']})")
                logger.info(f"{'='*40}")

                # Get apartments for matching
                apartments = await get_apartments_by_dong(session, dong_code)
                logger.info(f"DB 아파트: {len(apartments)}개")

                if not apartments:
                    logger.info("매칭할 아파트가 없습니다. 스킵합니다.")
                    continue

                # Fetch listings using mobile API
                bounds = {
                    "btm": bounds_info["btm"],
                    "lft": bounds_info["lft"],
                    "top": bounds_info["top"],
                    "rgt": bounds_info["rgt"],
                }

                try:
                    listings = await crawler.get_all_listings_by_region_mobile(
                        cortarNo=bounds_info["cortarNo"],
                        trade_types="A1",  # 매매만
                        bounds=bounds,
                        max_pages=10,
                        delay=5.0,
                    )
                    logger.info(f"수집된 호가: {len(listings)}건")

                except Exception as e:
                    logger.error(f"수집 오류: {e}")
                    continue

                # Match and save listings with improved matching
                for listing in listings:
                    apt_id, match_result = await match_listing_to_apartment(
                        listing, apartments, dong_code
                    )

                    if apt_id:
                        is_new = await save_listing(session, apt_id, listing)
                        if is_new:
                            total_stats["listings_new"] += 1
                        else:
                            total_stats["listings_updated"] += 1
                        total_stats["matched"] += 1

                        # Log successful match
                        await log_matching_result(
                            session, listing, dong_code, match_result,
                            success=True
                        )

                        if match_result:
                            logger.debug(
                                f"  매칭: {listing.complex_name} → "
                                f"{match_result.target_name} "
                                f"(score={match_result.total_score:.2f}, "
                                f"conf={match_result.confidence.value})"
                            )
                    else:
                        total_stats["unmatched"] += 1

                        # Log failed match
                        failure_reason = "No match found above threshold"
                        if match_result:
                            failure_reason = (
                                f"Best score {match_result.total_score:.2f} "
                                f"< threshold {MATCHING_CONFIG.min_match_threshold}"
                            )
                        await log_matching_result(
                            session, listing, dong_code, match_result,
                            success=False, failure_reason=failure_reason
                        )

                await session.commit()

                # Longer rate limiting between regions (randomized)
                region_delay = random.uniform(15, 25)
                logger.info(f"지역 처리 완료. {region_delay:.1f}초 대기...")
                await asyncio.sleep(region_delay)

        # Final stats
        listing_count = await session.execute(text("SELECT COUNT(*) FROM listings"))
        listing_total = listing_count.scalar()

        # Get matching quality stats for this run
        match_stats = await session.execute(text("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success,
                AVG(match_score) as avg_score
            FROM matching_logs
            WHERE created_at > datetime('now', '-1 hour')
        """))
        match_row = match_stats.first()

    logger.info("\n" + "=" * 60)
    logger.info("수집 완료!")
    logger.info(f"  - 새 호가: {total_stats['listings_new']}건")
    logger.info(f"  - 업데이트된 호가: {total_stats['listings_updated']}건")
    logger.info(f"  - 매칭 성공: {total_stats['matched']}건")
    logger.info(f"  - 매칭 실패: {total_stats['unmatched']}건")
    if total_stats['matched'] + total_stats['unmatched'] > 0:
        match_rate = total_stats['matched'] / (total_stats['matched'] + total_stats['unmatched']) * 100
        logger.info(f"  - 매칭률: {match_rate:.1f}%")
    if match_row and match_row.avg_score:
        logger.info(f"  - 평균 매칭 점수: {match_row.avg_score:.3f}")
    logger.info(f"  - 전체 호가: {listing_total}건")
    logger.info("=" * 60)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
