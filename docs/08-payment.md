# 8. 비즈니스 모델 및 결제 시스템

## 8.1 수익 모델

```
┌─────────────────────────────────────────────────────────────────┐
│                        수익 구조                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────────────┐   │
│  │   광고 수익  │   │  구독 수익   │   │  제휴/API 수익      │   │
│  │  (Free 티어) │   │ (Basic/Pro) │   │  (B2B)             │   │
│  └──────┬──────┘   └──────┬──────┘   └──────────┬──────────┘   │
│         │                 │                      │              │
│         ▼                 ▼                      ▼              │
│     Google Ads      토스페이먼츠            부동산 중개업소      │
│     카카오 Ads      정기 결제              프롭테크 스타트업     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8.2 가격 정책

| 플랜 | 월간 | 연간 (17% 할인) | 대상 |
|------|------|-----------------|------|
| Free | ₩0 | - | 일반 사용자 |
| Basic | ₩9,900 | ₩99,000 | 개인 투자자 |
| Premium | ₩19,900 | ₩199,000 | 전문 투자자 |
| Enterprise | 별도 협의 | - | 부동산 업체, B2B |

### 플랜별 기능 비교

| 기능 | Free | Basic | Premium |
|------|------|-------|---------|
| 실거래가 조회 | ✅ 무제한 | ✅ 무제한 | ✅ 무제한 |
| 매물 호가 조회 | 10건/일 | 100건/일 | 무제한 |
| 유사 매물 분석 | ❌ | 10건/일 | 무제한 |
| 저평가 리포트 | ❌ | 5건/일 | 무제한 |
| 가격 알림 | ❌ | 3개 지역 | 10개 지역 |
| 관심 매물 | 5개 | 50개 | 무제한 |
| API 접근 | ❌ | ❌ | ✅ |
| 광고 | 있음 | 없음 | 없음 |

---

## 8.3 결제 시스템 연동

### 토스페이먼츠 정기결제

```typescript
// types/payment.ts
interface SubscriptionPayment {
  orderId: string;
  orderName: string;
  customerKey: string;
  amount: number;
}

// 빌링키 발급 (카드 등록)
async function issueBillingKey(customerKey: string) {
  const response = await fetch('/api/payments/billing-key', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      customerKey,
      successUrl: `${window.location.origin}/payments/success`,
      failUrl: `${window.location.origin}/payments/fail`,
    }),
  });
  return response.json();
}

