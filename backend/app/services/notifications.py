"""Notification service for alerts.

This module handles:
- Telegram notifications
- Email notifications (future)
- Push notifications (future)
- Alert preferences management
"""
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import json
import logging
import aiohttp

logger = logging.getLogger(__name__)


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


class TelegramNotifier:
    """Telegram Bot notification sender."""

    TELEGRAM_API_BASE = "https://api.telegram.org/bot"

    def __init__(self, bot_token: str, default_chat_id: Optional[str] = None):
        """Initialize Telegram notifier.

        Args:
            bot_token: Telegram Bot token from @BotFather
            default_chat_id: Default chat ID for notifications
        """
        self.bot_token = bot_token
        self.default_chat_id = default_chat_id
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def send_message(
        self,
        text: str,
        chat_id: Optional[str] = None,
        parse_mode: str = "Markdown",
        disable_notification: bool = False,
    ) -> bool:
        """Send a text message via Telegram.

        Args:
            text: Message text (supports Markdown/HTML based on parse_mode)
            chat_id: Target chat ID (uses default if not provided)
            parse_mode: Markdown or HTML
            disable_notification: Send silently

        Returns:
            True if sent successfully
        """
        target_chat_id = chat_id or self.default_chat_id
        if not target_chat_id:
            logger.error("No chat_id provided and no default set")
            return False

        if not self.bot_token:
            logger.error("Telegram bot token not configured")
            return False

        url = f"{self.TELEGRAM_API_BASE}{self.bot_token}/sendMessage"
        payload = {
            "chat_id": target_chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_notification": disable_notification,
        }

        try:
            session = await self._get_session()
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    logger.info(f"Telegram message sent to {target_chat_id}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Telegram API error: {response.status} - {error_text}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    async def send_undervalued_alert(
        self,
        listing: Dict[str, Any],
        chat_id: Optional[str] = None,
    ) -> bool:
        """Send formatted alert for undervalued listing.

        Args:
            listing: Listing data with apartment details
            chat_id: Target chat ID

        Returns:
            True if sent successfully
        """
        apartment_name = listing.get("apartment_name", "아파트")
        discount = abs(listing.get("discount_percent", 0))
        price = listing.get("price", 0)
        area = listing.get("area", 0)
        floor = listing.get("floor", "")
        dong_name = listing.get("dong_name", "")

        # Format price
        if price >= 10000:
            price_str = f"{price // 10000}억"
            if price % 10000:
                price_str += f" {price % 10000:,}만원"
            else:
                price_str += "원"
        else:
            price_str = f"{price:,}만원"

        message = f"""🏠 *저평가 매물 알림*

*{apartment_name}*
📍 {dong_name}
💰 {price_str}
📐 {area:.1f}㎡ ({area * 0.3025:.1f}평)
🏢 {floor}층

📉 *유사 매물 대비 {discount:.1f}% 저렴*

[상세보기](https://chat-apt.com/listing/{listing.get('id', '')})
"""
        return await self.send_message(message, chat_id=chat_id)

    async def send_fire_sale_alert(
        self,
        listing: Dict[str, Any],
        chat_id: Optional[str] = None,
    ) -> bool:
        """Send alert for fire sale (urgent sale) listing.

        Args:
            listing: Listing data
            chat_id: Target chat ID

        Returns:
            True if sent successfully
        """
        apartment_name = listing.get("apartment_name", "아파트")
        price = listing.get("price", 0)
        fire_sale_score = listing.get("fire_sale_score", 0)

        # Format price
        if price >= 10000:
            price_str = f"{price // 10000}억"
            if price % 10000:
                price_str += f" {price % 10000:,}만원"
            else:
                price_str += "원"
        else:
            price_str = f"{price:,}만원"

        message = f"""🔥 *급매물 탐지*

*{apartment_name}*
💰 {price_str}
⚡ 급매 점수: {fire_sale_score:.0f}/100

급하게 매물을 내놓은 것으로 추정됩니다.
협상 여지가 있을 수 있습니다.

[상세보기](https://chat-apt.com/listing/{listing.get('id', '')})
"""
        return await self.send_message(message, chat_id=chat_id)

    async def send_price_drop_alert(
        self,
        listing: Dict[str, Any],
        old_price: int,
        new_price: int,
        chat_id: Optional[str] = None,
    ) -> bool:
        """Send alert for price drop.

        Args:
            listing: Listing data
            old_price: Previous price
            new_price: Current price
            chat_id: Target chat ID

        Returns:
            True if sent successfully
        """
        apartment_name = listing.get("apartment_name", "아파트")
        drop_amount = old_price - new_price
        drop_percent = (drop_amount / old_price) * 100

        def format_price(p: int) -> str:
            if p >= 10000:
                result = f"{p // 10000}억"
                if p % 10000:
                    result += f" {p % 10000:,}만"
                return result
            return f"{p:,}만"

        message = f"""📉 *가격 인하 알림*

*{apartment_name}*

~~{format_price(old_price)}원~~ → *{format_price(new_price)}원*

📉 {format_price(drop_amount)}원 인하 (-{drop_percent:.1f}%)

[상세보기](https://chat-apt.com/listing/{listing.get('id', '')})
"""
        return await self.send_message(message, chat_id=chat_id)

    async def send_system_notification(
        self,
        title: str,
        message: str,
        chat_id: Optional[str] = None,
    ) -> bool:
        """Send system notification (crawl status, errors, etc).

        Args:
            title: Notification title
            message: Notification body
            chat_id: Target chat ID

        Returns:
            True if sent successfully
        """
        formatted = f"""📊 *{title}*

{message}

_{datetime.now().strftime('%Y-%m-%d %H:%M:%S KST')}_
"""
        return await self.send_message(formatted, chat_id=chat_id)


