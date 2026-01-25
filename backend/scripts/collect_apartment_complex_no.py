"""아파트 단지의 naver_complex_no 수집 스크립트.

PC API를 사용하여 지역별 아파트 단지 목록을 조회하고,
기존 apartments 테이블과 매칭하여 naver_complex_no를 업데이트합니다.

Usage:
    python scripts/collect_apartment_complex_no.py
"""
import asyncio
import sqlite3
import sys
import logging
import random
from datetime import datetime
from pathlib import Path
from difflib import SequenceMatcher
from typing import List, Dict, Optional

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

# PC API endpoints
COMPLEX_LIST_URL = "https://new.land.naver.com/api/regions/complexes"

# 서울 주요 지역 코드
REGION_CODES = {
    "11680": "1168000000",  # 강남구
    "11650": "1165000000",  # 서초구
    "11710": "1171000000",  # 송파구
    "11740": "1174000000",  # 강동구
    "11440": "1144000000",  # 마포구
    "11170": "1117000000",  # 용산구
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


async def get_complexes_from_naver(
    client: httpx.AsyncClient,
    cortar_no: str,
    page: int = 1
) -> List[Dict]:
    """Get apartment complexes from Naver PC API."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://new.land.naver.com",
        "Accept": "application/json",
    }

    params = {
        "cortarNo": cortar_no,
        "realEstateType": "APT",
        "order": "rank",
        "page": page,
    }

    try:
        response = await client.get(COMPLEX_LIST_URL, params=params, headers=headers)

        if response.status_code == 200:
            data = response.json()
            complexes = []
            for item in data.get("complexList", []):
                complexes.append({
                    "complex_no": str(item.get("complexNo", "")),
                    "name": item.get("complexName", ""),
                    "address": item.get("address", ""),
                    "total_units": item.get("totalHouseholdCount"),
                    "built_year": item.get("useApproveYmd", "")[:4] if item.get("useApproveYmd") else None,
                    "latitude": item.get("latitude"),
                    "longitude": item.get("longitude"),
                })
            return complexes
        elif response.status_code == 429:
            logger.warning("Rate limited")
            return []
        else:
            logger.warning(f"Failed: {response.status_code}")
            return []

    except Exception as e:
        logger.error(f"Error: {e}")
        return []


async def main():
    """Main job."""
    logger.info("=" * 60)
    logger.info("아파트 단지 naver_complex_no 수집")
    logger.info("=" * 60)

    conn = sqlite3.connect(str(BACKEND_DIR / "chat_apt.db"))
    cursor = conn.cursor()

    # Get existing apartments by dong_code
    cursor.execute("""
        SELECT id, name, dong_code, naver_complex_no
        FROM apartments
        WHERE dong_code IS NOT NULL
    """)
    db_apartments = {}
    for row in cursor.fetchall():
        dong_code = row[2][:5] if row[2] else None
        if dong_code not in db_apartments:
            db_apartments[dong_code] = []
        db_apartments[dong_code].append({
            "id": row[0],
            "name": row[1],
            "dong_code": dong_code,
            "naver_complex_no": row[3],
        })

    logger.info(f"DB 아파트: {sum(len(v) for v in db_apartments.values())}개")

    updated = 0
    not_matched = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        for dong_code, cortar_no in REGION_CODES.items():
            logger.info(f"\n=== 지역: {dong_code} ===")

            if dong_code not in db_apartments:
                logger.info("매칭할 아파트 없음")
                continue

            db_apts = db_apartments[dong_code]
            logger.info(f"DB 아파트: {len(db_apts)}개")

            # Collect all complexes from Naver
            all_complexes = []
            page = 1
            while True:
                complexes = await get_complexes_from_naver(client, cortar_no, page)
                if not complexes:
                    break
                all_complexes.extend(complexes)
                if len(complexes) < 20:
                    break
                page += 1
                await asyncio.sleep(random.uniform(2, 4))

            logger.info(f"네이버 단지: {len(all_complexes)}개")

            # Match and update
            for db_apt in db_apts:
                if db_apt["naver_complex_no"]:
                    continue  # Already has complex_no

                best_match = None
                best_score = 0

                for naver_complex in all_complexes:
                    score = similarity_score(db_apt["name"], naver_complex["name"])
                    if score > best_score and score >= 0.7:
                        best_score = score
                        best_match = naver_complex

                if best_match:
                    cursor.execute(
                        """UPDATE apartments
                           SET naver_complex_no = ?, latitude = ?, longitude = ?
                           WHERE id = ?""",
                        (best_match["complex_no"],
                         best_match["latitude"],
                         best_match["longitude"],
                         db_apt["id"])
                    )
                    conn.commit()
                    updated += 1
                    logger.info(f"  매칭: {db_apt['name']} -> {best_match['name']} (complex_no={best_match['complex_no']}, score={best_score:.2f})")
                else:
                    not_matched += 1

            # Rate limiting between regions
            await asyncio.sleep(random.uniform(5, 10))

    conn.close()

    logger.info("\n" + "=" * 60)
    logger.info("수집 완료!")
    logger.info(f"  - 업데이트: {updated}건")
    logger.info(f"  - 매칭 실패: {not_matched}건")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
