'use client'

import { useState, useCallback } from 'react'
import { Heart } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuth } from '@/contexts/AuthContext'
import { useToast } from '@/components/ui'
import { api } from '@/lib/api'

interface FavoriteButtonProps {
  listingId: number
  initialFavorite?: boolean
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
  className?: string
  onToggle?: (isFavorite: boolean) => void
}

export function FavoriteButton({
  listingId,
  initialFavorite = false,
  size = 'md',
  showLabel = false,
  className,
  onToggle,
}: FavoriteButtonProps) {
  const { isAuthenticated } = useAuth()
  const { error: showError, success: showSuccess } = useToast()
  const [isFavorite, setIsFavorite] = useState(initialFavorite)
  const [isLoading, setIsLoading] = useState(false)

  const sizes = {
    sm: 'w-4 h-4',
    md: 'w-5 h-5',
    lg: 'w-6 h-6',
  }

  const buttonSizes = {
    sm: 'p-1.5',
    md: 'p-2',
    lg: 'p-2.5',
  }

  const handleToggle = useCallback(async () => {
    if (!isAuthenticated) {
      showError('로그인이 필요합니다', '관심 매물을 저장하려면 로그인해주세요.')
      return
    }

    setIsLoading(true)
    try {
      if (isFavorite) {
        await api.removeFavoriteListing(listingId)
        setIsFavorite(false)
        showSuccess('관심 매물에서 제거되었습니다')
        onToggle?.(false)
      } else {
        await api.addFavoriteListing(listingId)
        setIsFavorite(true)
        showSuccess('관심 매물에 추가되었습니다')
        onToggle?.(true)
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : '오류가 발생했습니다'
      showError('처리 실패', message)
    } finally {
      setIsLoading(false)
    }
  }, [isAuthenticated, isFavorite, listingId, onToggle, showError, showSuccess])

  return (
    <button
      onClick={handleToggle}
      disabled={isLoading}
      className={cn(
        'inline-flex items-center justify-center rounded-full transition-all duration-200',
        'hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        buttonSizes[size],
        className
      )}
      aria-label={isFavorite ? '관심 매물에서 제거' : '관심 매물에 추가'}
    >
      <Heart
        className={cn(
          sizes[size],
          'transition-all duration-200',
          isFavorite
            ? 'fill-red-500 text-red-500'
            : 'text-gray-400 hover:text-red-400',
          isLoading && 'animate-pulse'
        )}
      />
      {showLabel && (
        <span
          className={cn(
            'ml-1.5 text-sm font-medium',
            isFavorite ? 'text-red-500' : 'text-gray-600'
          )}
        >
          {isFavorite ? '관심' : '저장'}
        </span>
      )}
    </button>
  )
}
