"""아파트 이름으로 네이버 complex_no 수집 스크립트.

네이버 검색 API를 사용하여 아파트 이름으로 검색하고 complex_no를 업데이트합니다.

Usage:
    python scripts/collect_complex_no_by_search.py
"""
import asyncio
import sqlite3
import sys
import logging
import random
from pathlib import Path
from difflib import SequenceMatcher

# Add backend directory to path
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

import httpx

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Naver search API
SEARCH_URL = "https://new.land.naver.com/api/search"


def normalize_name(name: str) -> str:
    """Normalize apartment name for comparison."""
    import re
    name = name.strip()
    # Remove parentheses content
    name = re.sub(r'\([^)]*\)', '', name)
    # Remove common suffixes
    for suffix in ['아파트', '단지', '차', '동', '주상복합']:
        name = name.replace(suffix, '')
    # Remove non-alphanumeric characters
    name = re.sub(r'[^가-힣a-zA-Z0-9]', '', name)
    return name.lower()


def similarity_score(name1: str, name2: str) -> float:
    """Calculate similarity between two apartment names."""
    n1 = normalize_name(name1)
    n2 = normalize_name(name2)
    return SequenceMatcher(None, n1, n2).ratio()


async def search_complex(client: httpx.AsyncClient, keyword: str):
    """Search for apartment complex by keyword."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://new.land.naver.com/",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    params = {
        "keyword": keyword,
    }

    try:
        response = await client.get(SEARCH_URL, params=params, headers=headers)

        if response.status_code == 200:
            data = response.json()
            # complexes is the list of matching apartment complexes
            complexes = data.get("complexes", [])
            return complexes
        elif response.status_code == 429:
            logger.warning(f"Rate limited for: {keyword}")
            return "RATE_LIMITED"
        else:
            logger.debug(f"Search failed for {keyword}: {response.status_code}")
            return []

    except Exception as e:
        logger.error(f"Error searching {keyword}: {e}")
        return []


async def main():
    """Main job."""
    logger.info("=" * 60)
    logger.info("네이버 검색 API로 아파트 complex_no 수집")
    logger.info("=" * 60)

    # Connect to database
    conn = sqlite3.connect(str(BACKEND_DIR / "chat_apt.db"))
    cursor = conn.cursor()

    # Get apartments without naver_complex_no
    cursor.execute("""
        SELECT id, name, address
        FROM apartments
        WHERE naver_complex_no IS NULL
        ORDER BY id
    """)
    apartments = cursor.fetchall()

    logger.info(f"업데이트 대상 아파트: {len(apartments)}개")

    if not apartments:
        logger.info("업데이트할 아파트가 없습니다.")
        conn.close()
        return

    updated = 0
    failed = 0
    rate_limited = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        for apt_id, apt_name, apt_address in apartments:
            # Search by apartment name
            result = await search_complex(client, apt_name)

            if result == "RATE_LIMITED":
                rate_limited += 1
                # Wait longer and retry once
                logger.info(f"Rate limited. Waiting 60 seconds...")
                await asyncio.sleep(60)
                result = await search_complex(client, apt_name)

                if result == "RATE_LIMITED":
                    logger.warning(f"Still rate limited. Skipping: {apt_name}")
                    failed += 1
                    continue

            if not result:
                # Try with address if name search fails
                if apt_address:
                    # Extract district from address (e.g., "서울시 강남구 삼성동" -> "강남구")
                    address_parts = apt_address.split()
                    search_term = f"{apt_name} {address_parts[1] if len(address_parts) > 1 else ''}"
                    result = await search_complex(client, search_term.strip())

            if result and result != "RATE_LIMITED":
                # Find best matching complex
                best_match = None
                best_score = 0

                for complex_info in result:
                    complex_name = complex_info.get("complexName", "")
                    score = similarity_score(apt_name, complex_name)

                    if score > best_score and score >= 0.6:
                        best_score = score
                        best_match = complex_info

                if best_match:
                    complex_no = str(best_match.get("complexNo", ""))
                    if complex_no:
                        cursor.execute(
                            """UPDATE apartments
                               SET naver_complex_no = ?,
                                   latitude = COALESCE(latitude, ?),
                                   longitude = COALESCE(longitude, ?)
                               WHERE id = ?""",
                            (complex_no,
                             best_match.get("latitude"),
                             best_match.get("longitude"),
                             apt_id)
                        )
                        conn.commit()
                        updated += 1
                        logger.info(f"[{updated}] 매칭: {apt_name} -> {best_match.get('complexName')} (complex_no={complex_no}, score={best_score:.2f})")
                    else:
                        failed += 1
                        logger.debug(f"No complex_no in result: {apt_name}")
                else:
                    failed += 1
                    logger.debug(f"No match found: {apt_name}")
            else:
                failed += 1
                logger.debug(f"No search result: {apt_name}")

            # Rate limiting - random delay between 2-5 seconds
            delay = random.uniform(2, 5)
            await asyncio.sleep(delay)

            # Log progress every 50 apartments
            if (updated + failed) % 50 == 0:
                logger.info(f"진행률: {updated + failed}/{len(apartments)} (성공: {updated}, 실패: {failed})")

    conn.close()

    logger.info("\n" + "=" * 60)
    logger.info("수집 완료!")
    logger.info(f"  - 성공: {updated}건")
    logger.info(f"  - 실패: {failed}건")
    logger.info(f"  - Rate Limited: {rate_limited}건")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
