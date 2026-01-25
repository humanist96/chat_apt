"""Daily data collection scheduler.

This module handles scheduled jobs for:
- Crawling Naver Real Estate listings
- Fetching public transaction data
- Running analysis on new data
- Sending notifications for matching alerts
"""
import asyncio
from datetime import datetime, date, timedelta
from typing import List, Optional
import logging

from app.crawler.naver import NaverRealEstateCrawler, NaverListing
from app.services.public_data_api import PublicDataAPIClient, REGION_CODES
from app.services.notifications import get_notification_service
from app.services.cache import get_cache_service, CacheKeys
from app.services.sync import run_sync_job
from app.analysis.comparison import ComparisonAnalyzer
from app.config import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DailyCollectionJob:
    """Daily job for collecting real estate data."""

    def __init__(self):
        self.settings = get_settings()
        self.notification_service = get_notification_service()
        self.cache_service = get_cache_service()

    async def run(self):
        """Run the daily collection job."""
        logger.info(f"Starting daily collection job at {datetime.now()}")

        try:
            # 1. Collect public transaction data
            await self.collect_transactions()

            # 2. Crawl Naver listings
            await self.crawl_listings()

            # 3. Run analysis
            await self.run_analysis()

            # 4. Sync data to OpenSearch
            await self.sync_to_opensearch()

            # 5. Check alerts
            await self.check_alerts()

            # 6. Clear old cache
            await self.cleanup_cache()

            logger.info("Daily collection job completed successfully")

        except Exception as e:
            logger.error(f"Daily collection job failed: {e}")
            raise

    async def collect_transactions(self):
        """Collect real transaction data from public API."""
        logger.info("Collecting public transaction data...")

        # Get last month's data
        today = date.today()
        if today.month == 1:
            target_month = date(today.year - 1, 12, 1)
        else:
            target_month = date(today.year, today.month - 1, 1)

        deal_ymd = target_month.strftime("%Y%m")

        async with PublicDataAPIClient() as client:
            for region_name, region_code in REGION_CODES.items():
                try:
                    logger.info(f"Fetching transactions for {region_name} ({deal_ymd})")

                    transactions = await client.get_transactions(
                        lawd_cd=region_code,
                        deal_ymd=deal_ymd,
                    )

                    logger.info(f"  Found {len(transactions)} transactions")

                    # TODO: Save to database
                    # await self.save_transactions(transactions)

                except Exception as e:
                    logger.error(f"Failed to fetch {region_name}: {e}")
                    continue

    async def crawl_listings(self):
        """Crawl listings from Naver Real Estate."""
        logger.info("Crawling Naver Real Estate listings...")

        # Target regions for crawling
        target_regions = [
            "1168000000",  # 서울 강남구
            "1165000000",  # 서울 서초구
            "1171000000",  # 서울 송파구
        ]

        async with NaverRealEstateCrawler() as crawler:
            for region in target_regions:
                try:
                    # Get complexes in region
                    complexes = await crawler.get_complexes_in_region(
                        cortarNo=region,
                        page=1,
                        count=50,
                    )

                    logger.info(f"Found {len(complexes)} complexes in {region}")

                    for complex_info in complexes[:10]:  # Limit for demo
                        try:
                            listings = await crawler.get_listings(
                                complex_no=complex_info.complex_no,
                                trade_type="A1",  # 매매
                            )

                            logger.info(
                                f"  {complex_info.complex_name}: {len(listings)} listings"
                            )

                            # TODO: Save to database
                            # await self.save_listings(listings)

                        except Exception as e:
                            logger.error(
                                f"Failed to crawl {complex_info.complex_name}: {e}"
                            )
                            continue

                except Exception as e:
                    logger.error(f"Failed to crawl region {region}: {e}")
                    continue

    async def run_analysis(self):
        """Run analysis on collected data."""
        logger.info("Running analysis on collected data...")

        analyzer = ComparisonAnalyzer()

        # TODO: Fetch listings from database and run analysis
        # listings = await self.get_new_listings()
        # for listing in listings:
        #     report = analyzer.generate_report(...)
        #     await self.save_analysis_result(report)

        logger.info("Analysis completed")

    async def sync_to_opensearch(self):
        """Sync data to OpenSearch for search and analytics."""
        logger.info("Syncing data to OpenSearch...")

        try:
            # Run incremental sync (only changes since last sync)
            results = await run_sync_job(full=False)

            total_synced = sum(r.synced_records for r in results)
            logger.info(f"OpenSearch sync completed: {total_synced} records synced")

        except Exception as e:
            logger.error(f"OpenSearch sync failed: {e}")
            # Don't raise - sync failure shouldn't stop other jobs

    async def check_alerts(self):
        """Check for alert matches and send notifications."""
        logger.info("Checking alert conditions...")

        # TODO: Fetch new/updated listings and check against alerts
        # new_listings = await self.get_new_listings()
        # for listing in new_listings:
        #     notifications = self.notification_service.check_and_notify(listing)
        #     for user_id, notification in notifications:
        #         await self.notification_service.send_notification(user_id, notification)

        logger.info("Alert check completed")

    async def cleanup_cache(self):
        """Clean up old cache entries."""
        logger.info("Cleaning up cache...")

        cache = get_cache_service()

        # Clear recommendations cache (will be regenerated)
        await cache.delete_pattern("recommendations:*")

        # Clear old price trends (older than 1 hour)
        await cache.delete_pattern("price_trend:*")

        logger.info("Cache cleanup completed")


class SchedulerConfig:
    """Configuration for the scheduler."""

    # Run at 3:00 AM KST (6:00 PM UTC previous day)
    RUN_HOUR_UTC = 18
    RUN_MINUTE = 0

    # Retry settings
    MAX_RETRIES = 3
    RETRY_DELAY_SECONDS = 300  # 5 minutes


async def run_scheduler():
    """Main scheduler loop."""
    logger.info("Starting scheduler...")

    config = SchedulerConfig()
    job = DailyCollectionJob()

    while True:
        now = datetime.utcnow()

        # Calculate next run time
        next_run = now.replace(
            hour=config.RUN_HOUR_UTC,
            minute=config.RUN_MINUTE,
            second=0,
            microsecond=0,
        )

        if now >= next_run:
            next_run += timedelta(days=1)

        # Wait until next run
        wait_seconds = (next_run - now).total_seconds()
        logger.info(f"Next run scheduled at {next_run} UTC (in {wait_seconds/3600:.1f} hours)")

        await asyncio.sleep(wait_seconds)

        # Run the job with retries
        for attempt in range(config.MAX_RETRIES):
            try:
                await job.run()
                break
            except Exception as e:
                logger.error(f"Job failed (attempt {attempt + 1}/{config.MAX_RETRIES}): {e}")
                if attempt < config.MAX_RETRIES - 1:
                    await asyncio.sleep(config.RETRY_DELAY_SECONDS)


async def run_once():
    """Run the collection job once (for testing/manual execution)."""
    job = DailyCollectionJob()
    await job.run()


if __name__ == "__main__":
    # For testing: run once
    asyncio.run(run_once())
