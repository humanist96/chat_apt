'use client'

import { TrendingDown, TrendingUp, MapPin, Percent } from 'lucide-react'
import { Badge, Card } from '@/components/ui'
import { formatPrice } from '@/lib/utils'

interface SimilarApartmentCardProps {
  name: string
  similarityScore: number
  avgPricePerPyeong: number
  gapPercent: number
  isSelected?: boolean
  onClick?: () => void
}

export function SimilarApartmentCard({
  name,
  similarityScore,
  avgPricePerPyeong,
  gapPercent,
  isSelected = false,
  onClick,
}: SimilarApartmentCardProps) {
  const getSimilarityColor = (score: number) => {
    if (score >= 80) return 'success'
    if (score >= 60) return 'warning'
    return 'default'
  }

  const isUndervalued = gapPercent < 0

  return (
    <Card
      className={`cursor-pointer transition-all duration-200 ${
        isSelected ? 'ring-2 ring-primary-500 shadow-md' : ''
      }`}
      hoverable
      padding="sm"
      onClick={onClick}
    >
      <div className="flex flex-col h-full">
        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <h4 className="font-semibold text-gray-900 text-sm truncate flex-1 mr-2">
            {name}
          </h4>
          <Badge variant={getSimilarityColor(similarityScore) as any} size="sm">
            유사도 {similarityScore}%
          </Badge>
        </div>

        {/* Price info */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-500">평균 평당가</span>
            <span className="font-medium">{avgPricePerPyeong.toLocaleString()}만</span>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-500">가격 차이</span>
            <div
              className={`flex items-center ${
                isUndervalued ? 'text-green-600' : 'text-red-600'
              }`}
            >
              {isUndervalued ? (
                <TrendingDown className="w-4 h-4 mr-1" />
              ) : (
                <TrendingUp className="w-4 h-4 mr-1" />
              )}
              <span className="font-semibold">
                {Math.abs(gapPercent).toFixed(1)}%
              </span>
            </div>
          </div>
        </div>

        {/* Status indicator */}
        <div className="mt-3 pt-3 border-t border-gray-100">
          <p
            className={`text-xs font-medium ${
              isUndervalued ? 'text-green-600' : 'text-red-600'
            }`}
          >
            {isUndervalued
              ? `비교 아파트 대비 ${Math.abs(gapPercent).toFixed(1)}% 저렴`
              : `비교 아파트 대비 ${gapPercent.toFixed(1)}% 비쌈`}
          </p>
        </div>
      </div>
    </Card>
  )
}
