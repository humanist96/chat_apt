"""Payment API endpoints for subscription management."""
from typing import Optional
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.auth import get_current_user, AuthenticatedUser
from app.models.user import UserProfile
from app.models.payment import Subscription, PaymentHistory
from app.services.toss_payments import (
    TossPaymentsClient,
    TossPaymentsError,
    SUBSCRIPTION_PLANS,
)


router = APIRouter()


# ========== Request/Response Models ==========

class SubscriptionCreateRequest(BaseModel):
    """Request to create a subscription."""
    plan: str  # basic or premium
    auth_key: str  # From TossPayments card registration


class PaymentConfirmRequest(BaseModel):
    """Request to confirm a payment."""
    payment_key: str
    order_id: str
    amount: int


class SubscriptionResponse(BaseModel):
    """Subscription response schema."""
    id: int
    plan: str
    status: str
    current_period_start: Optional[datetime]
    current_period_end: Optional[datetime]
    cancel_at_period_end: bool

    class Config:
        from_attributes = True


class PaymentHistoryResponse(BaseModel):
    """Payment history response schema."""
    id: int
    amount: int
    status: Optional[str]
    paid_at: Optional[datetime]

    class Config:
        from_attributes = True


class PlanInfoResponse(BaseModel):
    """Plan information response."""
    plan_id: str
    name: str
    price: int
    features: list[str]


# ========== Endpoints ==========

@router.get("/plans", response_model=list[PlanInfoResponse])
async def get_subscription_plans():
    """Get available subscription plans."""
    return [
        PlanInfoResponse(
            plan_id=plan_id,
            name=info["name"],
            price=info["price"],
            features=info["features"],
        )
        for plan_id, info in SUBSCRIPTION_PLANS.items()
    ]


@router.get("/subscription", response_model=Optional[SubscriptionResponse])
async def get_current_subscription(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's subscription."""
    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == UUID(user.id))
        .where(Subscription.status == "active")
        .order_by(Subscription.created_at.desc())
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        return None

    return subscription


@router.post("/subscription", response_model=SubscriptionResponse)
async def create_subscription(
    request: SubscriptionCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new subscription with billing key.

    This endpoint:
    1. Issues a billing key using the auth_key from card registration
    2. Charges the first month
    3. Creates the subscription record
    """
    # Validate plan
    if request.plan not in SUBSCRIPTION_PLANS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan: {request.plan}",
        )

    plan_info = SUBSCRIPTION_PLANS[request.plan]
    user_uuid = UUID(user.id)

    # Check for existing active subscription
    existing = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user_uuid)
        .where(Subscription.status == "active")
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have an active subscription",
        )

    async with TossPaymentsClient() as toss:
        try:
            # Issue billing key
            billing_result = await toss.issue_billing_key(
                auth_key=request.auth_key,
                customer_key=user.id,
            )

            # Charge first payment
            now = datetime.utcnow()
            order_id = f"SUB-{user.id[:8]}-{now.strftime('%Y%m%d%H%M%S')}"

            payment_result = await toss.charge_with_billing_key(
                billing_key=billing_result.billing_key,
                customer_key=user.id,
                amount=plan_info["price"],
                order_id=order_id,
                order_name=f"Chat APT {plan_info['name']} 구독",
            )

            # Create subscription record
            subscription = Subscription(
                user_id=user_uuid,
                plan=request.plan,
                status="active",
                billing_key=billing_result.billing_key,
                current_period_start=now,
                current_period_end=now + timedelta(days=30),
            )
            db.add(subscription)

            # Create payment history
            payment_history = PaymentHistory(
                user_id=user_uuid,
                subscription_id=subscription.id,
                amount=plan_info["price"],
                status="success",
                payment_key=payment_result.payment_key,
                order_id=order_id,
                paid_at=now,
            )
            db.add(payment_history)

            # Update user tier
            user_result = await db.execute(
                select(UserProfile).where(UserProfile.id == user_uuid)
            )
            user_profile = user_result.scalar_one_or_none()
            if user_profile:
                user_profile.membership_tier = request.plan

            await db.flush()
            await db.refresh(subscription)

            return subscription

        except TossPaymentsError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Payment failed: {e.message}",
            )


@router.post("/subscription/cancel")
async def cancel_subscription(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel current subscription (at period end)."""
    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == UUID(user.id))
        .where(Subscription.status == "active")
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found",
        )

    subscription.cancel_at_period_end = True
    await db.flush()

    return {
        "message": "Subscription will be cancelled at the end of the billing period",
        "ends_at": subscription.current_period_end,
    }


@router.post("/subscription/reactivate")
async def reactivate_subscription(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reactivate a cancelled subscription."""
    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == UUID(user.id))
        .where(Subscription.status == "active")
        .where(Subscription.cancel_at_period_end == True)
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No cancelled subscription found to reactivate",
        )

    subscription.cancel_at_period_end = False
    await db.flush()

    return {"message": "Subscription reactivated successfully"}


@router.get("/history", response_model=list[PaymentHistoryResponse])
async def get_payment_history(
    limit: int = 20,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's payment history."""
    result = await db.execute(
        select(PaymentHistory)
        .where(PaymentHistory.user_id == UUID(user.id))
        .order_by(PaymentHistory.created_at.desc())
        .limit(limit)
    )
    payments = result.scalars().all()

    return payments


@router.post("/webhook")
async def payment_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle TossPayments webhooks.

    This endpoint receives notifications for:
    - Payment status changes
    - Subscription renewals
    - Failed payments
    """
    body = await request.json()
    event_type = body.get("eventType")

    if event_type == "PAYMENT_STATUS_CHANGED":
        payment_key = body.get("data", {}).get("paymentKey")
        status_val = body.get("data", {}).get("status")

        # Update payment record if exists
        result = await db.execute(
            select(PaymentHistory)
            .where(PaymentHistory.payment_key == payment_key)
        )
        payment = result.scalar_one_or_none()

        if payment:
            payment.status = status_val.lower() if status_val else None

    return {"status": "ok"}


@router.post("/confirm", response_model=dict)
async def confirm_one_time_payment(
    request: PaymentConfirmRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirm a one-time payment (for non-subscription purchases)."""
    async with TossPaymentsClient() as toss:
        try:
            result = await toss.confirm_payment(
                payment_key=request.payment_key,
                order_id=request.order_id,
                amount=request.amount,
            )

            # Record payment
            payment_history = PaymentHistory(
                user_id=UUID(user.id),
                amount=result.amount,
                status="success",
                payment_key=result.payment_key,
                order_id=result.order_id,
                paid_at=datetime.utcnow(),
            )
            db.add(payment_history)

            return {
                "status": "success",
                "payment_key": result.payment_key,
                "amount": result.amount,
                "receipt_url": result.receipt_url,
            }

        except TossPaymentsError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Payment confirmation failed: {e.message}",
            )
