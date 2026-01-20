'use client'

import { useState } from 'react'
import { Check, Loader2 } from 'lucide-react'
import { useRouter } from 'next/navigation'

const PLANS = [
  {
    id: 'free',
    name: 'Free',
    price: 0,
    description: '기본 기능을 무료로 체험하세요',
    features: [
      '일 10회 매물 검색',
      '기본 시세 정보',
      '실거래가 조회',
    ],
    notIncluded: [
      '유사 매물 분석',
      '저평가 리포트',
      '급매 알림',
    ],
    cta: '현재 요금제',
    highlighted: false,
    disabled: true,
  },
  {
    id: 'basic',
    name: 'Basic',
    price: 9900,
    description: '개인 투자자를 위한 필수 기능',
    features: [
      '일 100회 매물 검색',
      '유사 매물 비교 분석',
      '저평가 리포트 (일 5건)',
      '가격 추이 차트',
    ],
    notIncluded: [
      '무제한 검색',
      '급매 알림',
    ],
    cta: '구독하기',
    highlighted: true,
    disabled: false,
  },
  {
    id: 'premium',
    name: 'Premium',
    price: 29900,
    description: '전문 투자자를 위한 올인원 패키지',
    features: [
      '무제한 매물 검색',
      '무제한 유사 매물 분석',
      '무제한 저평가 리포트',
      '실시간 급매 알림',
      '우선 고객 지원',
      'API 액세스',
    ],
    notIncluded: [],
    cta: '구독하기',
    highlighted: false,
    disabled: false,
  },
]

export default function PricingPage() {
  const router = useRouter()
  const [loading, setLoading] = useState<string | null>(null)

  const handleSubscribe = async (planId: string) => {
    if (planId === 'free') return

    setLoading(planId)

    // In a real app, check if user is logged in first
    // For now, redirect to checkout page
    router.push(`/checkout?plan=${planId}`)
  }

  return (
    <div className="container mx-auto px-4 py-12">
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">요금제</h1>
        <p className="text-xl text-gray-600">
          필요에 맞는 요금제를 선택하세요
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-5xl mx-auto">
        {PLANS.map((plan) => (
          <div
            key={plan.id}
            className={`rounded-2xl p-8 ${
              plan.highlighted
                ? 'bg-primary-600 text-white shadow-2xl scale-105 relative'
                : 'bg-white border border-gray-200 shadow-lg'
            }`}
          >
            {plan.highlighted && (
              <div className="absolute -top-4 left-1/2 transform -translate-x-1/2">
                <span className="bg-yellow-400 text-yellow-900 text-sm font-bold px-4 py-1 rounded-full">
                  추천
                </span>
              </div>
            )}

            <h2
              className={`text-2xl font-bold mb-2 ${
                plan.highlighted ? 'text-white' : 'text-gray-900'
              }`}
            >
              {plan.name}
            </h2>

            <div className="mb-4">
              <span
                className={`text-5xl font-bold ${
                  plan.highlighted ? 'text-white' : 'text-gray-900'
                }`}
              >
                ₩{plan.price.toLocaleString()}
              </span>
              <span
                className={`text-lg ${
                  plan.highlighted ? 'text-primary-100' : 'text-gray-500'
                }`}
              >
                /월
              </span>
            </div>

            <p
              className={`mb-6 ${
                plan.highlighted ? 'text-primary-100' : 'text-gray-600'
              }`}
            >
              {plan.description}
            </p>

            <ul className="space-y-3 mb-8">
              {plan.features.map((feature, i) => (
                <li key={i} className="flex items-start">
                  <Check
                    className={`w-5 h-5 mr-3 flex-shrink-0 ${
                      plan.highlighted ? 'text-white' : 'text-green-500'
                    }`}
                  />
                  <span
                    className={
                      plan.highlighted ? 'text-white' : 'text-gray-700'
                    }
                  >
                    {feature}
                  </span>
                </li>
              ))}
              {plan.notIncluded.map((feature, i) => (
                <li key={i} className="flex items-start opacity-50">
                  <span className="w-5 h-5 mr-3 flex-shrink-0 text-center">
                    -
                  </span>
                  <span
                    className={`line-through ${
                      plan.highlighted ? 'text-white' : 'text-gray-500'
                    }`}
                  >
                    {feature}
                  </span>
                </li>
              ))}
            </ul>

            <button
              onClick={() => handleSubscribe(plan.id)}
              disabled={plan.disabled || loading === plan.id}
              className={`w-full py-3 rounded-lg font-semibold transition flex items-center justify-center ${
                plan.highlighted
                  ? 'bg-white text-primary-600 hover:bg-gray-100 disabled:bg-gray-200'
                  : plan.disabled
                  ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                  : 'bg-primary-600 text-white hover:bg-primary-700'
              }`}
            >
              {loading === plan.id ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                plan.cta
              )}
            </button>
          </div>
        ))}
      </div>

      {/* FAQ Section */}
      <div className="mt-16 max-w-3xl mx-auto">
        <h2 className="text-2xl font-bold text-center mb-8">자주 묻는 질문</h2>

        <div className="space-y-4">
          <div className="bg-white rounded-lg p-6 shadow-sm border">
            <h3 className="font-semibold mb-2">
              언제든지 구독을 취소할 수 있나요?
            </h3>
            <p className="text-gray-600">
              네, 언제든지 취소할 수 있습니다. 취소하시면 현재 결제 기간이 끝날
              때까지 서비스를 이용하실 수 있습니다.
            </p>
          </div>

          <div className="bg-white rounded-lg p-6 shadow-sm border">
            <h3 className="font-semibold mb-2">결제 수단은 무엇이 있나요?</h3>
            <p className="text-gray-600">
              신용카드, 체크카드로 결제하실 수 있습니다. TossPayments를 통해
              안전하게 결제됩니다.
            </p>
          </div>

          <div className="bg-white rounded-lg p-6 shadow-sm border">
            <h3 className="font-semibold mb-2">
              요금제를 변경할 수 있나요?
            </h3>
            <p className="text-gray-600">
              네, 언제든지 상위 요금제로 업그레이드하거나 하위 요금제로 변경할
              수 있습니다. 변경은 다음 결제일부터 적용됩니다.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
