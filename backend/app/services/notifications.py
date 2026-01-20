"""Notification service for alerts.

This module handles:
- Email notifications
- Push notifications (future)
- Alert preferences management
"""
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import json


class NotificationType(Enum):
    """Types of notifications."""
    UNDERVALUED_LISTING = "undervalued_listing"
    PRICE_DROP = "price_drop"
    NEW_LISTING = "new_listing"
    SUBSCRIPTION = "subscription"
    SYSTEM = "system"


@dataclass
class NotificationPayload:
    """Notification data structure."""
    type: NotificationType
    title: str
    message: str
    data: Optional[Dict[str, Any]] = None
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "title": self.title,
            "message": self.message,
            "data": self.data,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class AlertCondition:
    """User-defined alert condition."""
    user_id: str
    dong_code: Optional[str] = None
    min_area: Optional[float] = None
    max_area: Optional[float] = None
    max_price: Optional[int] = None
    min_discount_percent: float = -5.0  # Alert when discount >= this (negative = cheaper)
    enabled: bool = True

    def matches(self, listing: Dict[str, Any]) -> bool:
        """Check if a listing matches this alert condition."""
        if not self.enabled:
            return False

        # Check region
        if self.dong_code and listing.get("dong_code") != self.dong_code:
            return False

        # Check area
        area = listing.get("area", 0)
        if self.min_area and area < self.min_area:
            return False
        if self.max_area and area > self.max_area:
            return False

        # Check price
        if self.max_price and listing.get("price", 0) > self.max_price:
            return False

        # Check discount
        discount = listing.get("discount_percent", 0)
        if discount > self.min_discount_percent:
            return False

        return True


class NotificationService:
    """Service for managing and sending notifications."""

    def __init__(self):
        self._queue: List[NotificationPayload] = []
        self._user_alerts: Dict[str, List[AlertCondition]] = {}

    def register_alert(self, condition: AlertCondition):
        """Register an alert condition for a user."""
        if condition.user_id not in self._user_alerts:
            self._user_alerts[condition.user_id] = []
        self._user_alerts[condition.user_id].append(condition)

    def remove_alert(self, user_id: str, index: int):
        """Remove an alert condition."""
        if user_id in self._user_alerts and 0 <= index < len(self._user_alerts[user_id]):
            self._user_alerts[user_id].pop(index)

    def get_user_alerts(self, user_id: str) -> List[AlertCondition]:
        """Get all alert conditions for a user."""
        return self._user_alerts.get(user_id, [])

    def check_and_notify(
        self,
        listing: Dict[str, Any],
    ) -> List[tuple[str, NotificationPayload]]:
        """Check listing against all alerts and generate notifications.

        Args:
            listing: Listing data to check

        Returns:
            List of (user_id, notification) tuples
        """
        notifications = []

        for user_id, alerts in self._user_alerts.items():
            for alert in alerts:
                if alert.matches(listing):
                    notification = self._create_undervalued_notification(listing)
                    notifications.append((user_id, notification))
                    break  # One notification per user per listing

        return notifications

    def _create_undervalued_notification(
        self,
        listing: Dict[str, Any],
    ) -> NotificationPayload:
        """Create notification for undervalued listing."""
        apartment_name = listing.get("apartment_name", "아파트")
        discount = abs(listing.get("discount_percent", 0))
        price = listing.get("price", 0)

        # Format price
        if price >= 10000:
            price_str = f"{price // 10000}억"
            if price % 10000:
                price_str += f" {price % 10000:,}만"
        else:
            price_str = f"{price:,}만"

        return NotificationPayload(
            type=NotificationType.UNDERVALUED_LISTING,
            title=f"저평가 매물 발견: {apartment_name}",
            message=f"유사 매물 대비 {discount:.1f}% 저렴한 매물이 등록되었습니다. 가격: {price_str}원",
            data={
                "listing_id": listing.get("id"),
                "apartment_id": listing.get("apartment_id"),
                "apartment_name": apartment_name,
                "price": price,
                "discount_percent": listing.get("discount_percent"),
            },
        )

    async def send_notification(
        self,
        user_id: str,
        notification: NotificationPayload,
    ) -> bool:
        """Send a notification to a user.

        In production, this would integrate with:
        - Email service (SendGrid, AWS SES)
        - Push notification service (FCM, APNs)
        - In-app notification system

        Args:
            user_id: Target user ID
            notification: Notification to send

        Returns:
            True if sent successfully
        """
        # Queue notification for processing
        self._queue.append(notification)

        # TODO: Implement actual sending
        # - Check user notification preferences
        # - Send via appropriate channel (email, push, etc.)

        return True

    def get_pending_notifications(self) -> List[NotificationPayload]:
        """Get pending notifications in queue."""
        return self._queue.copy()

    def clear_queue(self):
        """Clear the notification queue."""
        self._queue.clear()


# Singleton instance
_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    """Get the notification service singleton."""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service
