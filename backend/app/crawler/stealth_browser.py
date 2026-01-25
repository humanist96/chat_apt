"""Stealth browser for bypassing bot detection.

This module provides a Playwright-based browser with
anti-detection features for crawling protected websites.
"""
import asyncio
import random
import logging
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

from app.crawler.anti_abuse import USER_AGENTS, AntiAbuseManager


logger = logging.getLogger(__name__)


# JavaScript to inject for stealth mode
STEALTH_SCRIPTS = """
// Overwrite navigator.webdriver
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined,
});

// Add chrome object
window.chrome = {
    runtime: {},
    loadTimes: function() {},
    csi: function() {},
    app: {},
};

// Overwrite permissions
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        originalQuery(parameters)
);

// Fix iframe contentWindow
Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
    get: function() {
        return window;
    }
});

// Randomize canvas fingerprint
const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
HTMLCanvasElement.prototype.toDataURL = function(type) {
    if (type === 'image/png' && this.width === 16 && this.height === 16) {
        // Fingerprint canvas, add noise
        const context = this.getContext('2d');
        const imageData = context.getImageData(0, 0, this.width, this.height);
        for (let i = 0; i < imageData.data.length; i += 4) {
            imageData.data[i] = imageData.data[i] + Math.floor(Math.random() * 10 - 5);
        }
        context.putImageData(imageData, 0, 0);
    }
    return originalToDataURL.apply(this, arguments);
};

// Fix languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['ko-KR', 'ko', 'en-US', 'en'],
});

// Fix plugins
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5],
});

// Fix platform
Object.defineProperty(navigator, 'platform', {
    get: () => 'Win32',
});

// Disable automation flags
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
"""