# Telegram notifier singleton
_telegram_notifier: Optional[TelegramNotifier] = None


def get_telegram_notifier() -> Optional[TelegramNotifier]:
    """Get the Telegram notifier singleton."""
    global _telegram_notifier
    if _telegram_notifier is None:
        try:
            from app.config import get_settings
            settings = get_settings()
            if settings.telegram_bot_token:
                _telegram_notifier = TelegramNotifier(
                    bot_token=settings.telegram_bot_token,
                    default_chat_id=settings.telegram_chat_id,
                )
        except Exception as e:
            logger.warning(f"Failed to initialize Telegram notifier: {e}")
    return _telegram_notifier


class NotificationService:
    """Service for managing and sending notifications."""

    def __init__(self):
        self._queue: List[NotificationPayload] = []
        self._user_alerts: Dict[str, List[AlertCondition]] = {}
        self._telegram: Optional[TelegramNotifier] = None

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

    @property
    def telegram(self) -> Optional[TelegramNotifier]:
        """Get Telegram notifier (lazy initialization)."""
        if self._telegram is None:
            self._telegram = get_telegram_notifier()
        return self._telegram

    async def send_notification(
        self,
        user_id: str,
        notification: NotificationPayload,
        telegram_chat_id: Optional[str] = None,
    ) -> bool:
        """Send a notification to a user.

        Sends via configured channels:
        - Telegram (if configured)
        - Email (future)
        - Push notification (future)

        Args:
            user_id: Target user ID
            notification: Notification to send
            telegram_chat_id: Optional Telegram chat ID for this user

        Returns:
            True if sent successfully
        """
        # Queue notification for processing
        self._queue.append(notification)

        success = True

        # Send via Telegram if configured
        if self.telegram:
            message = f"*{notification.title}*\n\n{notification.message}"
            telegram_success = await self.telegram.send_message(
                message,
                chat_id=telegram_chat_id,
            )
            if not telegram_success:
                logger.warning(f"Failed to send Telegram notification to user {user_id}")
                success = False

        return success

    async def send_telegram_alert(
        self,
        listing: Dict[str, Any],
        alert_type: str = "undervalued",
        chat_id: Optional[str] = None,
    ) -> bool:
        """Send a listing alert via Telegram.

        Args:
            listing: Listing data
            alert_type: Type of alert (undervalued, fire_sale, price_drop)
            chat_id: Target Telegram chat ID

        Returns:
            True if sent successfully
        """
        if not self.telegram:
            logger.warning("Telegram notifier not configured")
            return False

        if alert_type == "undervalued":
            return await self.telegram.send_undervalued_alert(listing, chat_id)
        elif alert_type == "fire_sale":
            return await self.telegram.send_fire_sale_alert(listing, chat_id)
        else:
            logger.warning(f"Unknown alert type: {alert_type}")
            return False

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
