'use client'

import { Check } from 'lucide-react'
import Link from 'next/link'

const PLANS = [
  {
    name: 'Free',
    price: '0',
    period: '월',
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
    cta: '무료 시작하기',
    highlighted: false,
  },
  {
    name: 'Basic',
    price: '9,900',
    period: '월',
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
    cta: '시작하기',
    highlighted: true,
  },
  {
    name: 'Premium',
    price: '29,900',
    period: '월',
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
    cta: '시작하기',
    highlighted: false,
  },
]

export function PricingSection() {
  return (
    <section className="py-12" id="pricing">
      <h2 className="text-2xl font-bold text-center mb-2">요금제</h2>
      <p className="text-gray-600 text-center mb-8">
        필요에 맞는 요금제를 선택하세요
      </p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto">
        {PLANS.map((plan, index) => (
          <div
            key={index}
            className={`rounded-xl p-6 ${
              plan.highlighted
                ? 'bg-primary-600 text-white shadow-xl scale-105'
                : 'bg-white border border-gray-200 shadow-sm'
            }`}
          >
            {/* Plan Name */}
            <h3
              className={`text-xl font-bold mb-2 ${
                plan.highlighted ? 'text-white' : 'text-gray-900'
              }`}
            >
              {plan.name}
            </h3>

            {/* Price */}
            <div className="mb-4">
              <span
                className={`text-4xl font-bold ${
                  plan.highlighted ? 'text-white' : 'text-gray-900'
                }`}
              >
                ₩{plan.price}
              </span>
              <span
                className={`text-sm ${
                  plan.highlighted ? 'text-primary-100' : 'text-gray-500'
                }`}
              >
                /{plan.period}
              </span>
            </div>

            {/* Description */}
            <p
              className={`text-sm mb-6 ${
                plan.highlighted ? 'text-primary-100' : 'text-gray-600'
              }`}
            >
              {plan.description}
            </p>

            {/* Features */}
            <ul className="space-y-3 mb-6">
              {plan.features.map((feature, i) => (
                <li key={i} className="flex items-start">
                  <Check
                    className={`w-5 h-5 mr-2 flex-shrink-0 ${
                      plan.highlighted ? 'text-white' : 'text-green-500'
                    }`}
                  />
                  <span
                    className={`text-sm ${
                      plan.highlighted ? 'text-white' : 'text-gray-700'
                    }`}
                  >
                    {feature}
                  </span>
                </li>
              ))}
              {plan.notIncluded.map((feature, i) => (
                <li key={i} className="flex items-start opacity-50">
                  <span className="w-5 h-5 mr-2 flex-shrink-0 text-center">-</span>
                  <span
                    className={`text-sm line-through ${
                      plan.highlighted ? 'text-white' : 'text-gray-500'
                    }`}
                  >
                    {feature}
                  </span>
                </li>
              ))}
            </ul>

            {/* CTA Button */}
            <Link
              href="/signup"
              className={`block w-full text-center py-3 rounded-lg font-semibold transition ${
                plan.highlighted
                  ? 'bg-white text-primary-600 hover:bg-gray-100'
                  : 'bg-primary-600 text-white hover:bg-primary-700'
              }`}
            >
              {plan.cta}
            </Link>
          </div>
        ))}
      </div>
    </section>
  )
}
