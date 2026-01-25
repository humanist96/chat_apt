'use client'

import { Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { XCircle, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui'

function CheckoutFailContent() {
  const searchParams = useSearchParams()

  const errorCode = searchParams.get('code')
  const errorMessage = searchParams.get('message')

  const getErrorDescription = (code: string | null) => {
    switch (code) {
      case 'PAY_PROCESS_CANCELED':
        return '결제가 취소되었습니다.'
      case 'PAY_PROCESS_ABORTED':
        return '결제가 중단되었습니다.'
      case 'REJECT_CARD_COMPANY':
        return '카드사에서 결제를 거부했습니다. 다른 카드로 시도해주세요.'
      case 'INVALID_CARD_NUMBER':
        return '카드 번호가 올바르지 않습니다.'
      case 'INVALID_CARD_EXPIRATION':
        return '카드 유효기간이 올바르지 않습니다.'
      case 'INVALID_CARD_CVC':
        return 'CVC 번호가 올바르지 않습니다.'
      case 'EXCEED_CARD_LIMIT':
        return '카드 한도가 초과되었습니다.'
      case 'DUPLICATED_ORDER_ID':
        return '중복된 주문입니다. 다시 시도해주세요.'
      default:
        return errorMessage || '결제 처리 중 오류가 발생했습니다.'
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="max-w-md mx-auto text-center px-4">
        <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-6">
          <XCircle className="w-8 h-8 text-red-600" />
        </div>
        <h1 className="text-2xl font-bold text-gray-900 mb-4">결제 실패</h1>
        <p className="text-gray-600 mb-2">{getErrorDescription(errorCode)}</p>
        {errorCode && (
          <p className="text-gray-400 text-sm mb-6">오류 코드: {errorCode}</p>
        )}
        <div className="space-y-3">
          <Link href="/pricing">
            <Button className="w-full">다시 시도하기</Button>
          </Link>
          <Link href="/">
            <Button variant="outline" className="w-full">홈으로 돌아가기</Button>
          </Link>
        </div>

        <div className="mt-8 p-4 bg-gray-50 rounded-lg text-left">
          <h3 className="font-medium text-gray-900 mb-2">문제가 계속되나요?</h3>
          <ul className="text-sm text-gray-600 space-y-1">
            <li>- 다른 카드로 결제를 시도해보세요</li>
            <li>- 카드사 앱에서 결제 한도를 확인해주세요</li>
            <li>- 해외 결제가 차단되어 있다면 해제해주세요</li>
          </ul>
        </div>
      </div>
    </div>
  )
}

export default function CheckoutFailPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center">
          <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
        </div>
      }
    >
      <CheckoutFailContent />
    </Suspense>
  )
}
