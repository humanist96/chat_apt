"""Tests for payment module."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from app.services.toss_payments import (
    TossPaymentsClient,
    TossPaymentsError,
    PaymentResult,
    BillingKeyResult,
    PaymentStatus,
    SUBSCRIPTION_PLANS,
)


class TestSubscriptionPlans:
    """Tests for subscription plan definitions."""

    def test_plans_defined(self):
        """Test that subscription plans are defined."""
        assert "basic" in SUBSCRIPTION_PLANS
        assert "premium" in SUBSCRIPTION_PLANS

    def test_basic_plan_details(self):
        """Test basic plan details."""
        basic = SUBSCRIPTION_PLANS["basic"]
        assert basic["name"] == "Basic"
        assert basic["price"] == 9900
        assert len(basic["features"]) > 0

    def test_premium_plan_details(self):
        """Test premium plan details."""
        premium = SUBSCRIPTION_PLANS["premium"]
        assert premium["name"] == "Premium"
        assert premium["price"] == 29900
        assert premium["price"] > SUBSCRIPTION_PLANS["basic"]["price"]


class TestPaymentResult:
    """Tests for PaymentResult dataclass."""

    def test_payment_result_creation(self):
        """Test creating a PaymentResult."""
        result = PaymentResult(
            payment_key="pk_test_123",
            order_id="order_456",
            status="DONE",
            amount=9900,
            method="카드",
            approved_at="2024-01-15T12:00:00+09:00",
            card_company="삼성",
            card_number="1234****5678",
        )

        assert result.payment_key == "pk_test_123"
        assert result.order_id == "order_456"
        assert result.status == "DONE"
        assert result.amount == 9900

    def test_payment_result_optional_fields(self):
        """Test PaymentResult with minimal fields."""
        result = PaymentResult(
            payment_key="pk_test_789",
            order_id="order_abc",
            status="READY",
            amount=29900,
        )

        assert result.method is None
        assert result.approved_at is None
        assert result.receipt_url is None


class TestBillingKeyResult:
    """Tests for BillingKeyResult dataclass."""

    def test_billing_key_result_creation(self):
        """Test creating a BillingKeyResult."""
        result = BillingKeyResult(
            billing_key="bk_test_abc123",
            customer_key="user_123",
            card_company="삼성카드",
            card_number="1234****5678",
            authenticated_at="2024-01-15T12:00:00+09:00",
        )

        assert result.billing_key == "bk_test_abc123"
        assert result.customer_key == "user_123"
        assert result.card_company == "삼성카드"


class TestPaymentStatus:
    """Tests for PaymentStatus enum."""

    def test_status_values(self):
        """Test payment status values."""
        assert PaymentStatus.READY.value == "READY"
        assert PaymentStatus.DONE.value == "DONE"
        assert PaymentStatus.CANCELED.value == "CANCELED"
        assert PaymentStatus.EXPIRED.value == "EXPIRED"


class TestTossPaymentsError:
    """Tests for TossPaymentsError exception."""

    def test_error_creation(self):
        """Test creating a TossPaymentsError."""
        error = TossPaymentsError(
            code="INVALID_CARD_NUMBER",
            message="유효하지 않은 카드 번호입니다",
        )

        assert error.code == "INVALID_CARD_NUMBER"
        assert error.message == "유효하지 않은 카드 번호입니다"
        assert "INVALID_CARD_NUMBER" in str(error)

    def test_error_str(self):
        """Test error string representation."""
        error = TossPaymentsError(code="TEST", message="Test message")
        assert str(error) == "[TEST] Test message"


class TestTossPaymentsClient:
    """Tests for TossPaymentsClient."""

    def test_client_initialization(self):
        """Test client initialization."""
        client = TossPaymentsClient(
            client_key="ck_test_123",
            secret_key="sk_test_456",
        )

        assert client.client_key == "ck_test_123"
        assert client.secret_key == "sk_test_456"

    def test_auth_header_generation(self):
        """Test Basic Auth header generation."""
        client = TossPaymentsClient(
            client_key="ck_test",
            secret_key="sk_test_secret",
        )

        header = client._get_auth_header()

        assert header.startswith("Basic ")
        # Should be base64 encoded "sk_test_secret:"

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test using client as context manager."""
        async with TossPaymentsClient(
            client_key="ck_test",
            secret_key="sk_test",
        ) as client:
            assert client is not None

    @pytest.mark.asyncio
    async def test_confirm_payment_mocked(self):
        """Test confirm_payment with mocked response."""
        client = TossPaymentsClient(
            client_key="ck_test",
            secret_key="sk_test",
        )

        mock_response = {
            "paymentKey": "pk_test_123",
            "orderId": "order_456",
            "status": "DONE",
            "totalAmount": 9900,
            "method": "카드",
            "approvedAt": "2024-01-15T12:00:00+09:00",
            "card": {
                "company": "삼성",
                "number": "1234****5678",
            },
            "receipt": {
                "url": "https://receipt.tosspayments.com/...",
            },
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response

            result = await client.confirm_payment(
                payment_key="pk_test_123",
                order_id="order_456",
                amount=9900,
            )

            assert result.payment_key == "pk_test_123"
            assert result.status == "DONE"
            assert result.amount == 9900
            assert result.card_company == "삼성"

        await client.close()

    @pytest.mark.asyncio
    async def test_issue_billing_key_mocked(self):
        """Test issue_billing_key with mocked response."""
        client = TossPaymentsClient(
            client_key="ck_test",
            secret_key="sk_test",
        )

        mock_response = {
            "billingKey": "bk_test_abc",
            "customerKey": "user_123",
            "card": {
                "company": "신한",
                "number": "5678****1234",
            },
            "authenticatedAt": "2024-01-15T12:00:00+09:00",
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response

            result = await client.issue_billing_key(
                auth_key="auth_key_123",
                customer_key="user_123",
            )

            assert result.billing_key == "bk_test_abc"
            assert result.customer_key == "user_123"
            assert result.card_company == "신한"

        await client.close()

    @pytest.mark.asyncio
    async def test_charge_with_billing_key_mocked(self):
        """Test charge_with_billing_key with mocked response."""
        client = TossPaymentsClient(
            client_key="ck_test",
            secret_key="sk_test",
        )

        mock_response = {
            "paymentKey": "pk_billing_123",
            "orderId": "SUB-user123-20240115",
            "status": "DONE",
            "totalAmount": 29900,
            "method": "카드",
            "approvedAt": "2024-01-15T12:00:00+09:00",
            "card": {
                "company": "현대",
                "number": "9999****0000",
            },
            "receipt": {
                "url": "https://receipt.tosspayments.com/...",
            },
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response

            result = await client.charge_with_billing_key(
                billing_key="bk_test_abc",
                customer_key="user_123",
                amount=29900,
                order_id="SUB-user123-20240115",
                order_name="Chat APT Premium 구독",
            )

            assert result.payment_key == "pk_billing_123"
            assert result.status == "DONE"
            assert result.amount == 29900

        await client.close()

    @pytest.mark.asyncio
    async def test_cancel_payment_mocked(self):
        """Test cancel_payment with mocked response."""
        client = TossPaymentsClient(
            client_key="ck_test",
            secret_key="sk_test",
        )

        mock_response = {
            "paymentKey": "pk_test_123",
            "orderId": "order_456",
            "status": "CANCELED",
            "totalAmount": 9900,
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response

            result = await client.cancel_payment(
                payment_key="pk_test_123",
                cancel_reason="고객 요청에 의한 취소",
            )

            assert result.status == "CANCELED"

        await client.close()

    @pytest.mark.asyncio
    async def test_get_payment_mocked(self):
        """Test get_payment with mocked response."""
        client = TossPaymentsClient(
            client_key="ck_test",
            secret_key="sk_test",
        )

        mock_response = {
            "paymentKey": "pk_test_123",
            "orderId": "order_456",
            "status": "DONE",
            "totalAmount": 9900,
            "method": "카드",
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response

            result = await client.get_payment("pk_test_123")

            assert result.payment_key == "pk_test_123"
            assert result.status == "DONE"

        await client.close()
