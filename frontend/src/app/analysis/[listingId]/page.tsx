'use client'

import { useEffect, useState, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import {
  ArrowLeft,
  TrendingDown,
  TrendingUp,
  CheckCircle,
  AlertTriangle,
  MapPin,
  Maximize,
  Building,
} from 'lucide-react'
import { api } from '@/lib/api'
import { formatPrice, formatArea, toPyeong } from '@/lib/utils'
import { useAuth } from '@/contexts/AuthContext'
import {
  Button,
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Badge,
  CardSkeleton,
} from '@/components/ui'
import { PriceComparisonChart, SimilarApartmentCard } from '@/components/analysis'
import { FavoriteButton } from '@/components/FavoriteButton'
import type {
  Listing,
  Apartment,
  ComparisonReport,
  PriceTrendData,
  SimilarApartmentComparison,
} from '@/types'

// Colors for comparison chart lines
const COMPARISON_COLORS = [
  '#9ca3af', // gray-400
  '#6b7280', // gray-500
  '#4b5563', // gray-600
  '#374151', // gray-700
  '#1f2937', // gray-800
]

interface AnalysisData {
  listing: Listing
  apartment: Apartment
  comparison: ComparisonReport
  targetTrend: PriceTrendData[]
  comparisonTrends: Map<number, PriceTrendData[]>
}

export default function AnalysisPage() {
  const params = useParams()
  const router = useRouter()
  const { isAuthenticated } = useAuth()
  const [data, setData] = useState<AnalysisData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedComparison, setSelectedComparison] = useState<number | null>(null)

  const listingId = params.listingId
    ? parseInt(params.listingId as string, 10)
    : null

  const fetchData = useCallback(async () => {
    if (!listingId) return

    setIsLoading(true)
    setError(null)

    try {
      // Get comparison report and listing details
      const [comparison, listing] = await Promise.all([
        api.getComparisonReport(listingId),
        api.getListing(listingId),
      ])

      const apartment = await api.getApartment(listing.apartment_id)

      // Get price trends for target apartment
      const targetTrend = await api.getPriceTrend(listing.apartment_id).catch(() => [])

      // Get price trends for similar apartments
      const comparisonTrends = new Map<number, PriceTrendData[]>()
      await Promise.all(
        comparison.comparison_results.slice(0, 5).map(async (comp) => {
          try {
            const trend = await api.getPriceTrend(comp.apartment_id)
            comparisonTrends.set(comp.apartment_id, trend)
          } catch {
            comparisonTrends.set(comp.apartment_id, [])
          }
        })
      )

      setData({
        listing,
        apartment,
        comparison,
        targetTrend,
        comparisonTrends,
      })

      // Select first comparison by default
      if (comparison.comparison_results.length > 0) {
        setSelectedComparison(comparison.comparison_results[0].apartment_id)
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : '분석 데이터를 불러올 수 없습니다'
      )
    } finally {
      setIsLoading(false)
    }
  }, [listingId])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-6xl mx-auto">
          <CardSkeleton count={3} />
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-6xl mx-auto text-center">
          <div className="bg-red-50 border border-red-200 rounded-xl p-8">
            <p className="text-red-700 mb-4">{error || '분석 데이터를 찾을 수 없습니다'}</p>
            <Button onClick={() => router.back()} variant="outline">
              <ArrowLeft className="w-4 h-4 mr-2" />
              돌아가기
            </Button>
          </div>
        </div>
      </div>
    )
  }

  const { listing, apartment, comparison, targetTrend, comparisonTrends } = data
  const pricePerPyeong = Math.round(listing.price / toPyeong(listing.area))
  const isUndervalued = comparison.is_undervalued

  // Prepare chart data
  const chartData = {
    targetTrend,
    comparisonTrends: comparison.comparison_results.slice(0, 5).map((comp, index) => ({
      name: comp.apartment_name,
      data: comparisonTrends.get(comp.apartment_id) || [],
      color: COMPARISON_COLORS[index % COMPARISON_COLORS.length],
    })),
    currentAskingPricePerPyeong: pricePerPyeong,
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-6xl mx-auto">
        {/* Back button */}
        <button
          onClick={() => router.back()}
          className="flex items-center text-gray-600 hover:text-gray-900 mb-6 transition"
        >
          <ArrowLeft className="w-4 h-4 mr-1" />
          돌아가기
        </button>

        {/* Target Listing Card */}
        <Card className="mb-8">
          <CardContent>
            <div className="flex flex-col md:flex-row md:items-start gap-6">
              {/* Listing Info */}
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <Badge variant="primary">분석 대상</Badge>
                  {isAuthenticated && (
                    <FavoriteButton listingId={listing.id} size="sm" />
                  )}
                </div>
                <h1 className="text-2xl font-bold text-gray-900 mb-2">
                  {apartment.name}
                </h1>
                <div className="flex items-center text-gray-600 mb-4">
                  <MapPin className="w-4 h-4 mr-1" />
                  <span>{apartment.address}</span>
                </div>

                <div className="grid grid-cols-3 gap-4 text-sm">
                  <div>
                    <p className="text-gray-500 mb-1">호가</p>
                    <p className="font-bold text-xl text-primary-600">
                      {formatPrice(listing.price)}
                    </p>
                  </div>
                  <div>
                    <p className="text-gray-500 mb-1">면적</p>
                    <p className="font-semibold">{formatArea(listing.area)}</p>
                  </div>
                  <div>
                    <p className="text-gray-500 mb-1">평당가</p>
                    <p className="font-semibold">{pricePerPyeong.toLocaleString()}만</p>
                  </div>
                </div>
              </div>

              {/* Analysis Result Summary */}
              <div
                className={`p-6 rounded-xl ${
                  isUndervalued ? 'bg-green-50' : 'bg-red-50'
                }`}
              >
                <div className="flex items-center gap-2 mb-3">
                  {isUndervalued ? (
                    <CheckCircle className="w-6 h-6 text-green-600" />
                  ) : (
                    <AlertTriangle className="w-6 h-6 text-red-600" />
                  )}
                  <span
                    className={`font-bold text-lg ${
                      isUndervalued ? 'text-green-700' : 'text-red-700'
                    }`}
                  >
                    {isUndervalued ? '저평가 매물' : '고평가 매물'}
                  </span>
                </div>
                <div className="flex items-baseline gap-2">
                  {isUndervalued ? (
                    <TrendingDown className="w-8 h-8 text-green-600" />
                  ) : (
                    <TrendingUp className="w-8 h-8 text-red-600" />
                  )}
                  <span
                    className={`text-3xl font-bold ${
                      isUndervalued ? 'text-green-600' : 'text-red-600'
                    }`}
                  >
                    {Math.abs(comparison.gap_percent).toFixed(1)}%
                  </span>
                </div>
                <p
                  className={`mt-2 text-sm ${
                    isUndervalued ? 'text-green-700' : 'text-red-700'
                  }`}
                >
                  유사 매물 평균 대비{' '}
                  {isUndervalued ? '저렴합니다' : '비쌉니다'}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Similar Apartments Comparison */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle>유사 아파트 비교 ({comparison.comparison_results.length}개)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
              {comparison.comparison_results.slice(0, 5).map((comp) => (
                <SimilarApartmentCard
                  key={comp.apartment_id}
                  name={comp.apartment_name}
                  similarityScore={Math.round(comp.similarity_score * 100)}
                  avgPricePerPyeong={comp.avg_price_per_pyeong}
                  gapPercent={comp.gap_percent}
                  isSelected={selectedComparison === comp.apartment_id}
                  onClick={() => setSelectedComparison(comp.apartment_id)}
                />
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Price Trend Chart */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle>가격 추이 비교 차트</CardTitle>
          </CardHeader>
          <CardContent>
            <PriceComparisonChart data={chartData} />
          </CardContent>
        </Card>

        {/* Analysis Conclusion */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle>분석 결론</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-start gap-3">
                {isUndervalued ? (
                  <CheckCircle className="w-5 h-5 text-green-600 mt-0.5 flex-shrink-0" />
                ) : (
                  <AlertTriangle className="w-5 h-5 text-red-600 mt-0.5 flex-shrink-0" />
                )}
                <div>
                  <p className="font-semibold text-gray-900">
                    {isUndervalued
                      ? '이 매물은 주변 유사 아파트 대비 저평가되어 있습니다.'
                      : '이 매물은 주변 유사 아파트 대비 고평가되어 있습니다.'}
                  </p>
                  <p className="text-gray-600 mt-1">
                    유사 아파트 {comparison.comparison_results.length}개의 평균 평당가는{' '}
                    <span className="font-medium">
                      {comparison.similar_avg_price_per_pyeong.toLocaleString()}만원
                    </span>
                    이며, 이 매물의 평당가는{' '}
                    <span className="font-medium">
                      {comparison.listing_price_per_pyeong.toLocaleString()}만원
                    </span>
                    입니다.
                  </p>
                </div>
              </div>

              <div className="p-4 bg-gray-50 rounded-lg">
                <p className="text-sm text-gray-600">
                  {isUndervalued ? (
                    <>
                      현재 호가 기준으로{' '}
                      <span className="font-bold text-green-600">
                        약 {formatPrice(
                          Math.round(
                            (comparison.similar_avg_price_per_pyeong -
                              comparison.listing_price_per_pyeong) *
                              toPyeong(listing.area)
                          )
                        )}
                      </span>{' '}
                      저렴하게 매물이 나온 상태입니다.
                    </>
                  ) : (
                    <>
                      현재 호가 기준으로{' '}
                      <span className="font-bold text-red-600">
                        약 {formatPrice(
                          Math.round(
                            (comparison.listing_price_per_pyeong -
                              comparison.similar_avg_price_per_pyeong) *
                              toPyeong(listing.area)
                          )
                        )}
                      </span>{' '}
                      비싸게 나온 상태입니다.
                    </>
                  )}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row gap-4">
          <Link href={`/listing/${listing.id}`} className="flex-1">
            <Button variant="outline" className="w-full" size="lg">
              매물 상세보기
            </Button>
          </Link>
          <Link href="/listings" className="flex-1">
            <Button className="w-full" size="lg">
              다른 매물 찾아보기
            </Button>
          </Link>
        </div>
      </div>
    </div>
  )
}
