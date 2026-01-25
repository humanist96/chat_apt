"""PostgreSQL to OpenSearch synchronization service.

This module handles data replication from PostgreSQL (primary)
to OpenSearch (search/analytics).
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session_maker
from app.models.apartment import Apartment, Transaction, Listing
from app.services.opensearch import (
    OpenSearchClient,
    get_opensearch_client,
    APARTMENTS_INDEX,
    LISTINGS_INDEX,
    TRANSACTIONS_INDEX,
    setup_indices,
)

logger = logging.getLogger(__name__)


@dataclass
class SyncStats:
    """Statistics for a sync operation."""
    table_name: str
    total_records: int
    synced_records: int
    failed_records: int
    duration_ms: int
    last_synced_at: datetime


class DataSyncService:
    """Service to sync data from PostgreSQL to OpenSearch."""

    def __init__(
        self,
        opensearch_client: Optional[OpenSearchClient] = None,
        batch_size: int = 500
    ):
        self._client = opensearch_client
        self.batch_size = batch_size
        self._last_sync: Dict[str, datetime] = {}

    @property
    def client(self) -> OpenSearchClient:
        if self._client is None:
            self._client = get_opensearch_client()
        return self._client

    async def initialize(self) -> None:
        """Initialize OpenSearch indices."""
        await self.client.connect()
        await setup_indices(self.client)

    async def close(self) -> None:
        """Close connections."""
        if self._client:
            await self._client.close()

    def _apartment_to_doc(self, apt: Apartment) -> Dict[str, Any]:
        """Convert Apartment model to OpenSearch document."""
        doc = {
            "id": apt.id,
            "name": apt.name,
            "address": apt.address,
            "dong_code": apt.dong_code,
            "complex_no": apt.complex_no,
            "total_units": apt.total_units,
            "built_year": apt.built_year,
            "avg_area": float(apt.avg_area) if apt.avg_area else None,
            "created_at": apt.created_at.isoformat() if apt.created_at else None,
            "updated_at": apt.updated_at.isoformat() if apt.updated_at else None,
        }

        # Add geo_point if coordinates available
        if apt.latitude and apt.longitude:
            doc["location"] = {
                "lat": float(apt.latitude),
                "lon": float(apt.longitude)
            }

        return doc

    def _listing_to_doc(
        self,
        listing: Listing,
        apartment: Optional[Apartment] = None,
        analysis: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Convert Listing model to OpenSearch document."""
        doc = {
            "id": listing.id,
            "apartment_id": listing.apartment_id,
            "article_no": listing.article_no,
            "trade_type": listing.trade_type,
            "price": listing.price,
            "rent_price": listing.rent_price,
            "area": float(listing.area) if listing.area else None,
            "floor": listing.floor,
            "direction": listing.direction,
            "description": listing.description,
            "is_active": listing.is_active,
            "first_seen_at": listing.first_seen_at.isoformat() if listing.first_seen_at else None,
            "last_seen_at": listing.last_seen_at.isoformat() if listing.last_seen_at else None,
            "created_at": listing.created_at.isoformat() if listing.created_at else None,
        }

        # Add apartment info
        if apartment:
            doc["apartment_name"] = apartment.name
            doc["dong_code"] = apartment.dong_code
            if apartment.latitude and apartment.longitude:
                doc["location"] = {
                    "lat": float(apartment.latitude),
                    "lon": float(apartment.longitude)
                }

        # Add analysis info
        if analysis:
            doc["discount_rate"] = analysis.get("discount_rate")
            doc["recommendation_score"] = analysis.get("recommendation_score")

        return doc

    def _transaction_to_doc(
        self,
        txn: Transaction,
        apartment: Optional[Apartment] = None
    ) -> Dict[str, Any]:
        """Convert Transaction model to OpenSearch document."""
        doc = {
            "id": txn.id,
            "apartment_id": txn.apartment_id,
            "deal_amount": txn.deal_amount,
            "area": float(txn.area) if txn.area else None,
            "floor": txn.floor,
            "deal_year": txn.deal_year,
            "deal_month": txn.deal_month,
            "deal_day": txn.deal_day,
            "created_at": txn.created_at.isoformat() if txn.created_at else None,
        }

        # Create deal_date for date histogram
        if txn.deal_year and txn.deal_month:
            day = txn.deal_day or 1
            try:
                deal_date = datetime(txn.deal_year, txn.deal_month, day)
                doc["deal_date"] = deal_date.isoformat()
            except ValueError:
                pass

        # Add apartment info
        if apartment:
            doc["apartment_name"] = apartment.name
            doc["dong_code"] = apartment.dong_code

        return doc

    async def sync_apartments(
        self,
        session: AsyncSession,
        full_sync: bool = False
    ) -> SyncStats:
        """Sync apartments table to OpenSearch.

        Args:
            session: Database session
            full_sync: If True, sync all records. If False, only changed since last sync.
        """
        start_time = datetime.now()
        table_name = "apartments"

        # Build query
        query = select(Apartment)
        if not full_sync and table_name in self._last_sync:
            query = query.where(Apartment.updated_at >= self._last_sync[table_name])

        # Get total count
        count_result = await session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total_records = count_result.scalar() or 0

        if total_records == 0:
            return SyncStats(
                table_name=table_name,
                total_records=0,
                synced_records=0,
                failed_records=0,
                duration_ms=0,
                last_synced_at=datetime.now()
            )

        # Process in batches
        synced = 0
        failed = 0
        offset = 0

        while offset < total_records:
            batch_query = query.offset(offset).limit(self.batch_size)
            result = await session.execute(batch_query)
            apartments = result.scalars().all()

            if not apartments:
                break

            # Prepare documents
            documents: List[Tuple[str, Dict[str, Any]]] = []
            for apt in apartments:
                doc_id = str(apt.id)
                doc = self._apartment_to_doc(apt)
                documents.append((doc_id, doc))

            # Bulk index
            try:
                result = await self.client.bulk_index(
                    APARTMENTS_INDEX.name,
                    documents
                )
                synced += result.get("indexed", 0)
                if result.get("errors"):
                    failed += len(documents) - result.get("indexed", 0)
            except Exception as e:
                logger.error(f"Failed to bulk index apartments: {e}")
                failed += len(documents)

            offset += self.batch_size

        # Update last sync time
        self._last_sync[table_name] = start_time

        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        logger.info(f"Synced apartments: {synced}/{total_records} in {duration_ms}ms")

        return SyncStats(
            table_name=table_name,
            total_records=total_records,
            synced_records=synced,
            failed_records=failed,
            duration_ms=duration_ms,
            last_synced_at=datetime.now()
        )

    async def sync_listings(
        self,
        session: AsyncSession,
        full_sync: bool = False,
        include_analysis: bool = True
    ) -> SyncStats:
        """Sync listings table to OpenSearch."""
        start_time = datetime.now()
        table_name = "listings"

        # Build query with apartment join
        query = select(Listing, Apartment).join(
            Apartment, Listing.apartment_id == Apartment.id
        )

        if not full_sync and table_name in self._last_sync:
            query = query.where(Listing.updated_at >= self._last_sync[table_name])

        # Get total count
        count_query = select(func.count()).select_from(Listing)
        if not full_sync and table_name in self._last_sync:
            count_query = count_query.where(
                Listing.updated_at >= self._last_sync[table_name]
            )

        count_result = await session.execute(count_query)
        total_records = count_result.scalar() or 0

        if total_records == 0:
            return SyncStats(
                table_name=table_name,
                total_records=0,
                synced_records=0,
                failed_records=0,
                duration_ms=0,
                last_synced_at=datetime.now()
            )

        # Get analysis results if needed
        analysis_map: Dict[int, Dict[str, Any]] = {}
        if include_analysis:
            from app.models.apartment import AnalysisResult
            analysis_query = select(AnalysisResult)
            analysis_result = await session.execute(analysis_query)
            for ar in analysis_result.scalars():
                analysis_map[ar.listing_id] = {
                    "discount_rate": float(ar.discount_rate) if ar.discount_rate else None,
                    "recommendation_score": float(ar.recommendation_score) if ar.recommendation_score else None,
                }

        # Process in batches
        synced = 0
        failed = 0
        offset = 0

        while offset < total_records:
            batch_query = query.offset(offset).limit(self.batch_size)
            result = await session.execute(batch_query)
            rows = result.all()

            if not rows:
                break

            # Prepare documents
            documents: List[Tuple[str, Dict[str, Any]]] = []
            for listing, apartment in rows:
                doc_id = str(listing.id)
                analysis = analysis_map.get(listing.id)
                doc = self._listing_to_doc(listing, apartment, analysis)
                documents.append((doc_id, doc))

            # Bulk index
            try:
                result = await self.client.bulk_index(
                    LISTINGS_INDEX.name,
                    documents
                )
                synced += result.get("indexed", 0)
                if result.get("errors"):
                    failed += len(documents) - result.get("indexed", 0)
            except Exception as e:
                logger.error(f"Failed to bulk index listings: {e}")
                failed += len(documents)

            offset += self.batch_size

        self._last_sync[table_name] = start_time
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        logger.info(f"Synced listings: {synced}/{total_records} in {duration_ms}ms")

        return SyncStats(
            table_name=table_name,
            total_records=total_records,
            synced_records=synced,
            failed_records=failed,
            duration_ms=duration_ms,
            last_synced_at=datetime.now()
        )

    async def sync_transactions(
        self,
        session: AsyncSession,
        full_sync: bool = False
    ) -> SyncStats:
        """Sync transactions table to OpenSearch."""
        start_time = datetime.now()
        table_name = "transactions"

        # Build query with apartment join
        query = select(Transaction, Apartment).join(
            Apartment, Transaction.apartment_id == Apartment.id
        )

        if not full_sync and table_name in self._last_sync:
            query = query.where(Transaction.created_at >= self._last_sync[table_name])

        # Get total count
        count_query = select(func.count()).select_from(Transaction)
        if not full_sync and table_name in self._last_sync:
            count_query = count_query.where(
                Transaction.created_at >= self._last_sync[table_name]
            )

        count_result = await session.execute(count_query)
        total_records = count_result.scalar() or 0

        if total_records == 0:
            return SyncStats(
                table_name=table_name,
                total_records=0,
                synced_records=0,
                failed_records=0,
                duration_ms=0,
                last_synced_at=datetime.now()
            )

        # Process in batches
        synced = 0
        failed = 0
        offset = 0

        while offset < total_records:
            batch_query = query.offset(offset).limit(self.batch_size)
            result = await session.execute(batch_query)
            rows = result.all()

            if not rows:
                break

            # Prepare documents
            documents: List[Tuple[str, Dict[str, Any]]] = []
            for txn, apartment in rows:
                doc_id = str(txn.id)
                doc = self._transaction_to_doc(txn, apartment)
                documents.append((doc_id, doc))

            # Bulk index
            try:
                result = await self.client.bulk_index(
                    TRANSACTIONS_INDEX.name,
                    documents
                )
                synced += result.get("indexed", 0)
                if result.get("errors"):
                    failed += len(documents) - result.get("indexed", 0)
            except Exception as e:
                logger.error(f"Failed to bulk index transactions: {e}")
                failed += len(documents)

            offset += self.batch_size

        self._last_sync[table_name] = start_time
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        logger.info(f"Synced transactions: {synced}/{total_records} in {duration_ms}ms")

        return SyncStats(
            table_name=table_name,
            total_records=total_records,
            synced_records=synced,
            failed_records=failed,
            duration_ms=duration_ms,
            last_synced_at=datetime.now()
        )

    async def full_sync(self, session: AsyncSession) -> List[SyncStats]:
        """Perform full sync of all tables."""
        logger.info("Starting full sync to OpenSearch...")

        results = []

        # Sync in order (apartments first as it's referenced by others)
        results.append(await self.sync_apartments(session, full_sync=True))
        results.append(await self.sync_transactions(session, full_sync=True))
        results.append(await self.sync_listings(session, full_sync=True))

        total_synced = sum(r.synced_records for r in results)
        total_failed = sum(r.failed_records for r in results)

        logger.info(f"Full sync complete: {total_synced} synced, {total_failed} failed")

        return results

    async def incremental_sync(self, session: AsyncSession) -> List[SyncStats]:
        """Perform incremental sync (only changes since last sync)."""
        logger.info("Starting incremental sync to OpenSearch...")

        results = []
        results.append(await self.sync_apartments(session, full_sync=False))
        results.append(await self.sync_transactions(session, full_sync=False))
        results.append(await self.sync_listings(session, full_sync=False))

        total_synced = sum(r.synced_records for r in results)

        logger.info(f"Incremental sync complete: {total_synced} records updated")

        return results


# Singleton instance
_sync_service: Optional[DataSyncService] = None


def get_sync_service() -> DataSyncService:
    """Get or create the sync service singleton."""
    global _sync_service
    if _sync_service is None:
        _sync_service = DataSyncService()
    return _sync_service


async def run_sync_job(full: bool = False) -> List[SyncStats]:
    """Run sync job (for scheduler integration)."""
    sync_service = get_sync_service()
    await sync_service.initialize()

    try:
        session_maker = get_session_maker()
        async with session_maker() as session:
            if full:
                return await sync_service.full_sync(session)
            else:
                return await sync_service.incremental_sync(session)
    finally:
        await sync_service.close()
