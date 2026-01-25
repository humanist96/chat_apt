"""기존 매물 데이터에 naver_complex_no 업데이트.

네이버 API를 사용하여 article_no로 complex_no를 조회하고 업데이트합니다.

Usage:
    python scripts/update_complex_no.py
"""
import asyncio
import sqlite3
import sys
import logging
import random
from datetime import datetime
from pathlib import Path

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

# Naver API endpoint
ARTICLE_DETAIL_URL = "https://new.land.naver.com/api/articles/{article_no}"


async def get_complex_no_from_naver(client: httpx.AsyncClient, article_no: str):
    """Get complex_no from Naver API using article_no."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://new.land.naver.com",
        "Accept": "application/json",
    }

    try:
        url = ARTICLE_DETAIL_URL.format(article_no=article_no)
        response = await client.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            article_detail = data.get("articleDetail", {})
            complex_no = article_detail.get("complexNo")
            return str(complex_no) if complex_no else None
        elif response.status_code == 429:
            logger.warning("Rate limited. Waiting...")
            return "RATE_LIMITED"
        else:
            logger.debug(f"Failed to get complex_no for {article_no}: {response.status_code}")
            return None

    except Exception as e:
        logger.error(f"Error fetching {article_no}: {e}")
        return None


async def main():
    """Main update job."""
    logger.info("=" * 60)
    logger.info("기존 매물 데이터 naver_complex_no 업데이트")
    logger.info("=" * 60)

    # Connect to database
    conn = sqlite3.connect(str(BACKEND_DIR / "chat_apt.db"))
    cursor = conn.cursor()

    # Get listings without complex_no
    cursor.execute("""
        SELECT id, article_no
        FROM listings
        WHERE naver_complex_no IS NULL AND article_no IS NOT NULL
        LIMIT 100
    """)
    listings = cursor.fetchall()

    logger.info(f"업데이트 대상 매물: {len(listings)}건")

    if not listings:
        logger.info("업데이트할 매물이 없습니다.")
        conn.close()
        return

    updated = 0
    failed = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        for listing_id, article_no in listings:
            complex_no = await get_complex_no_from_naver(client, article_no)

            if complex_no == "RATE_LIMITED":
                # Wait and retry
                await asyncio.sleep(30)
                complex_no = await get_complex_no_from_naver(client, article_no)

            if complex_no and complex_no != "RATE_LIMITED":
                cursor.execute(
                    "UPDATE listings SET naver_complex_no = ? WHERE id = ?",
                    (complex_no, listing_id)
                )
                conn.commit()
                updated += 1
                logger.info(f"Updated listing {listing_id}: article_no={article_no} -> complex_no={complex_no}")
            else:
                failed += 1
                logger.warning(f"Failed to update listing {listing_id}: article_no={article_no}")

            # Rate limiting - random delay between 3-7 seconds
            delay = random.uniform(3, 7)
            await asyncio.sleep(delay)

    conn.close()

    logger.info("\n" + "=" * 60)
    logger.info("업데이트 완료!")
    logger.info(f"  - 성공: {updated}건")
    logger.info(f"  - 실패: {failed}건")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
