'use client'

import { useState, useEffect } from 'react'
import { RecommendationCard } from './RecommendationCard'
import { Loader2 } from 'lucide-react'
import { api } from '@/lib/api'
import type { FireSale } from '@/types'

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

// Convert area (m²) to pyeong
const toPyeong = (areaM2: number): number => areaM2 / 3.30579

// Convert fire sale data to recommendation format
const convertFireSaleToRecommendation = (
  fireSale: FireSale,
  rank: number
): Recommendation => {
  const areaPyeong = toPyeong(fireSale.area)
  const pricePerPyeong = Math.round(fireSale.asking_price / areaPyeong)
  // Higher discount = higher recommendation score (base 60 + up to 40 bonus)
  const recommendationScore = Math.min(100, 60 + fireSale.discount_rate * 2)

  return {
    listing_id: fireSale.listing_id,
    apartment_id: fireSale.apartment_id,
    apartment_name: fireSale.apartment_name,
    listing_price: fireSale.asking_price,
    area: fireSale.area,
    price_per_pyeong: pricePerPyeong,
    recommendation_score: Math.round(recommendationScore * 10) / 10,
    discount_percent: -fireSale.discount_rate, // Negative because it's below market
    rank,
  }
}

export function RecommendationList({ filters }: RecommendationListProps) {
  const [recommendations, setRecommendations] = useState<Recommendation[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchRecommendations = async () => {
      setIsLoading(true)
      setError(null)

      try {
        // Fetch fire sales as recommendations (undervalued listings)
        const dongCode = filters.dongCode || undefined
        const { fire_sales } = await api.getFireSales(dongCode, 10, 20)

        // Filter by price and area if specified
        let filteredSales = fire_sales
        if (filters.minPrice) {
          filteredSales = filteredSales.filter(
            (fs) => fs.asking_price >= filters.minPrice!
          )
        }
        if (filters.maxPrice) {
          filteredSales = filteredSales.filter(
            (fs) => fs.asking_price <= filters.maxPrice!
          )
        }
        if (filters.minArea) {
          filteredSales = filteredSales.filter(
            (fs) => fs.area >= filters.minArea!
          )
        }
        if (filters.maxArea) {
          filteredSales = filteredSales.filter(
            (fs) => fs.area <= filters.maxArea!
          )
        }

        // Convert to recommendation format and take top 4
        const converted = filteredSales
          .slice(0, 4)
          .map((fs, idx) => convertFireSaleToRecommendation(fs, idx + 1))

        setRecommendations(converted)
      } catch (err) {
        console.error('Failed to fetch recommendations:', err)
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
