'use client'

import Link from 'next/link'
import { TrendingDown, MapPin, Maximize, Award } from 'lucide-react'

interface Recommendation {
  listing_id: number
  apartment_id: number
  apartment_name: string
  listing_price: number
  area: number
  price_per_pyeong: number
  recommendation_score: number
  discount_percent: number
  rank: number
}

interface RecommendationCardProps {
  data: Recommendation
}

export function RecommendationCard({ data }: RecommendationCardProps) {
  const formatPrice = (price: number) => {
    if (price >= 10000) {
      const billion = Math.floor(price / 10000)
      const remainder = price % 10000
      if (remainder > 0) {
        return `${billion}억 ${remainder.toLocaleString()}`
      }
      return `${billion}억`
    }
    return `${price.toLocaleString()}만`
  }

  const formatArea = (areaM2: number) => {
    const pyeong = Math.round(areaM2 / 3.306)
    return `${areaM2}㎡ (${pyeong}평)`
  }

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600 bg-green-100'
    if (score >= 60) return 'text-yellow-600 bg-yellow-100'
    return 'text-red-600 bg-red-100'
  }

  const getRankBadge = (rank: number) => {
    if (rank === 1) return 'bg-yellow-400 text-yellow-900'
    if (rank === 2) return 'bg-gray-300 text-gray-700'
    if (rank === 3) return 'bg-orange-400 text-orange-900'
    return 'bg-gray-200 text-gray-600'
  }

  return (
    <Link href={`/listing/${data.listing_id}`}>
      <div className="bg-white rounded-xl shadow-md hover:shadow-lg transition-shadow overflow-hidden border border-gray-100">
        {/* Rank Badge */}
        <div className="relative">
          <div className="h-32 bg-gradient-to-br from-primary-100 to-primary-200 flex items-center justify-center">
            <span className="text-4xl font-bold text-primary-600">#{data.rank}</span>
          </div>
          <div
            className={`absolute top-2 right-2 px-2 py-1 rounded-full text-xs font-bold ${getRankBadge(data.rank)}`}
          >
            <Award className="w-3 h-3 inline mr-1" />
            TOP {data.rank}
          </div>
        </div>

        {/* Content */}
        <div className="p-4">
          <h3 className="font-bold text-lg text-gray-900 mb-2 truncate">
            {data.apartment_name}
          </h3>

          {/* Price */}
          <div className="mb-3">
            <span className="text-2xl font-bold text-primary-600">
              {formatPrice(data.listing_price)}
            </span>
          </div>

          {/* Details */}
          <div className="space-y-2 text-sm text-gray-600">
            <div className="flex items-center">
              <Maximize className="w-4 h-4 mr-2 text-gray-400" />
              <span>{formatArea(data.area)}</span>
            </div>
            <div className="flex items-center">
              <MapPin className="w-4 h-4 mr-2 text-gray-400" />
              <span>평당 {data.price_per_pyeong.toLocaleString()}만</span>
            </div>
          </div>

          {/* Score & Discount */}
          <div className="mt-4 flex items-center justify-between">
            <div className={`px-2 py-1 rounded-full text-xs font-semibold ${getScoreColor(data.recommendation_score)}`}>
              추천 {data.recommendation_score}점
            </div>
            <div className="flex items-center text-green-600 font-semibold">
              <TrendingDown className="w-4 h-4 mr-1" />
              {Math.abs(data.discount_percent).toFixed(1)}% 저렴
            </div>
          </div>
        </div>
      </div>
    </Link>
  )
}
