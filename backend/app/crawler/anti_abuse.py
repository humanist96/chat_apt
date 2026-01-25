"""Anti-abuse utilities for web crawling.

This module provides strategies to avoid detection and blocking
when crawling websites like Naver Real Estate.
"""
import random
import time
import asyncio
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from app.config import get_settings


@dataclass
class RequestDelay:
    """Configurable delay generator for humanizing request patterns."""

    min_delay: float = 3.0  # Minimum delay in seconds
    max_delay: float = 8.0  # Maximum delay in seconds
    use_gaussian: bool = True  # Use Gaussian distribution
    mean: float = 5.0  # Mean for Gaussian
    std_dev: float = 1.5  # Standard deviation for Gaussian

    def get_delay(self) -> float:
        """Generate a randomized delay.

        Returns:
            Delay in seconds
        """
        if self.use_gaussian:
            delay = random.gauss(self.mean, self.std_dev)
            # Clamp to min/max range
            return max(self.min_delay, min(self.max_delay, delay))
        else:
            return random.uniform(self.min_delay, self.max_delay)

    async def wait(self) -> float:
        """Wait for the generated delay.

        Returns:
            The actual delay waited
        """
        delay = self.get_delay()
        await asyncio.sleep(delay)
        return delay


# Common user agents for rotation
USER_AGENTS = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Chrome on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Safari on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    # Mobile Chrome (Android)
    "Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
]


class ProxyManager:
    """Manages proxy rotation for distributed requests."""

    def __init__(self, proxy_list: Optional[List[str]] = None):
        """Initialize proxy manager.

        Args:
            proxy_list: List of proxy URLs (http://host:port)
        """
        settings = get_settings()

        if proxy_list:
            self.proxies = proxy_list
        elif settings.proxy_list:
            self.proxies = [p.strip() for p in settings.proxy_list.split(",") if p.strip()]
        else:
            self.proxies = []

        self._current_index = 0
        self._failed_proxies: Dict[str, datetime] = {}
        self._cooldown_seconds = 300  # 5 minutes cooldown for failed proxies

    def get_proxy(self) -> Optional[str]:
        """Get next available proxy.

        Returns:
            Proxy URL or None if no proxies available
        """
        if not self.proxies:
            return None

        # Filter out proxies still in cooldown
        now = datetime.now()
        available = [
            p for p in self.proxies
            if p not in self._failed_proxies
            or (now - self._failed_proxies[p]).total_seconds() > self._cooldown_seconds
        ]

        if not available:
            # All proxies are in cooldown, use round-robin anyway
            available = self.proxies

        # Round-robin selection
        proxy = available[self._current_index % len(available)]
        self._current_index += 1

        return proxy

    def mark_failed(self, proxy: str):
        """Mark a proxy as failed.

        Args:
            proxy: The proxy URL that failed
        """
        self._failed_proxies[proxy] = datetime.now()

    def mark_success(self, proxy: str):
        """Mark a proxy as working.

        Args:
            proxy: The proxy URL that worked
        """
        self._failed_proxies.pop(proxy, None)


class AntiAbuseManager:
    """Manages anti-abuse strategies for crawling."""

    def __init__(
        self,
        request_delay: Optional[RequestDelay] = None,
        proxy_manager: Optional[ProxyManager] = None,
    ):
        """Initialize anti-abuse manager.

        Args:
            request_delay: Custom delay configuration
            proxy_manager: Custom proxy manager
        """
        self.delay = request_delay or RequestDelay()
        self.proxy_manager = proxy_manager or ProxyManager()
        self._request_count = 0
        self._last_request_time: Optional[float] = None

    def get_random_user_agent(self) -> str:
        """Get a random user agent string.

        Returns:
            User agent string
        """
        return random.choice(USER_AGENTS)

    def get_headers(self) -> Dict[str, str]:
        """Get request headers with randomized user agent.

        Returns:
            Headers dict
        """
        return {
            "User-Agent": self.get_random_user_agent(),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }

    def get_proxy(self) -> Optional[str]:
        """Get a proxy URL.

        Returns:
            Proxy URL or None
        """
        return self.proxy_manager.get_proxy()

    async def pre_request(self) -> Dict[str, Any]:
        """Prepare for a request.

        This should be called before each request to apply delays
        and get necessary configuration.

        Returns:
            Dict with headers and proxy configuration
        """
        # Apply delay
        if self._last_request_time is not None:
            await self.delay.wait()

        self._last_request_time = time.time()
        self._request_count += 1

        return {
            "headers": self.get_headers(),
            "proxy": self.get_proxy(),
        }

    def on_request_success(self, proxy: Optional[str] = None):
        """Called when a request succeeds.

        Args:
            proxy: The proxy used (if any)
        """
        if proxy:
            self.proxy_manager.mark_success(proxy)

    def on_request_failure(self, proxy: Optional[str] = None, is_blocked: bool = False):
        """Called when a request fails.

        Args:
            proxy: The proxy used (if any)
            is_blocked: Whether the failure was due to blocking
        """
        if proxy:
            self.proxy_manager.mark_failed(proxy)

        if is_blocked:
            # Increase delays when blocked
            self.delay.min_delay *= 1.5
            self.delay.max_delay *= 1.5
            self.delay.mean *= 1.5

    @staticmethod
    def is_blocked_response(status_code: int, response_text: str = "") -> bool:
        """Check if a response indicates blocking.

        Args:
            status_code: HTTP status code
            response_text: Response body text

        Returns:
            True if the response indicates blocking
        """
        # Common blocking indicators
        blocked_codes = {403, 429, 503, 520, 521, 522, 523, 524}

        if status_code in blocked_codes:
            return True

        # Check for CAPTCHA or blocking keywords in response
        blocking_keywords = [
            "captcha",
            "blocked",
            "too many requests",
            "rate limit",
            "access denied",
            "보안 문자",
            "자동화된 요청",
        ]

        response_lower = response_text.lower()
        return any(keyword in response_lower for keyword in blocking_keywords)


class ExponentialBackoff:
    """Exponential backoff strategy for retries."""

    def __init__(
        self,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        multiplier: float = 2.0,
        max_retries: int = 5,
    ):
        """Initialize backoff configuration.

        Args:
            initial_delay: Initial delay in seconds
            max_delay: Maximum delay cap
            multiplier: Multiplier for each retry
            max_retries: Maximum number of retries
        """
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.multiplier = multiplier
        self.max_retries = max_retries
        self._current_retry = 0

    def get_delay(self) -> float:
        """Get the delay for the current retry.

        Returns:
            Delay in seconds
        """
        delay = self.initial_delay * (self.multiplier ** self._current_retry)
        # Add jitter (±10%)
        jitter = delay * 0.1 * (random.random() * 2 - 1)
        return min(self.max_delay, delay + jitter)

    async def wait(self) -> bool:
        """Wait for the backoff delay.

        Returns:
            True if should retry, False if max retries exceeded
        """
        if self._current_retry >= self.max_retries:
            return False

        delay = self.get_delay()
        await asyncio.sleep(delay)
        self._current_retry += 1
        return True

    def reset(self):
        """Reset the retry counter."""
        self._current_retry = 0

    @property
    def retries_remaining(self) -> int:
        """Number of retries remaining."""
        return max(0, self.max_retries - self._current_retry)
