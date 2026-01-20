'use client'

import { useState, useEffect } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { CreditCard, Shield, ArrowLeft, Loader2, Check } from 'lucide-react'
import Link from 'next/link'

const PLANS: Record<string, { name: string; price: number; features: string[] }> = {
  basic: {
    name: 'Basic',
    price: 9900,
    features: [
      '일 100회 매물 검색',
      '유사 매물 비교 분석',
      '저평가 리포트 (일 5건)',
    ],
  },
  premium: {
    name: 'Premium',
    price: 29900,
    features: [
      '무제한 매물 검색',
      '무제한 유사 매물 분석',
      '무제한 저평가 리포트',
      '실시간 급매 알림',
    ],
  },
}

export default function CheckoutPage() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const planId = searchParams.get('plan') || 'basic'

  const [isLoading, setIsLoading] = useState(false)
  const [isComplete, setIsComplete] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const plan = PLANS[planId]

  if (!plan) {
    return (
      <div className="container mx-auto px-4 py-12 text-center">
        <h1 className="text-2xl font-bold text-red-600">
          잘못된 요금제입니다
        </h1>
        <Link href="/pricing" className="text-primary-600 hover:underline mt-4 inline-block">
          요금제 페이지로 돌아가기
        </Link>
      </div>
    )
  }

  const handlePayment = async () => {
    setIsLoading(true)
    setError(null)

    try {
      // In a real implementation, this would:
      // 1. Load TossPayments SDK
      // 2. Open card registration modal
      // 3. Get auth_key from card registration
      // 4. Call backend API to create subscription

      // Simulate payment process
      await new Promise((resolve) => setTimeout(resolve, 2000))

      // For demo, show success
      setIsComplete(true)

      // Redirect after success
      setTimeout(() => {
        router.push('/mypage?subscription=success')
      }, 2000)

    } catch (err) {
      setError('결제 처리 중 오류가 발생했습니다. 다시 시도해주세요.')
    } finally {
      setIsLoading(false)
    }
  }

  if (isComplete) {
    return (
      <div className="container mx-auto px-4 py-12">
        <div className="max-w-md mx-auto text-center">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
            <Check className="w-8 h-8 text-green-600" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-4">
            구독이 완료되었습니다!
          </h1>
          <p className="text-gray-600 mb-6">
            {plan.name} 요금제 구독이 시작되었습니다.
            <br />
            잠시 후 마이페이지로 이동합니다.
          </p>
          <Loader2 className="w-6 h-6 animate-spin mx-auto text-primary-600" />
        </div>
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-12">
      <div className="max-w-4xl mx-auto">
        {/* Back Button */}
        <Link
          href="/pricing"
          className="inline-flex items-center text-gray-600 hover:text-primary-600 mb-8"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          요금제 선택으로 돌아가기
        </Link>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Order Summary */}
          <div className="bg-white rounded-xl shadow-lg p-6 h-fit">
            <h2 className="text-xl font-bold mb-6">주문 요약</h2>

            <div className="border-b pb-4 mb-4">
              <div className="flex justify-between items-center mb-2">
                <span className="font-semibold">{plan.name} 요금제</span>
                <span className="text-lg font-bold">
                  ₩{plan.price.toLocaleString()}/월
                </span>
              </div>
              <p className="text-sm text-gray-500">매월 자동 결제됩니다</p>
            </div>

            <div className="mb-6">
              <h3 className="font-medium mb-3">포함된 기능</h3>
              <ul className="space-y-2">
                {plan.features.map((feature, i) => (
                  <li key={i} className="flex items-center text-sm text-gray-600">
                    <Check className="w-4 h-4 mr-2 text-green-500" />
                    {feature}
                  </li>
                ))}
              </ul>
            </div>

            <div className="border-t pt-4">
              <div className="flex justify-between items-center text-lg font-bold">
                <span>오늘 결제 금액</span>
                <span className="text-primary-600">
                  ₩{plan.price.toLocaleString()}
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-2">
                * 부가세 포함 금액입니다
              </p>
            </div>
          </div>

          {/* Payment Form */}
          <div className="bg-white rounded-xl shadow-lg p-6">
            <h2 className="text-xl font-bold mb-6">결제 정보</h2>

            {error && (
              <div className="bg-red-50 text-red-600 p-4 rounded-lg mb-6">
                {error}
              </div>
            )}

            {/* Card Input Placeholder */}
            <div className="border-2 border-dashed border-gray-200 rounded-lg p-8 mb-6 text-center">
              <CreditCard className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-500 mb-2">
                TossPayments 카드 등록 영역
              </p>
              <p className="text-xs text-gray-400">
                실제 구현시 TossPayments SDK가 로드됩니다
              </p>
            </div>

            {/* Security Notice */}
            <div className="flex items-start bg-gray-50 rounded-lg p-4 mb-6">
              <Shield className="w-5 h-5 text-green-600 mr-3 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-gray-900">
                  안전한 결제
                </p>
                <p className="text-xs text-gray-500">
                  결제 정보는 TossPayments를 통해 암호화되어 안전하게 처리됩니다.
                  카드 정보는 저희 서버에 저장되지 않습니다.
                </p>
              </div>
            </div>

            {/* Terms */}
            <div className="mb-6">
              <label className="flex items-start">
                <input
                  type="checkbox"
                  className="mt-1 mr-3"
                  defaultChecked
                />
                <span className="text-sm text-gray-600">
                  <Link href="/terms" className="text-primary-600 hover:underline">
                    이용약관
                  </Link>
                  {' 및 '}
                  <Link href="/privacy" className="text-primary-600 hover:underline">
                    개인정보처리방침
                  </Link>
                  에 동의합니다.
                  정기 결제에 동의하며, 언제든지 구독을 취소할 수 있습니다.
                </span>
              </label>
            </div>

            {/* Submit Button */}
            <button
              onClick={handlePayment}
              disabled={isLoading}
              className="w-full bg-primary-600 text-white py-4 rounded-lg font-semibold hover:bg-primary-700 transition disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center justify-center"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin mr-2" />
                  처리 중...
                </>
              ) : (
                <>₩{plan.price.toLocaleString()} 결제하기</>
              )}
            </button>

            <p className="text-xs text-center text-gray-500 mt-4">
              구독은 매월 자동으로 갱신되며, 언제든지 취소할 수 있습니다.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
