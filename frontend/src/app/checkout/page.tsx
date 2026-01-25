'use client'

import { Suspense, useState, useEffect, useCallback } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { CreditCard, Shield, ArrowLeft, Loader2, Check, AlertCircle } from 'lucide-react'
import Link from 'next/link'
import Script from 'next/script'
import { useAuth } from '@/contexts/AuthContext'
import { useToast } from '@/components/ui'
import { api } from '@/lib/api'

const PLANS: Record<string, { name: string; price: number; features: string[] }> = {
  basic: {
    name: 'Basic',
    price: 9900,
    features: [
      '일 100회 매물 검색',
      '유사 매물 비교 분석',
      '저평가 리포트 (일 5건)',
      '가격 추이 차트',
      '관심 매물 50개 저장',
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
      '중개사 정보 조회',
      '무제한 관심 매물/지역',
    ],
  },
}

// TossPayments client key from environment
const TOSS_CLIENT_KEY = process.env.NEXT_PUBLIC_TOSS_CLIENT_KEY || ''
const IS_DEV_MODE = !TOSS_CLIENT_KEY

// TossPayments SDK type declarations
declare global {
  interface Window {
    TossPayments?: (clientKey: string) => {
      requestBillingAuth: (method: string, options: {
        customerKey: string
        successUrl: string
        failUrl: string
      }) => Promise<void>
      widgets: (options: { customerKey: string }) => {
        setAmount: (options: { currency: string; value: number }) => Promise<void>
        renderPaymentMethods: (options: { selector: string; variantKey?: string }) => Promise<void>
        renderAgreement: (options: { selector: string; variantKey?: string }) => Promise<void>
        requestPayment: (options: {
          orderId: string
          orderName: string
          successUrl: string
          failUrl: string
          customerEmail?: string
          customerName?: string
        }) => Promise<void>
      }
    }
  }
}

function CheckoutContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const { isAuthenticated, isLoading: authLoading, user, profile } = useAuth()
  const { success, error: showError } = useToast()
  const planId = searchParams.get('plan') || 'basic'

  const [isLoading, setIsLoading] = useState(false)
  const [isComplete, setIsComplete] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [agreeTerms, setAgreeTerms] = useState(true)
  const [sdkLoaded, setSdkLoaded] = useState(false)
  const [widgetsReady, setWidgetsReady] = useState(false)
  const [paymentWidget, setPaymentWidget] = useState<ReturnType<ReturnType<NonNullable<Window['TossPayments']>>['widgets']> | null>(null)

  const plan = PLANS[planId]

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push(`/login?redirect=/checkout?plan=${planId}`)
    }
  }, [authLoading, isAuthenticated, router, planId])

  // Initialize TossPayments SDK
  const initializeTossPayments = useCallback(async () => {
    if (!window.TossPayments || !user || IS_DEV_MODE) return

    try {
      const tossPayments = window.TossPayments(TOSS_CLIENT_KEY)
      const customerKey = user.id

      const widgets = tossPayments.widgets({ customerKey })

      // Set amount
      await widgets.setAmount({
        currency: 'KRW',
        value: plan.price,
      })

      // Render payment methods widget
      await widgets.renderPaymentMethods({
        selector: '#payment-method',
        variantKey: 'DEFAULT',
      })

      // Render agreement widget
      await widgets.renderAgreement({
        selector: '#agreement',
        variantKey: 'AGREEMENT',
      })

      setPaymentWidget(widgets)
      setWidgetsReady(true)
    } catch (err) {
      console.error('Failed to initialize TossPayments:', err)
      setError('결제 모듈 초기화에 실패했습니다.')
    }
  }, [user, plan?.price])

  useEffect(() => {
    if (sdkLoaded && user && plan && !IS_DEV_MODE) {
      initializeTossPayments()
    }
  }, [sdkLoaded, user, plan, initializeTossPayments])

  if (!plan) {
    return (
      <div className="container mx-auto px-4 py-12 text-center">
        <h1 className="text-2xl font-bold text-red-600">잘못된 요금제입니다</h1>
        <Link href="/pricing" className="text-primary-600 hover:underline mt-4 inline-block">
          요금제 페이지로 돌아가기
        </Link>
      </div>
    )
  }

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
      </div>
    )
  }

  const handlePayment = async () => {
    if (!agreeTerms) {
      setError('이용약관에 동의해주세요.')
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      // Development mode: simulate successful payment
      if (IS_DEV_MODE) {
        await new Promise((resolve) => setTimeout(resolve, 2000))
        setIsComplete(true)
        success('구독이 완료되었습니다!')
        setTimeout(() => {
          router.push('/mypage?tab=billing')
        }, 2000)
        return
      }

      // Production mode: Use TossPayments Widget
      if (!paymentWidget || !user) {
        throw new Error('결제 모듈이 준비되지 않았습니다.')
      }

      const orderId = `CHATAPT-${planId.toUpperCase()}-${Date.now()}`

      await paymentWidget.requestPayment({
        orderId,
        orderName: `Chat APT ${plan.name} 구독`,
        successUrl: `${window.location.origin}/checkout/success?plan=${planId}`,
        failUrl: `${window.location.origin}/checkout/fail`,
        customerEmail: user.email || undefined,
        customerName: profile?.name || undefined,
      })
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '결제 처리 중 오류가 발생했습니다.'
      setError(errorMessage)
      showError('결제 실패', errorMessage)
    } finally {
      setIsLoading(false)
    }
  }

  if (isComplete) {
    return (
      <div className="container mx-auto px-4 py-12">
        <div className="max-w-md mx-auto text-center">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6 animate-scale-in">
            <Check className="w-8 h-8 text-green-600" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-4">구독이 완료되었습니다!</h1>
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
    <>
      {/* TossPayments SDK - Load only in production mode */}
      {!IS_DEV_MODE && (
        <Script
          src="https://js.tosspayments.com/v2/standard"
          strategy="afterInteractive"
          onLoad={() => setSdkLoaded(true)}
        />
      )}

      <div className="container mx-auto px-4 py-12">
        <div className="max-w-4xl mx-auto">
          <Link href="/pricing" className="inline-flex items-center text-gray-600 hover:text-primary-600 mb-8">
            <ArrowLeft className="w-4 h-4 mr-2" />
            요금제 선택으로 돌아가기
          </Link>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <div className="bg-white rounded-xl shadow-lg p-6 h-fit">
              <h2 className="text-xl font-bold mb-6">주문 요약</h2>

              {user && (
                <div className="bg-gray-50 rounded-lg p-4 mb-6">
                  <p className="text-sm text-gray-500">구독자</p>
                  <p className="font-medium">{profile?.name || user.email}</p>
                  <p className="text-sm text-gray-500">{user.email}</p>
                </div>
              )}

              <div className="border-b pb-4 mb-4">
                <div className="flex justify-between items-center mb-2">
                  <span className="font-semibold">{plan.name} 요금제</span>
                  <span className="text-lg font-bold">₩{plan.price.toLocaleString()}/월</span>
                </div>
                <p className="text-sm text-gray-500">매월 자동 결제됩니다</p>
              </div>

              <div className="mb-6">
                <h3 className="font-medium mb-3">포함된 기능</h3>
                <ul className="space-y-2">
                  {plan.features.map((feature, i) => (
                    <li key={i} className="flex items-center text-sm text-gray-600">
                      <Check className="w-4 h-4 mr-2 text-green-500 flex-shrink-0" />
                      {feature}
                    </li>
                  ))}
                </ul>
              </div>

              <div className="border-t pt-4">
                <div className="flex justify-between items-center text-lg font-bold">
                  <span>오늘 결제 금액</span>
                  <span className="text-primary-600">₩{plan.price.toLocaleString()}</span>
                </div>
                <p className="text-xs text-gray-500 mt-2">* 부가세 포함 금액입니다</p>
              </div>
            </div>

            <div className="bg-white rounded-xl shadow-lg p-6">
              <h2 className="text-xl font-bold mb-6">결제 정보</h2>

              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-lg mb-6 flex items-start">
                  <AlertCircle className="w-5 h-5 mr-2 flex-shrink-0 mt-0.5" />
                  <span>{error}</span>
                </div>
              )}

              {IS_DEV_MODE && (
                <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 p-4 rounded-lg mb-6">
                  <p className="text-sm font-medium">개발 모드</p>
                  <p className="text-xs mt-1">현재 데모 환경입니다. 실제 결제는 진행되지 않습니다.</p>
                </div>
              )}

            {/* TossPayments Widget */}
            {IS_DEV_MODE ? (
              <div className="border-2 border-dashed border-gray-200 rounded-lg p-8 mb-6 text-center">
                <CreditCard className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-500 mb-2">TossPayments 카드 등록 영역</p>
                <p className="text-xs text-gray-400">실제 구현시 TossPayments SDK가 로드됩니다</p>
              </div>
            ) : (
              <div className="mb-6 space-y-4">
                {/* Payment method widget container */}
                <div id="payment-method" className="min-h-[200px]">
                  {!widgetsReady && (
                    <div className="flex items-center justify-center h-[200px] border border-gray-200 rounded-lg">
                      <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
                    </div>
                  )}
                </div>
                {/* Agreement widget container */}
                <div id="agreement" />
              </div>
            )}

            <div className="flex items-start bg-gray-50 rounded-lg p-4 mb-6">
              <Shield className="w-5 h-5 text-green-600 mr-3 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-gray-900">안전한 결제</p>
                <p className="text-xs text-gray-500">
                  결제 정보는 TossPayments를 통해 암호화되어 안전하게 처리됩니다. 카드 정보는 저희 서버에 저장되지 않습니다.
                </p>
              </div>
            </div>

            <div className="mb-6">
              <label className="flex items-start cursor-pointer">
                <input
                  type="checkbox"
                  checked={agreeTerms}
                  onChange={(e) => setAgreeTerms(e.target.checked)}
                  className="mt-1 mr-3 w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                />
                <span className="text-sm text-gray-600">
                  <Link href="/terms" className="text-primary-600 hover:underline">이용약관</Link>
                  {' 및 '}
                  <Link href="/privacy" className="text-primary-600 hover:underline">개인정보처리방침</Link>
                  에 동의합니다. 정기 결제에 동의하며, 언제든지 구독을 취소할 수 있습니다.
                </span>
              </label>
            </div>

            <button
              onClick={handlePayment}
              disabled={isLoading || !agreeTerms}
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
    </>
  )
}

export default function CheckoutPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center">
          <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
        </div>
      }
    >
      <CheckoutContent />
    </Suspense>
  )
}
