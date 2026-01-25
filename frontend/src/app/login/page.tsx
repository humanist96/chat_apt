'use client'

import { Suspense, useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { AlertTriangle } from 'lucide-react'
import { LoginForm, SocialLoginButtons, Divider } from '@/components/auth'
import { useAuth } from '@/contexts/AuthContext'
import { useToast } from '@/components/ui'

function LoginContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { isAuthenticated, isLoading, isConfigured } = useAuth()
  const { info } = useToast()

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.push('/dashboard')
    }
  }, [isAuthenticated, isLoading, router])

  useEffect(() => {
    const message = searchParams.get('message')
    if (message) {
      info(message)
    }
  }, [searchParams, info])

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-primary-600 border-t-transparent" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <Link href="/" className="flex justify-center">
          <div className="flex items-center space-x-2">
            <div className="w-10 h-10 bg-primary-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-lg">CA</span>
            </div>
            <span className="text-2xl font-bold text-gray-900">Chat APT</span>
          </div>
        </Link>
        <h2 className="mt-6 text-center text-2xl font-bold text-gray-900">
          로그인
        </h2>
        <p className="mt-2 text-center text-sm text-gray-600">
          부동산 투자의 새로운 기준
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-4 shadow-sm rounded-2xl sm:px-10 border border-gray-100">
          {!isConfigured && (
            <div className="mb-6 p-4 rounded-lg bg-yellow-50 border border-yellow-200">
              <div className="flex items-start">
                <AlertTriangle className="w-5 h-5 text-yellow-600 mt-0.5 mr-2 flex-shrink-0" />
                <div>
                  <p className="text-sm font-medium text-yellow-800">
                    개발 모드
                  </p>
                  <p className="text-xs text-yellow-700 mt-1">
                    Supabase 환경변수가 설정되지 않았습니다.
                    <code className="mx-1 px-1 bg-yellow-100 rounded">.env.local</code>
                    파일에 설정해주세요.
                  </p>
                </div>
              </div>
            </div>
          )}
          <SocialLoginButtons />
          <Divider />
          <LoginForm />
        </div>
      </div>
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-primary-600 border-t-transparent" />
        </div>
      }
    >
      <LoginContent />
    </Suspense>
  )
}