// 정기 결제 실행
async function executeSubscription(
  billingKey: string,
  customerKey: string,
  amount: number,
  orderName: string
) {
  const response = await fetch(
    `https://api.tosspayments.com/v1/billing/${billingKey}`,
    {
      method: 'POST',
      headers: {
        Authorization: `Basic ${btoa(TOSS_SECRET_KEY + ':')}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        customerKey,
        amount,
        orderId: generateOrderId(),
        orderName,
      }),
    }
  );
  return response.json();
}
```

### 결제 API 엔드포인트

```python
# app/api/payments.py
from fastapi import APIRouter, HTTPException
import httpx

router = APIRouter(prefix="/api/payments")

TOSS_API_URL = "https://api.tosspayments.com/v1"

@router.post("/billing-key")
async def request_billing_key(data: BillingKeyRequest):
    """빌링키 발급 요청"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{TOSS_API_URL}/billing/authorizations/card",
            headers={
                "Authorization": f"Basic {get_toss_auth()}",
                "Content-Type": "application/json",
            },
            json={
                "customerKey": data.customer_key,
                "successUrl": data.success_url,
                "failUrl": data.fail_url,
            }
        )
    return response.json()


@router.post("/subscribe")
async def create_subscription(data: SubscribeRequest, user: User = Depends(get_current_user)):
    """구독 생성"""
    # 1. 결제 실행
    payment_result = await execute_payment(
        billing_key=data.billing_key,
        customer_key=user.id,
        amount=get_plan_price(data.plan),
        order_name=f"{data.plan} 구독"
    )

    if payment_result.get("code"):  # 에러
        raise HTTPException(status_code=400, detail=payment_result["message"])

    # 2. 구독 정보 저장
    subscription = await create_subscription_record(
        user_id=user.id,
        plan=data.plan,
        billing_key=data.billing_key,
        payment_key=payment_result["paymentKey"]
    )

    # 3. 사용자 등급 업데이트
    await update_user_tier(user.id, data.plan)

    return {"subscription_id": subscription.id}


@router.post("/webhook")
async def payment_webhook(request: Request):
    """토스페이먼츠 웹훅 처리"""
    body = await request.json()
    event_type = body.get("eventType")

    if event_type == "BILLING_KEY_DELETED":
        # 빌링키 삭제됨 - 구독 취소 처리
        await cancel_subscription_by_billing_key(body["billingKey"])

    elif event_type == "PAYMENT_DONE":
        # 결제 완료 - 구독 갱신
        await renew_subscription(body["paymentKey"])

    return {"status": "ok"}
```

---

## 8.4 구독 관리

### 자동 갱신 처리

```python
# workers/subscription_tasks.py
from celery import Celery

app = Celery('tasks')

@app.task
def process_subscription_renewals():
    """매일 실행: 만료 예정 구독 자동 갱신"""
    expiring_subscriptions = get_expiring_subscriptions(days=1)

    for subscription in expiring_subscriptions:
        if subscription.cancel_at_period_end:
            # 취소 예정 - 등급 다운그레이드
            downgrade_user_tier(subscription.user_id)
            expire_subscription(subscription.id)
        else:
            # 자동 갱신
            try:
                result = execute_payment(
                    billing_key=subscription.billing_key,
                    customer_key=subscription.user_id,
                    amount=get_plan_price(subscription.plan),
                    order_name=f"{subscription.plan} 구독 갱신"
                )

                if result.get("paymentKey"):
                    renew_subscription(subscription.id)
                    save_payment_history(subscription, result)
                else:
                    # 결제 실패
                    handle_payment_failure(subscription)

            except Exception as e:
                handle_payment_failure(subscription, str(e))


@app.task
def send_expiration_reminders():
    """만료 3일 전 알림 발송"""
    expiring_soon = get_expiring_subscriptions(days=3)

    for subscription in expiring_soon:
        send_email(
            to=subscription.user.email,
            template="subscription_expiring",
            data={
                "plan": subscription.plan,
                "expires_at": subscription.current_period_end,
            }
        )
```

### 구독 취소 처리

```python
@router.post("/cancel")
async def cancel_subscription(user: User = Depends(get_current_user)):
    """구독 취소 (기간 종료 후 해지)"""
    subscription = await get_user_subscription(user.id)

    if not subscription:
        raise HTTPException(status_code=404, detail="구독 정보가 없습니다.")

    # 즉시 해지가 아닌, 기간 종료 후 해지
    await update_subscription(
        subscription.id,
        cancel_at_period_end=True
    )

    return {
        "message": "구독이 취소되었습니다.",
        "expires_at": subscription.current_period_end
    }


@router.post("/refund")
async def refund_subscription(user: User = Depends(get_current_user)):
    """구독 환불 (즉시 해지)"""
    subscription = await get_user_subscription(user.id)
    latest_payment = await get_latest_payment(subscription.id)

    # 결제일로부터 7일 이내만 환불 가능
    if (datetime.now() - latest_payment.paid_at).days > 7:
        raise HTTPException(
            status_code=400,
            detail="결제일로부터 7일 이내에만 환불 가능합니다."
        )

    # 토스페이먼츠 환불 요청
    refund_result = await request_refund(
        payment_key=latest_payment.payment_key,
        cancel_reason="사용자 요청"
    )

    if refund_result.get("cancels"):
        # 즉시 등급 다운그레이드
        await downgrade_user_tier(user.id)
        await expire_subscription(subscription.id)

        return {"message": "환불이 완료되었습니다."}

    raise HTTPException(status_code=400, detail="환불 처리에 실패했습니다.")
```

---

## 8.5 결제 UI 컴포넌트

### 요금제 선택 페이지

```typescript
// app/pricing/page.tsx
'use client';

import { useState } from 'react';
import { useAuth } from '@/providers/AuthProvider';

const plans = [
  {
    id: 'basic',
    name: 'Basic',
    price: 9900,
    yearlyPrice: 99000,
    features: ['매물 100건/일', '유사 매물 분석', '알림 3개 지역'],
  },
  {
    id: 'premium',
    name: 'Premium',
    price: 19900,
    yearlyPrice: 199000,
    features: ['무제한 조회', '무제한 분석', 'API 접근', '광고 제거'],
    popular: true,
  },
];

export default function PricingPage() {
  const { user } = useAuth();
  const [isYearly, setIsYearly] = useState(false);

  const handleSubscribe = async (planId: string) => {
    if (!user) {
      // 로그인 페이지로 리다이렉트
      window.location.href = '/login?redirect=/pricing';
      return;
    }

    // 결제 페이지로 이동
    window.location.href = `/checkout?plan=${planId}&billing=${isYearly ? 'yearly' : 'monthly'}`;
  };

  return (
    <div className="max-w-4xl mx-auto py-12 px-4">
      <h1 className="text-3xl font-bold text-center mb-8">요금제</h1>

      {/* 월간/연간 토글 */}
      <div className="flex justify-center mb-8">
        <button
          className={`px-4 py-2 ${!isYearly ? 'bg-blue-600 text-white' : 'bg-gray-200'}`}
          onClick={() => setIsYearly(false)}
        >
          월간
        </button>
        <button
          className={`px-4 py-2 ${isYearly ? 'bg-blue-600 text-white' : 'bg-gray-200'}`}
          onClick={() => setIsYearly(true)}
        >
          연간 (17% 할인)
        </button>
      </div>

      {/* 요금제 카드 */}
      <div className="grid md:grid-cols-2 gap-6">
        {plans.map((plan) => (
          <div
            key={plan.id}
            className={`border rounded-lg p-6 ${plan.popular ? 'border-blue-600 ring-2 ring-blue-600' : ''}`}
          >
            {plan.popular && (
              <span className="bg-blue-600 text-white text-xs px-2 py-1 rounded">
                인기
              </span>
            )}
            <h2 className="text-xl font-bold mt-2">{plan.name}</h2>
            <p className="text-3xl font-bold mt-4">
              ₩{(isYearly ? plan.yearlyPrice : plan.price).toLocaleString()}
              <span className="text-sm text-gray-500">
                /{isYearly ? '년' : '월'}
              </span>
            </p>

            <ul className="mt-6 space-y-2">
              {plan.features.map((feature) => (
                <li key={feature} className="flex items-center gap-2">
                  <CheckIcon className="text-green-500" />
                  {feature}
                </li>
              ))}
            </ul>

            <button
              onClick={() => handleSubscribe(plan.id)}
              className="w-full mt-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              시작하기
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
```

### 결제 페이지

```typescript
// app/checkout/page.tsx
'use client';

import { useEffect, useRef } from 'react';
import { loadTossPayments } from '@tosspayments/payment-sdk';

export default function CheckoutPage() {
  const { plan, billing } = useSearchParams();
  const { user } = useAuth();
  const paymentWidgetRef = useRef(null);

  useEffect(() => {
    async function initPayment() {
      const tossPayments = await loadTossPayments(TOSS_CLIENT_KEY);
      const widgets = tossPayments.widgets({ customerKey: user.id });

      await widgets.setAmount({
        value: getPlanPrice(plan, billing),
        currency: 'KRW',
      });

      await widgets.renderPaymentMethods({
        selector: '#payment-methods',
        variantKey: 'DEFAULT',
      });

      await widgets.renderAgreement({
        selector: '#agreement',
        variantKey: 'AGREEMENT',
      });

      paymentWidgetRef.current = widgets;
    }

    if (user) {
      initPayment();
    }
  }, [user, plan, billing]);

  const handlePayment = async () => {
    try {
      await paymentWidgetRef.current.requestPayment({
        orderId: generateOrderId(),
        orderName: `${plan} 구독`,
        successUrl: `${window.location.origin}/checkout/success`,
        failUrl: `${window.location.origin}/checkout/fail`,
      });
    } catch (error) {
      console.error('결제 실패:', error);
    }
  };

  return (
    <div className="max-w-lg mx-auto py-12 px-4">
      <h1 className="text-2xl font-bold mb-8">결제</h1>

      <div id="payment-methods" />
      <div id="agreement" className="mt-4" />

      <button
        onClick={handlePayment}
        className="w-full mt-6 py-3 bg-blue-600 text-white rounded-lg"
      >
        결제하기
      </button>
    </div>
  );
}
```
