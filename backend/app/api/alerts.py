"""Alerts API endpoints for notification management."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import get_current_user, AuthenticatedUser, require_tier
from app.services.notifications import (
    NotificationService,
    AlertCondition,
    NotificationPayload,
    get_notification_service,
)


router = APIRouter()


# ========== Request/Response Models ==========

class AlertConditionCreate(BaseModel):
    """Request to create an alert condition."""
    dong_code: Optional[str] = None
    min_area: Optional[float] = None
    max_area: Optional[float] = None
    max_price: Optional[int] = None
    min_discount_percent: float = -5.0


class AlertConditionResponse(BaseModel):
    """Alert condition response."""
    index: int
    dong_code: Optional[str]
    min_area: Optional[float]
    max_area: Optional[float]
    max_price: Optional[int]
    min_discount_percent: float
    enabled: bool


class NotificationResponse(BaseModel):
    """Notification response."""
    type: str
    title: str
    message: str
    data: Optional[dict]
    created_at: str


# ========== Endpoints ==========

@router.get("/conditions", response_model=List[AlertConditionResponse])
async def get_alert_conditions(
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Get user's alert conditions.

    Requires Premium tier.
    """
    if user.membership_tier != "premium":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Alert feature requires Premium subscription",
        )

    service = get_notification_service()
    alerts = service.get_user_alerts(user.id)

    return [
        AlertConditionResponse(
            index=i,
            dong_code=alert.dong_code,
            min_area=alert.min_area,
            max_area=alert.max_area,
            max_price=alert.max_price,
            min_discount_percent=alert.min_discount_percent,
            enabled=alert.enabled,
        )
        for i, alert in enumerate(alerts)
    ]


@router.post("/conditions", response_model=AlertConditionResponse)
async def create_alert_condition(
    request: AlertConditionCreate,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Create a new alert condition.

    Requires Premium tier.
    """
    if user.membership_tier != "premium":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Alert feature requires Premium subscription",
        )

    service = get_notification_service()

    # Limit number of alerts per user
    existing = service.get_user_alerts(user.id)
    if len(existing) >= 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 alert conditions allowed",
        )

    condition = AlertCondition(
        user_id=user.id,
        dong_code=request.dong_code,
        min_area=request.min_area,
        max_area=request.max_area,
        max_price=request.max_price,
        min_discount_percent=request.min_discount_percent,
        enabled=True,
    )

    service.register_alert(condition)

    return AlertConditionResponse(
        index=len(existing),
        dong_code=condition.dong_code,
        min_area=condition.min_area,
        max_area=condition.max_area,
        max_price=condition.max_price,
        min_discount_percent=condition.min_discount_percent,
        enabled=condition.enabled,
    )


@router.delete("/conditions/{index}")
async def delete_alert_condition(
    index: int,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Delete an alert condition."""
    if user.membership_tier != "premium":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Alert feature requires Premium subscription",
        )

    service = get_notification_service()
    alerts = service.get_user_alerts(user.id)

    if index < 0 or index >= len(alerts):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert condition not found",
        )

    service.remove_alert(user.id, index)

    return {"message": "Alert condition deleted"}


@router.patch("/conditions/{index}/toggle")
async def toggle_alert_condition(
    index: int,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Toggle an alert condition on/off."""
    if user.membership_tier != "premium":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Alert feature requires Premium subscription",
        )

    service = get_notification_service()
    alerts = service.get_user_alerts(user.id)

    if index < 0 or index >= len(alerts):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert condition not found",
        )

    alerts[index].enabled = not alerts[index].enabled

    return {
        "message": "Alert condition toggled",
        "enabled": alerts[index].enabled,
    }


@router.get("/notifications", response_model=List[NotificationResponse])
async def get_notifications(
    limit: int = 20,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Get user's recent notifications.

    In a real implementation, this would fetch from database.
    """
    # TODO: Fetch from database based on user_id
    # For now, return empty list
    return []


@router.post("/test")
async def send_test_notification(
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Send a test notification to verify setup.

    Requires Premium tier.
    """
    if user.membership_tier != "premium":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Alert feature requires Premium subscription",
        )

    service = get_notification_service()

    notification = NotificationPayload(
        type=service._create_undervalued_notification({
            "id": 0,
            "apartment_id": 0,
            "apartment_name": "테스트 아파트",
            "price": 150000,
            "discount_percent": -8.5,
        }).type,
        title="테스트 알림",
        message="알림 설정이 정상적으로 작동합니다.",
        data={"test": True},
    )

    await service.send_notification(user.id, notification)

    return {
        "message": "Test notification sent",
        "notification": notification.to_dict(),
    }
