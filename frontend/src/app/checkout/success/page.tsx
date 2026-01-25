'use client'

import { useEffect, useState, Suspense } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { Check, Loader2, AlertCircle } from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'
import { api } from '@/lib/api'
import { Button } from '@/components/ui'

function CheckoutSuccessContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const { isAuthenticated, refreshSession } = useAuth()
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const paymentKey = searchParams.get('paymentKey')
  const orderId = searchParams.get('orderId')
  const amount = searchParams.get('amount')
  const plan = searchParams.get('plan')

  useEffect(() => {
    const confirmPayment = async () => {
      if (!paymentKey || !orderId || !amount) {
        setStatus('error')
        setErrorMessage('결제 정보가 올바르지 않습니다.')
        return
      }

      try {
        // Confirm payment with backend
        await api.confirmPayment({
          paymentKey,
          orderId,
          amount: parseInt(amount, 10),
        })

        // Refresh session to get updated membership tier
        await refreshSession()

        setStatus('success')

        // Redirect to mypage after 3 seconds
        setTimeout(() => {
          router.push('/mypage?tab=billing')
        }, 3000)
      } catch (err) {
        setStatus('error')
        setErrorMessage(
          err instanceof Error ? err.message : '결제 확인 중 오류가 발생했습니다.'
        )
      }
    }

    if (isAuthenticated) {
      confirmPayment()
    }
  }, [paymentKey, orderId, amount, isAuthenticated, refreshSession, router])

  if (status === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-primary-600 mx-auto mb-4" />
          <h1 className="text-xl font-semibold text-gray-900">결제 확인 중...</h1>
          <p className="text-gray-500 mt-2">잠시만 기다려주세요.</p>
        </div>
      </div>
    )
  }

  if (status === 'error') {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="max-w-md mx-auto text-center px-4">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-6">
            <AlertCircle className="w-8 h-8 text-red-600" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-4">결제 확인 실패</h1>
          <p className="text-gray-600 mb-6">{errorMessage}</p>
          <div className="space-y-3">
            <Link href="/pricing">
              <Button className="w-full">요금제 다시 선택하기</Button>
            </Link>
            <Link href="/">
              <Button variant="outline" className="w-full">홈으로 돌아가기</Button>
            </Link>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="max-w-md mx-auto text-center px-4">
        <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6 animate-scale-in">
          <Check className="w-8 h-8 text-green-600" />
        </div>
        <h1 className="text-2xl font-bold text-gray-900 mb-4">구독이 완료되었습니다!</h1>
        <p className="text-gray-600 mb-2">
          {plan === 'premium' ? 'Premium' : 'Basic'} 요금제 구독이 시작되었습니다.
        </p>
        <p className="text-gray-500 text-sm mb-6">
          잠시 후 마이페이지로 이동합니다.
        </p>
        <Loader2 className="w-6 h-6 animate-spin mx-auto text-primary-600 mb-6" />
        <Link href="/mypage?tab=billing">
          <Button variant="outline">마이페이지로 바로 가기</Button>
        </Link>
      </div>
    </div>
  )
}

export default function CheckoutSuccessPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center">
          <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
        </div>
      }
    >
      <CheckoutSuccessContent />
    </Suspense>
  )
}
