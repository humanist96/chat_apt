"""TossPayments API client for subscription billing.

This module provides integration with TossPayments for:
- One-time payments
- Recurring subscription billing
- Billing key management
"""
import base64
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

import httpx

from app.config import get_settings


class PaymentStatus(Enum):
    """Payment status codes."""
    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_FOR_DEPOSIT = "WAITING_FOR_DEPOSIT"
    DONE = "DONE"
    CANCELED = "CANCELED"
    PARTIAL_CANCELED = "PARTIAL_CANCELED"
    ABORTED = "ABORTED"
    EXPIRED = "EXPIRED"


@dataclass
class PaymentResult:
    """Payment result from TossPayments."""
    payment_key: str
    order_id: str
    status: str
    amount: int
    method: Optional[str] = None
    approved_at: Optional[str] = None
    card_company: Optional[str] = None
    card_number: Optional[str] = None
    receipt_url: Optional[str] = None
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None


@dataclass
class BillingKeyResult:
    """Billing key issuance result."""
    billing_key: str
    customer_key: str
    card_company: str
    card_number: str
    authenticated_at: str


class TossPaymentsClient:
    """Client for TossPayments API.

    Handles payment processing and subscription billing.
    API Documentation: https://docs.tosspayments.com/
    """

    BASE_URL = "https://api.tosspayments.com/v1"

    def __init__(
        self,
        client_key: Optional[str] = None,
        secret_key: Optional[str] = None,
    ):
        """Initialize the TossPayments client.

        Args:
            client_key: TossPayments client key (for frontend)
            secret_key: TossPayments secret key (for API calls)
        """
        settings = get_settings()
        self.client_key = client_key or settings.toss_client_key
        self.secret_key = secret_key or settings.toss_secret_key
        self._client: Optional[httpx.AsyncClient] = None

    def _get_auth_header(self) -> str:
        """Generate Basic Auth header."""
        credentials = f"{self.secret_key}:"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "Authorization": self._get_auth_header(),
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make an API request.

        Args:
            method: HTTP method
            endpoint: API endpoint
            data: Request payload

        Returns:
            Response JSON

        Raises:
            TossPaymentsError: If request fails
        """
        client = await self._get_client()
        url = f"{self.BASE_URL}{endpoint}"

        try:
            if method == "GET":
                response = await client.get(url, params=data)
            elif method == "POST":
                response = await client.post(url, json=data)
            else:
                raise ValueError(f"Unsupported method: {method}")

            response_data = response.json()

            if response.status_code >= 400:
                raise TossPaymentsError(
                    code=response_data.get("code", "UNKNOWN"),
                    message=response_data.get("message", "Unknown error"),
                )

            return response_data

        except httpx.HTTPError as e:
            raise TossPaymentsError(
                code="NETWORK_ERROR",
                message=str(e),
            )

    # ========== Payment Methods ==========

    async def confirm_payment(
        self,
        payment_key: str,
        order_id: str,
        amount: int,
    ) -> PaymentResult:
        """Confirm a payment after user approval.

        Args:
            payment_key: Payment key from TossPayments
            order_id: Your order ID
            amount: Payment amount

        Returns:
            PaymentResult with payment details
        """
        data = {
            "paymentKey": payment_key,
            "orderId": order_id,
            "amount": amount,
        }

        response = await self._request("POST", "/payments/confirm", data)

        return PaymentResult(
            payment_key=response["paymentKey"],
            order_id=response["orderId"],
            status=response["status"],
            amount=response["totalAmount"],
            method=response.get("method"),
            approved_at=response.get("approvedAt"),
            card_company=response.get("card", {}).get("company"),
            card_number=response.get("card", {}).get("number"),
            receipt_url=response.get("receipt", {}).get("url"),
        )

    async def get_payment(self, payment_key: str) -> PaymentResult:
        """Get payment details.

        Args:
            payment_key: Payment key

        Returns:
            PaymentResult with payment details
        """
        response = await self._request("GET", f"/payments/{payment_key}")

        return PaymentResult(
            payment_key=response["paymentKey"],
            order_id=response["orderId"],
            status=response["status"],
            amount=response["totalAmount"],
            method=response.get("method"),
            approved_at=response.get("approvedAt"),
            card_company=response.get("card", {}).get("company"),
            card_number=response.get("card", {}).get("number"),
            receipt_url=response.get("receipt", {}).get("url"),
        )

    async def cancel_payment(
        self,
        payment_key: str,
        cancel_reason: str,
        cancel_amount: Optional[int] = None,
    ) -> PaymentResult:
        """Cancel a payment.

        Args:
            payment_key: Payment key
            cancel_reason: Reason for cancellation
            cancel_amount: Partial cancel amount (None for full cancel)

        Returns:
            PaymentResult with updated status
        """
        data = {"cancelReason": cancel_reason}
        if cancel_amount is not None:
            data["cancelAmount"] = cancel_amount

        response = await self._request(
            "POST",
            f"/payments/{payment_key}/cancel",
            data,
        )

        return PaymentResult(
            payment_key=response["paymentKey"],
            order_id=response["orderId"],
            status=response["status"],
            amount=response["totalAmount"],
        )

    # ========== Billing (Subscription) Methods ==========

    async def issue_billing_key(
        self,
        auth_key: str,
        customer_key: str,
    ) -> BillingKeyResult:
        """Issue a billing key for recurring payments.

        Args:
            auth_key: Authentication key from card registration
            customer_key: Your customer ID

        Returns:
            BillingKeyResult with billing key
        """
        data = {
            "authKey": auth_key,
            "customerKey": customer_key,
        }

        response = await self._request("POST", "/billing/authorizations/issue", data)

        return BillingKeyResult(
            billing_key=response["billingKey"],
            customer_key=response["customerKey"],
            card_company=response.get("card", {}).get("company", ""),
            card_number=response.get("card", {}).get("number", ""),
            authenticated_at=response.get("authenticatedAt", ""),
        )

    async def charge_with_billing_key(
        self,
        billing_key: str,
        customer_key: str,
        amount: int,
        order_id: str,
        order_name: str,
    ) -> PaymentResult:
        """Charge a customer using their billing key.

        Args:
            billing_key: Customer's billing key
            customer_key: Your customer ID
            amount: Charge amount
            order_id: Your order ID
            order_name: Order description

        Returns:
            PaymentResult with payment details
        """
        data = {
            "customerKey": customer_key,
            "amount": amount,
            "orderId": order_id,
            "orderName": order_name,
        }

        response = await self._request(
            "POST",
            f"/billing/{billing_key}",
            data,
        )

        return PaymentResult(
            payment_key=response["paymentKey"],
            order_id=response["orderId"],
            status=response["status"],
            amount=response["totalAmount"],
            method=response.get("method"),
            approved_at=response.get("approvedAt"),
            card_company=response.get("card", {}).get("company"),
            card_number=response.get("card", {}).get("number"),
            receipt_url=response.get("receipt", {}).get("url"),
        )


class TossPaymentsError(Exception):
    """Exception for TossPayments API errors."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


# Subscription plan definitions
SUBSCRIPTION_PLANS = {
    "basic": {
        "name": "Basic",
        "price": 9900,
        "features": [
            "일 100회 매물 검색",
            "유사 매물 비교 분석",
            "저평가 리포트 (일 5건)",
        ],
    },
    "premium": {
        "name": "Premium",
        "price": 29900,
        "features": [
            "무제한 매물 검색",
            "무제한 유사 매물 분석",
            "무제한 저평가 리포트",
            "실시간 급매 알림",
            "API 액세스",
        ],
    },
}
