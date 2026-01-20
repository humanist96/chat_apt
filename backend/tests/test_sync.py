"""Tests for data sync service."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from decimal import Decimal

from app.services.sync import (
    DataSyncService,
    SyncStats,
    get_sync_service,
)


class TestSyncStats:
    """Tests for SyncStats."""

    def test_sync_stats_creation(self):
        """Test creating sync stats."""
        stats = SyncStats(
            table_name="apartments",
            total_records=100,
            synced_records=98,
            failed_records=2,
            duration_ms=1500,
            last_synced_at=datetime.now()
        )

        assert stats.table_name == "apartments"
        assert stats.total_records == 100
        assert stats.synced_records == 98
        assert stats.failed_records == 2


class TestDataSyncService:
    """Tests for DataSyncService."""

    def test_service_creation(self):
        """Test creating sync service."""
        service = DataSyncService()

        assert service.batch_size == 500
        assert service._client is None

    def test_service_with_batch_size(self):
        """Test service with custom batch size."""
        service = DataSyncService(batch_size=100)

        assert service.batch_size == 100

    def test_apartment_to_doc(self):
        """Test converting apartment to document."""
        service = DataSyncService()

        # Create mock apartment
        apt = MagicMock()
        apt.id = 1
        apt.name = "래미안"
        apt.address = "서울시 강남구"
        apt.dong_code = "11680"
        apt.complex_no = "12345"
        apt.latitude = Decimal("37.5")
        apt.longitude = Decimal("127.0")
        apt.total_units = 500
        apt.built_year = 2020
        apt.avg_area = Decimal("84.95")
        apt.created_at = datetime(2024, 1, 1)
        apt.updated_at = datetime(2024, 1, 15)

        doc = service._apartment_to_doc(apt)

        assert doc["id"] == 1
        assert doc["name"] == "래미안"
        assert doc["dong_code"] == "11680"
        assert doc["location"]["lat"] == 37.5
        assert doc["location"]["lon"] == 127.0
        assert doc["built_year"] == 2020

    def test_apartment_to_doc_no_location(self):
        """Test converting apartment without location."""
        service = DataSyncService()

        apt = MagicMock()
        apt.id = 1
        apt.name = "Test"
        apt.address = "Address"
        apt.dong_code = "11680"
        apt.complex_no = None
        apt.latitude = None
        apt.longitude = None
        apt.total_units = None
        apt.built_year = None
        apt.avg_area = None
        apt.created_at = None
        apt.updated_at = None

        doc = service._apartment_to_doc(apt)

        assert doc["id"] == 1
        assert "location" not in doc

    def test_listing_to_doc(self):
        """Test converting listing to document."""
        service = DataSyncService()

        listing = MagicMock()
        listing.id = 100
        listing.apartment_id = 1
        listing.article_no = "ART123"
        listing.trade_type = "A1"
        listing.price = 150000
        listing.rent_price = None
        listing.area = Decimal("84.95")
        listing.floor = 10
        listing.direction = "남향"
        listing.description = "좋은 매물"
        listing.is_active = True
        listing.first_seen_at = datetime(2024, 1, 1)
        listing.last_seen_at = datetime(2024, 1, 15)
        listing.created_at = datetime(2024, 1, 1)

        apartment = MagicMock()
        apartment.name = "래미안"
        apartment.dong_code = "11680"
        apartment.latitude = Decimal("37.5")
        apartment.longitude = Decimal("127.0")

        analysis = {
            "discount_rate": -8.5,
            "recommendation_score": 85.0
        }

        doc = service._listing_to_doc(listing, apartment, analysis)

        assert doc["id"] == 100
        assert doc["price"] == 150000
        assert doc["apartment_name"] == "래미안"
        assert doc["dong_code"] == "11680"
        assert doc["discount_rate"] == -8.5
        assert doc["recommendation_score"] == 85.0
        assert "location" in doc

    def test_transaction_to_doc(self):
        """Test converting transaction to document."""
        service = DataSyncService()

        txn = MagicMock()
        txn.id = 200
        txn.apartment_id = 1
        txn.deal_amount = 140000
        txn.area = Decimal("84.95")
        txn.floor = 15
        txn.deal_year = 2024
        txn.deal_month = 6
        txn.deal_day = 15
        txn.created_at = datetime(2024, 7, 1)

        apartment = MagicMock()
        apartment.name = "래미안"
        apartment.dong_code = "11680"

        doc = service._transaction_to_doc(txn, apartment)

        assert doc["id"] == 200
        assert doc["deal_amount"] == 140000
        assert doc["apartment_name"] == "래미안"
        assert doc["deal_year"] == 2024
        assert doc["deal_month"] == 6
        assert "deal_date" in doc

    @pytest.mark.asyncio
    async def test_sync_apartments_empty(self):
        """Test syncing with no records."""
        service = DataSyncService()

        # Mock OpenSearch client
        mock_os = MagicMock()
        mock_os.bulk_index = AsyncMock()
        service._client = mock_os

        # Mock session
        mock_session = MagicMock()

        # Mock query result (count)
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        mock_session.execute = AsyncMock(return_value=mock_count_result)

        stats = await service.sync_apartments(mock_session, full_sync=True)

        assert stats.table_name == "apartments"
        assert stats.total_records == 0
        assert stats.synced_records == 0

    @pytest.mark.asyncio
    async def test_initialize(self):
        """Test initialization."""
        service = DataSyncService()

        mock_os = MagicMock()
        mock_os.connect = AsyncMock()
        service._client = mock_os

        with patch('app.services.sync.setup_indices', new_callable=AsyncMock):
            await service.initialize()

        mock_os.connect.assert_called_once()


class TestSingletonPattern:
    """Test singleton pattern."""

    def test_get_sync_service(self):
        """Test getting sync service singleton."""
        service1 = get_sync_service()
        service2 = get_sync_service()

        assert service1 is service2
