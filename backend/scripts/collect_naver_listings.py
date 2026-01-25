"""네이버 부동산 호가 데이터 수집 스크립트.

모바일 API를 사용하여 호가 데이터를 수집합니다.
SQLite에 저장된 아파트 정보와 매칭하여 저장합니다.

개선 사항:
- 세션 초기화 (쿠키 획득)로 차단 회피
- 지역 순서 랜덤화로 패턴 회피
- 보수적인 요청 간격 설정

Usage:
    python scripts/collect_naver_listings.py
"""
import asyncio
import sqlite3
import sys
import logging
import random
from datetime import datetime
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


def normalize_name(name: str) -> str:
    """Normalize apartment name for comparison."""
    import re
    name = name.strip()
    name = re.sub(r'\([^)]*\)', '', name)
    for suffix in ['아파트', '단지', '차', '동']:
        name = name.replace(suffix, '')
    name = re.sub(r'[^가-힣a-zA-Z0-9]', '', name)
    return name.lower()


def similarity_score(name1: str, name2: str) -> float:
    """Calculate similarity between two apartment names."""
    n1 = normalize_name(name1)
    n2 = normalize_name(name2)
    return SequenceMatcher(None, n1, n2).ratio()


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
    apartments: List[Dict]
) -> Optional[int]:
    """Match a listing to an apartment by name similarity."""
    best_match = None
    best_score = 0

    for apt in apartments:
        score = similarity_score(listing.complex_name, apt["name"])
        if score > best_score and score >= 0.6:
            best_score = score
            best_match = apt["id"]

    return best_match


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

                # Match and save listings
                for listing in listings:
                    apt_id = await match_listing_to_apartment(listing, apartments)

                    if apt_id:
                        is_new = await save_listing(session, apt_id, listing)
                        if is_new:
                            total_stats["listings_new"] += 1
                        else:
                            total_stats["listings_updated"] += 1
                        total_stats["matched"] += 1
                    else:
                        total_stats["unmatched"] += 1

                await session.commit()

                # Longer rate limiting between regions (randomized)
                region_delay = random.uniform(15, 25)
                logger.info(f"지역 처리 완료. {region_delay:.1f}초 대기...")
                await asyncio.sleep(region_delay)

        # Final stats
        listing_count = await session.execute(text("SELECT COUNT(*) FROM listings"))

    logger.info("\n" + "=" * 60)
    logger.info("수집 완료!")
    logger.info(f"  - 새 호가: {total_stats['listings_new']}건")
    logger.info(f"  - 업데이트된 호가: {total_stats['listings_updated']}건")
    logger.info(f"  - 매칭 성공: {total_stats['matched']}건")
    logger.info(f"  - 매칭 실패: {total_stats['unmatched']}건")
    logger.info(f"  - 전체 호가: {listing_count.scalar()}건")
    logger.info("=" * 60)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
