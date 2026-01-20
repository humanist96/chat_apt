'use client'

import { useState, useEffect } from 'react'
import { RecommendationCard } from './RecommendationCard'
import { Loader2 } from 'lucide-react'

interface Filters {
  dongCode: string
  minPrice?: number
  maxPrice?: number
  minArea?: number
  maxArea?: number
}

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

interface RecommendationListProps {
  filters: Filters
}

// Mock data for demo (will be replaced with API call)
const MOCK_RECOMMENDATIONS: Recommendation[] = [
  {
    listing_id: 1,
    apartment_id: 101,
    apartment_name: '래미안 대치팰리스',
    listing_price: 235000,
    area: 84.95,
    price_per_pyeong: 9150,
    recommendation_score: 87.5,
    discount_percent: -8.3,
    rank: 1,
  },
  {
    listing_id: 2,
    apartment_id: 102,
    apartment_name: '은마아파트',
    listing_price: 185000,
    area: 76.79,
    price_per_pyeong: 7960,
    recommendation_score: 82.1,
    discount_percent: -6.2,
    rank: 2,
  },
  {
    listing_id: 3,
    apartment_id: 103,
    apartment_name: '잠실엘스',
    listing_price: 275000,
    area: 84.82,
    price_per_pyeong: 10720,
    recommendation_score: 79.8,
    discount_percent: -5.1,
    rank: 3,
  },
  {
    listing_id: 4,
    apartment_id: 104,
    apartment_name: '반포자이',
    listing_price: 320000,
    area: 114.5,
    price_per_pyeong: 9230,
    recommendation_score: 76.4,
    discount_percent: -4.5,
    rank: 4,
  },
]

export function RecommendationList({ filters }: RecommendationListProps) {
  const [recommendations, setRecommendations] = useState<Recommendation[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchRecommendations = async () => {
      setIsLoading(true)
      setError(null)

      try {
        // TODO: Replace with actual API call
        // const params = new URLSearchParams()
        // if (filters.dongCode) params.append('dong_code', filters.dongCode)
        // if (filters.minPrice) params.append('min_price', filters.minPrice.toString())
        // if (filters.maxPrice) params.append('max_price', filters.maxPrice.toString())
        // const response = await fetch(`/api/recommendations/top?${params}`)
        // const data = await response.json()
        // setRecommendations(data.recommendations)

        // Mock delay and data for demo
        await new Promise((resolve) => setTimeout(resolve, 500))
        setRecommendations(MOCK_RECOMMENDATIONS)
      } catch (err) {
        setError('데이터를 불러오는데 실패했습니다.')
      } finally {
        setIsLoading(false)
      }
    }

    fetchRecommendations()
  }, [filters])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
        <span className="ml-2 text-gray-600">추천 매물을 분석 중...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-500">{error}</p>
        <button
          onClick={() => window.location.reload()}
          className="mt-4 text-primary-600 hover:underline"
        >
          다시 시도
        </button>
      </div>
    )
  }

  if (recommendations.length === 0) {
    return (
      <div className="text-center py-12 bg-gray-50 rounded-lg">
        <p className="text-gray-500">조건에 맞는 추천 매물이 없습니다.</p>
        <p className="text-sm text-gray-400 mt-2">검색 조건을 변경해 보세요.</p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {recommendations.map((recommendation) => (
        <RecommendationCard key={recommendation.listing_id} data={recommendation} />
      ))}
    </div>
  )
}