class StealthBrowser:
    """Playwright-based stealth browser for bypassing bot detection."""

    def __init__(
        self,
        headless: bool = True,
        proxy: Optional[str] = None,
        user_agent: Optional[str] = None,
        viewport_width: int = 1920,
        viewport_height: int = 1080,
    ):
        """Initialize stealth browser.

        Args:
            headless: Run in headless mode
            proxy: Proxy URL (http://host:port)
            user_agent: Custom user agent
            viewport_width: Browser viewport width
            viewport_height: Browser viewport height
        """
        self.headless = headless
        self.proxy = proxy
        self.user_agent = user_agent or random.choice(USER_AGENTS)
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height

        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    async def start(self):
        """Start the browser."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError(
                "Playwright is not installed. "
                "Run: pip install playwright && playwright install chromium"
            )

        self._playwright = await async_playwright().start()

        # Browser launch arguments for stealth
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--disable-infobars",
            "--disable-background-networking",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-breakpad",
            "--disable-component-extensions-with-background-pages",
            "--disable-component-update",
            "--disable-default-apps",
            "--disable-extensions",
            "--disable-features=TranslateUI",
            "--disable-hang-monitor",
            "--disable-ipc-flooding-protection",
            "--disable-popup-blocking",
            "--disable-prompt-on-repost",
            "--disable-renderer-backgrounding",
            "--disable-sync",
            "--enable-features=NetworkService,NetworkServiceInProcess",
            "--force-color-profile=srgb",
            "--metrics-recording-only",
            "--no-first-run",
            "--password-store=basic",
            "--use-mock-keychain",
            "--no-sandbox",
        ]

        # Proxy configuration
        proxy_config = None
        if self.proxy:
            proxy_config = {"server": self.proxy}

        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=launch_args,
            proxy=proxy_config,
        )

        # Create context with anti-detection settings
        self._context = await self._browser.new_context(
            viewport={"width": self.viewport_width, "height": self.viewport_height},
            user_agent=self.user_agent,
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            geolocation={"longitude": 126.9780, "latitude": 37.5665},  # Seoul
            permissions=["geolocation"],
            java_script_enabled=True,
            bypass_csp=True,
        )

        # Inject stealth scripts before any page loads
        await self._context.add_init_script(STEALTH_SCRIPTS)

        self._page = await self._context.new_page()

        # Set extra HTTP headers
        await self._page.set_extra_http_headers({
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        })

        logger.info("StealthBrowser started successfully")
        return self

    async def close(self):
        """Close the browser."""
        if self._page:
            await self._page.close()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None

        logger.info("StealthBrowser closed")

    @asynccontextmanager
    async def session(self):
        """Context manager for browser session."""
        await self.start()
        try:
            yield self
        finally:
            await self.close()

    async def goto(
        self,
        url: str,
        wait_until: str = "networkidle",
        timeout: int = 30000,
    ) -> Dict[str, Any]:
        """Navigate to URL.

        Args:
            url: URL to navigate to
            wait_until: Wait condition (load, domcontentloaded, networkidle)
            timeout: Navigation timeout in milliseconds

        Returns:
            Response info dict
        """
        if not self._page:
            raise RuntimeError("Browser not started. Call start() first.")

        response = await self._page.goto(
            url,
            wait_until=wait_until,
            timeout=timeout,
        )

        return {
            "url": response.url if response else url,
            "status": response.status if response else None,
            "ok": response.ok if response else False,
        }

    async def get_content(self) -> str:
        """Get page HTML content."""
        if not self._page:
            raise RuntimeError("Browser not started.")
        return await self._page.content()

    async def get_text(self) -> str:
        """Get page text content."""
        if not self._page:
            raise RuntimeError("Browser not started.")
        return await self._page.inner_text("body")

    async def evaluate(self, expression: str) -> Any:
        """Evaluate JavaScript expression.

        Args:
            expression: JavaScript code to evaluate

        Returns:
            Result of evaluation
        """
        if not self._page:
            raise RuntimeError("Browser not started.")
        return await self._page.evaluate(expression)

    async def get_json_from_script(self, variable_name: str) -> Optional[Dict]:
        """Extract JSON data from a JavaScript variable.

        Args:
            variable_name: Name of the JS variable containing JSON

        Returns:
            Parsed JSON or None
        """
        try:
            return await self.evaluate(f"JSON.parse(JSON.stringify({variable_name}))")
        except Exception:
            return None

    async def wait_for_selector(
        self,
        selector: str,
        timeout: int = 10000,
    ) -> bool:
        """Wait for element to appear.

        Args:
            selector: CSS selector
            timeout: Timeout in milliseconds

        Returns:
            True if element found, False if timeout
        """
        if not self._page:
            raise RuntimeError("Browser not started.")
        try:
            await self._page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception:
            return False

    async def click(self, selector: str):
        """Click an element."""
        if not self._page:
            raise RuntimeError("Browser not started.")
        await self._page.click(selector)

    async def type_text(self, selector: str, text: str, delay: int = 100):
        """Type text into an input with human-like delay.

        Args:
            selector: CSS selector for input
            text: Text to type
            delay: Delay between keystrokes in milliseconds
        """
        if not self._page:
            raise RuntimeError("Browser not started.")
        await self._page.type(selector, text, delay=delay)

    async def scroll_page(self, scroll_amount: int = 500):
        """Scroll page down.

        Args:
            scroll_amount: Pixels to scroll
        """
        if not self._page:
            raise RuntimeError("Browser not started.")
        await self._page.evaluate(f"window.scrollBy(0, {scroll_amount})")

    async def random_mouse_movement(self):
        """Perform random mouse movements to appear human."""
        if not self._page:
            return

        for _ in range(random.randint(2, 5)):
            x = random.randint(100, self.viewport_width - 100)
            y = random.randint(100, self.viewport_height - 100)
            await self._page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.1, 0.3))

    async def screenshot(self, path: str):
        """Take a screenshot.

        Args:
            path: File path to save screenshot
        """
        if not self._page:
            raise RuntimeError("Browser not started.")
        await self._page.screenshot(path=path)

    async def fetch_api(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        body: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch API endpoint using browser's fetch.

        This bypasses some anti-bot protections by using the
        browser's JavaScript context.

        Args:
            url: API URL
            method: HTTP method
            headers: Optional headers
            body: Optional request body

        Returns:
            Response with status and data
        """
        if not self._page:
            raise RuntimeError("Browser not started.")

        fetch_code = f"""
        async () => {{
            try {{
                const response = await fetch("{url}", {{
                    method: "{method}",
                    headers: {headers or {}},
                    {"body: '" + body + "'," if body else ""}
                    credentials: 'include',
                }});

                const contentType = response.headers.get("content-type");
                let data;

                if (contentType && contentType.includes("application/json")) {{
                    data = await response.json();
                }} else {{
                    data = await response.text();
                }}

                return {{
                    ok: response.ok,
                    status: response.status,
                    data: data,
                }};
            }} catch (error) {{
                return {{
                    ok: false,
                    status: 0,
                    error: error.message,
                }};
            }}
        }}
        """

        return await self._page.evaluate(fetch_code)


