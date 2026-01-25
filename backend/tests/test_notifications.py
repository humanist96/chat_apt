"""Tests for notification and caching services."""
import pytest
from datetime import datetime

from app.services.notifications import (
    NotificationService,
    NotificationPayload,
    NotificationType,
    AlertCondition,
    get_notification_service,
)
from app.services.cache import (
    CacheService,
    CacheKeys,
    cache_key,
    get_cache_service,
)


class TestNotificationType:
    """Tests for NotificationType enum."""

    def test_notification_types(self):
        """Test notification type values."""
        assert NotificationType.UNDERVALUED_LISTING.value == "undervalued_listing"
        assert NotificationType.PRICE_DROP.value == "price_drop"
        assert NotificationType.NEW_LISTING.value == "new_listing"


class TestNotificationPayload:
    """Tests for NotificationPayload."""

    def test_payload_creation(self):
        """Test creating a notification payload."""
        payload = NotificationPayload(
            type=NotificationType.UNDERVALUED_LISTING,
            title="Test Title",
            message="Test message",
            data={"key": "value"},
        )

        assert payload.type == NotificationType.UNDERVALUED_LISTING
        assert payload.title == "Test Title"
        assert payload.message == "Test message"
        assert payload.data == {"key": "value"}
        assert payload.created_at is not None

    def test_payload_to_dict(self):
        """Test converting payload to dict."""
        payload = NotificationPayload(
            type=NotificationType.PRICE_DROP,
            title="Price Drop",
            message="Price dropped",
        )

        result = payload.to_dict()

        assert result["type"] == "price_drop"
        assert result["title"] == "Price Drop"
        assert "created_at" in result


class TestAlertCondition:
    """Tests for AlertCondition."""

    def test_alert_condition_creation(self):
        """Test creating an alert condition."""
        condition = AlertCondition(
            user_id="user-123",
            dong_code="11680",
            min_area=60.0,
            max_area=90.0,
            max_price=150000,
            min_discount_percent=-5.0,
        )

        assert condition.user_id == "user-123"
        assert condition.dong_code == "11680"
        assert condition.enabled is True

    def test_alert_matches_all_criteria(self):
        """Test matching when all criteria match."""
        condition = AlertCondition(
            user_id="user-123",
            dong_code="11680",
            min_area=60.0,
            max_area=90.0,
            max_price=150000,
            min_discount_percent=-5.0,
        )

        listing = {
            "dong_code": "11680",
            "area": 84.95,
            "price": 140000,
            "discount_percent": -8.0,  # 8% cheaper
        }

        assert condition.matches(listing) is True

    def test_alert_no_match_wrong_region(self):
        """Test no match when region differs."""
        condition = AlertCondition(
            user_id="user-123",
            dong_code="11680",
        )

        listing = {
            "dong_code": "11650",  # Different region
            "discount_percent": -10.0,
        }

        assert condition.matches(listing) is False

    def test_alert_no_match_price_too_high(self):
        """Test no match when price exceeds max."""
        condition = AlertCondition(
            user_id="user-123",
            max_price=150000,
        )

        listing = {
            "price": 200000,  # Over max
            "discount_percent": -10.0,
        }

        assert condition.matches(listing) is False

    def test_alert_no_match_not_discounted_enough(self):
        """Test no match when discount too small."""
        condition = AlertCondition(
            user_id="user-123",
            min_discount_percent=-5.0,  # Need at least 5% discount
        )

        listing = {
            "discount_percent": -2.0,  # Only 2% discount
        }

        assert condition.matches(listing) is False

    def test_alert_disabled(self):
        """Test disabled alert never matches."""
        condition = AlertCondition(
            user_id="user-123",
            enabled=False,
        )

        listing = {
            "discount_percent": -20.0,  # Big discount
        }

        assert condition.matches(listing) is False


class TestNotificationService:
    """Tests for NotificationService."""

    def test_register_alert(self):
        """Test registering an alert."""
        service = NotificationService()

        condition = AlertCondition(user_id="user-1", dong_code="11680")
        service.register_alert(condition)

        alerts = service.get_user_alerts("user-1")
        assert len(alerts) == 1
        assert alerts[0].dong_code == "11680"

    def test_remove_alert(self):
        """Test removing an alert."""
        service = NotificationService()

        condition1 = AlertCondition(user_id="user-1", dong_code="11680")
        condition2 = AlertCondition(user_id="user-1", dong_code="11650")
        service.register_alert(condition1)
        service.register_alert(condition2)

        service.remove_alert("user-1", 0)

        alerts = service.get_user_alerts("user-1")
        assert len(alerts) == 1
        assert alerts[0].dong_code == "11650"

    def test_check_and_notify(self):
        """Test checking listing against alerts."""
        service = NotificationService()

        condition = AlertCondition(
            user_id="user-1",
            dong_code="11680",
            min_discount_percent=-5.0,
        )
        service.register_alert(condition)

        listing = {
            "id": 123,
            "apartment_id": 456,
            "apartment_name": "테스트아파트",
            "dong_code": "11680",
            "price": 150000,
            "discount_percent": -10.0,
        }

        notifications = service.check_and_notify(listing)

        assert len(notifications) == 1
        user_id, notification = notifications[0]
        assert user_id == "user-1"
        assert notification.type == NotificationType.UNDERVALUED_LISTING
        assert "테스트아파트" in notification.title

    @pytest.mark.asyncio
    async def test_send_notification(self):
        """Test sending a notification."""
        service = NotificationService()

        notification = NotificationPayload(
            type=NotificationType.SYSTEM,
            title="Test",
            message="Test message",
        )

        result = await service.send_notification("user-1", notification)

        assert result is True
        assert len(service.get_pending_notifications()) == 1


class TestCacheService:
    """Tests for CacheService."""

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        """Test setting and getting cache values."""
        cache = CacheService()

        await cache.set("test_key", {"value": 123}, ttl=60)
        result = await cache.get("test_key")

        assert result == {"value": 123}

    @pytest.mark.asyncio
    async def test_get_nonexistent(self):
        """Test getting nonexistent key."""
        cache = CacheService()

        result = await cache.get("nonexistent_key")

        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self):
        """Test deleting cache value."""
        cache = CacheService()

        await cache.set("delete_test", "value")
        await cache.delete("delete_test")

        result = await cache.get("delete_test")
        assert result is None

    @pytest.mark.asyncio
    async def test_exists(self):
        """Test checking key existence."""
        cache = CacheService()

        await cache.set("exists_test", "value")

        assert await cache.exists("exists_test") is True
        assert await cache.exists("not_exists") is False

    def test_clear_memory_cache(self):
        """Test clearing memory cache."""
        cache = CacheService()
        cache._memory_cache = {"key1": "value1", "key2": "value2"}

        cache.clear_memory_cache()

        assert len(cache._memory_cache) == 0


class TestCacheKeys:
    """Tests for CacheKeys patterns."""

    def test_apartment_key(self):
        """Test apartment cache key."""
        key = CacheKeys.apartment(123)
        assert key == "apartment:123"

    def test_listing_key(self):
        """Test listing cache key."""
        key = CacheKeys.listing(456)
        assert key == "listing:456"

    def test_recommendations_key(self):
        """Test recommendations cache key."""
        key = CacheKeys.recommendations("11680")
        assert key == "recommendations:11680"

    def test_similar_apartments_key(self):
        """Test similar apartments cache key."""
        key = CacheKeys.similar_apartments(789)
        assert key == "similar:789"


class TestCacheKeyFunction:
    """Tests for cache_key function."""

    def test_cache_key_args(self):
        """Test cache key with args."""
        key1 = cache_key(1, 2, 3)
        key2 = cache_key(1, 2, 3)
        key3 = cache_key(1, 2, 4)

        assert key1 == key2
        assert key1 != key3

    def test_cache_key_kwargs(self):
        """Test cache key with kwargs."""
        key1 = cache_key(a=1, b=2)
        key2 = cache_key(b=2, a=1)  # Different order

        assert key1 == key2  # Should be same (sorted)

    def test_cache_key_mixed(self):
        """Test cache key with args and kwargs."""
        key = cache_key(1, 2, foo="bar")
        assert isinstance(key, str)
        assert len(key) == 32  # MD5 hash length


class TestGetSingletons:
    """Tests for singleton getters."""

    def test_get_notification_service(self):
        """Test getting notification service singleton."""
        service1 = get_notification_service()
        service2 = get_notification_service()

        assert service1 is service2

    def test_get_cache_service(self):
        """Test getting cache service singleton."""
        cache1 = get_cache_service()
        cache2 = get_cache_service()

        assert cache1 is cache2