class StealthCrawler:
    """High-level crawler using StealthBrowser with anti-abuse features."""

    def __init__(
        self,
        anti_abuse: Optional[AntiAbuseManager] = None,
        headless: bool = True,
    ):
        """Initialize stealth crawler.

        Args:
            anti_abuse: Anti-abuse manager for delays and proxy rotation
            headless: Run browser in headless mode
        """
        self.anti_abuse = anti_abuse or AntiAbuseManager()
        self.headless = headless
        self._browser: Optional[StealthBrowser] = None

    async def _get_browser(self) -> StealthBrowser:
        """Get or create browser instance."""
        if self._browser is None:
            proxy = self.anti_abuse.get_proxy()
            user_agent = self.anti_abuse.get_random_user_agent()

            self._browser = StealthBrowser(
                headless=self.headless,
                proxy=proxy,
                user_agent=user_agent,
            )
            await self._browser.start()

        return self._browser

    async def close(self):
        """Close the browser."""
        if self._browser:
            await self._browser.close()
            self._browser = None

    async def fetch_with_browser(
        self,
        url: str,
        wait_until: str = "networkidle",
        retry_on_block: bool = True,
    ) -> Dict[str, Any]:
        """Fetch URL using stealth browser.

        Args:
            url: URL to fetch
            wait_until: Wait condition
            retry_on_block: Retry with new browser if blocked

        Returns:
            Response dict with content and status
        """
        await self.anti_abuse.pre_request()

        browser = await self._get_browser()

        try:
            result = await browser.goto(url, wait_until=wait_until)

            if not result["ok"]:
                if retry_on_block and result["status"] in (403, 429, 503):
                    # Close current browser and try with new proxy
                    await self.close()
                    self.anti_abuse.on_request_failure(is_blocked=True)

                    # Wait and retry
                    await asyncio.sleep(random.uniform(5, 10))
                    return await self.fetch_with_browser(
                        url,
                        wait_until=wait_until,
                        retry_on_block=False,
                    )

            content = await browser.get_content()

            self.anti_abuse.on_request_success()

            return {
                "ok": result["ok"],
                "status": result["status"],
                "url": result["url"],
                "content": content,
            }

        except Exception as e:
            logger.error(f"Browser fetch failed: {e}")
            self.anti_abuse.on_request_failure(is_blocked=True)
            return {
                "ok": False,
                "status": 0,
                "error": str(e),
                "content": None,
            }

    async def fetch_api_with_browser(
        self,
        base_url: str,
        api_url: str,
    ) -> Dict[str, Any]:
        """Fetch API using browser context.

        First navigates to base_url to establish cookies/session,
        then fetches the API endpoint.

        Args:
            base_url: Base URL to establish session
            api_url: API URL to fetch

        Returns:
            API response dict
        """
        await self.anti_abuse.pre_request()

        browser = await self._get_browser()

        try:
            # Navigate to base URL first
            await browser.goto(base_url, wait_until="domcontentloaded")

            # Random delay
            await asyncio.sleep(random.uniform(1, 2))

            # Perform human-like actions
            await browser.random_mouse_movement()

            # Fetch API
            result = await browser.fetch_api(api_url)

            self.anti_abuse.on_request_success()

            return result

        except Exception as e:
            logger.error(f"API fetch failed: {e}")
            self.anti_abuse.on_request_failure(is_blocked=True)
            return {
                "ok": False,
                "status": 0,
                "error": str(e),
            }
