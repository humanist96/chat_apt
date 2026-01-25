'use client'

import { useEffect, useState, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import {
  MapPin,
  Maximize,
  Building,
  Calendar,
  ArrowLeft,
  TrendingUp,
  BarChart3,
  Compass,
  Home,
  User,
  ExternalLink,
} from 'lucide-react'
import { api } from '@/lib/api'
import { formatPrice, formatArea, toPyeong, formatDate } from '@/lib/utils'
import { useAuth } from '@/contexts/AuthContext'
import { Button, Card, CardHeader, CardTitle, CardContent, Badge, CardSkeleton } from '@/components/ui'
import { FavoriteButton } from '@/components/FavoriteButton'
import type { Listing, Apartment, Transaction, PriceTrendData } from '@/types'
import { getNaverListingUrl } from '@/types'

interface ListingDetailData {
  listing: Listing
  apartment: Apartment
  transactions: Transaction[]
  priceTrend: PriceTrendData[]
}

export default function ListingDetailPage() {
  const params = useParams()
  const router = useRouter()
  const { isAuthenticated, profile } = useAuth()
  const [data, setData] = useState<ListingDetailData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isFavorite, setIsFavorite] = useState(false)

  const listingId = params.id ? parseInt(params.id as string, 10) : null

  const fetchData = useCallback(async () => {
    if (!listingId) return

    setIsLoading(true)
    setError(null)

    try {
      const listing = await api.getListing(listingId)
      const [apartment, transactions, priceTrend] = await Promise.all([
        api.getApartment(listing.apartment_id),
        api.getTransactions(listing.apartment_id).catch(() => []),
        api.getPriceTrend(listing.apartment_id).catch(() => []),
      ])

      setData({ listing, apartment, transactions, priceTrend })

      // Check favorite status if authenticated
      if (isAuthenticated) {
        try {
          const { is_favorite } = await api.checkFavoriteStatus(listingId)
          setIsFavorite(is_favorite)
        } catch {
          // Ignore errors for favorite check
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '데이터를 불러올 수 없습니다')
    } finally {
      setIsLoading(false)
    }
  }, [listingId, isAuthenticated])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto">
          <CardSkeleton count={1} />
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto text-center">
          <div className="bg-red-50 border border-red-200 rounded-xl p-8">
            <p className="text-red-700 mb-4">{error || '매물을 찾을 수 없습니다'}</p>
            <Button onClick={() => router.back()} variant="outline">
              <ArrowLeft className="w-4 h-4 mr-2" />
              돌아가기
            </Button>
          </div>
        </div>
      </div>
    )
  }

  const { listing, apartment, transactions, priceTrend } = data
  const pricePerPyeong = Math.round(listing.price / toPyeong(listing.area))

  // Filter transactions by exact same type (±1㎡) for accurate comparison
  // Same apartment type typically has area difference within 0.5~1㎡
  const AREA_MARGIN_M2 = 1
  const sameTypeTransactions = transactions.filter(
    (t) => t.area && Math.abs(t.area - listing.area) <= AREA_MARGIN_M2
  )

  // Get recent transactions (same type only for accurate comparison)
  const recentTransactions = sameTypeTransactions.length > 0
    ? sameTypeTransactions.slice(0, 5)
    : [] // Don't show other types as they're not comparable

  // For price comparison, only use same type transactions
  const transactionsForComparison = sameTypeTransactions.slice(0, 5)
  const avgRecentPrice =
    transactionsForComparison.length > 0
      ? Math.round(
          transactionsForComparison.reduce((sum, t) => sum + t.deal_amount, 0) /
            transactionsForComparison.length
        )
      : null

  const priceDiff = avgRecentPrice ? listing.price - avgRecentPrice : null
  const priceDiffPercent = avgRecentPrice
    ? ((listing.price - avgRecentPrice) / avgRecentPrice) * 100
    : null

  // Helper function to format deal_date
  const formatDealDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, '0')}.${String(date.getDate()).padStart(2, '0')}`
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-4xl mx-auto">
        {/* Back button */}
        <button
          onClick={() => router.back()}
          className="flex items-center text-gray-600 hover:text-gray-900 mb-6 transition"
        >
          <ArrowLeft className="w-4 h-4 mr-1" />
          목록으로
        </button>

        {/* Main Info Card */}
        <Card className="mb-6">
          <CardContent>
            <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Badge variant={listing.is_active ? 'success' : 'default'}>
                    {listing.is_active ? '거래가능' : '거래완료'}
                  </Badge>
                  <Badge variant="outline">{listing.trade_type}</Badge>
                </div>
                <h1 className="text-2xl font-bold text-gray-900 mb-2">
                  {apartment.name}
                </h1>
                <div className="flex items-center text-gray-600">
                  <MapPin className="w-4 h-4 mr-1" />
                  <span>{apartment.address}</span>
                </div>
              </div>
              <div className="flex items-start gap-2">
                <FavoriteButton
                  listingId={listing.id}
                  initialFavorite={isFavorite}
                  size="lg"
                  onToggle={setIsFavorite}
                />
              </div>
            </div>

            {/* Price Section */}
            <div className="mt-6 p-4 bg-gray-50 rounded-xl">
              <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
                <div>
                  <p className="text-sm text-gray-500 mb-1">호가</p>
                  <p className="text-3xl font-bold text-primary-600">
                    {formatPrice(listing.price)}
                  </p>
                  <p className="text-sm text-gray-500 mt-1">
                    평당 {pricePerPyeong.toLocaleString()}만원
                  </p>
                </div>
                {priceDiff !== null && (
                  <div className="text-right">
                    <p className="text-sm text-gray-500 mb-1">
                      동일 평형 실거래가 대비
                      <span className="text-xs ml-1">({formatArea(listing.area)})</span>
                    </p>
                    <p
                      className={`text-lg font-semibold ${
                        priceDiff < 0 ? 'text-green-600' : 'text-red-600'
                      }`}
                    >
                      {priceDiff > 0 ? '+' : ''}
                      {formatPrice(priceDiff)}
                      <span className="text-sm ml-1">
                        ({priceDiffPercent! > 0 ? '+' : ''}
                        {priceDiffPercent!.toFixed(1)}%)
                      </span>
                    </p>
                  </div>
                )}
                {avgRecentPrice === null && sameTypeTransactions.length === 0 && transactions.length > 0 && (
                  <div className="text-right">
                    <p className="text-sm text-yellow-600">
                      동일 평형({formatArea(listing.area)}) 거래 내역이 없습니다
                    </p>
                  </div>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Property Details */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          {/* Listing Details */}
          <Card>
            <CardHeader>
              <CardTitle>매물 정보</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center text-gray-600">
                    <Maximize className="w-4 h-4 mr-2" />
                    <span>면적</span>
                  </div>
                  <span className="font-medium">{formatArea(listing.area)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center text-gray-600">
                    <Building className="w-4 h-4 mr-2" />
                    <span>층수</span>
                  </div>
                  <span className="font-medium">{listing.floor}층</span>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center text-gray-600">
                    <Compass className="w-4 h-4 mr-2" />
                    <span>방향</span>
                  </div>
                  <span className="font-medium">{listing.direction || '-'}</span>
                </div>
                {listing.description && (
                  <div className="pt-4 border-t">
                    <p className="text-sm text-gray-600">{listing.description}</p>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Apartment Details */}
          <Card>
            <CardHeader>
              <CardTitle>단지 정보</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center text-gray-600">
                    <Home className="w-4 h-4 mr-2" />
                    <span>총 세대수</span>
                  </div>
                  <span className="font-medium">
                    {apartment.total_units?.toLocaleString() || '-'}세대
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center text-gray-600">
                    <Calendar className="w-4 h-4 mr-2" />
                    <span>건축년도</span>
                  </div>
                  <span className="font-medium">{apartment.built_year}년</span>
                </div>
                {listing.realtor_name && profile?.membership_tier !== 'free' && (
                  <div className="pt-4 border-t">
                    <div className="flex items-center text-gray-600 mb-2">
                      <User className="w-4 h-4 mr-2" />
                      <span>중개사</span>
                    </div>
                    <p className="font-medium">{listing.realtor_name}</p>
                  </div>
                )}
                {listing.realtor_name && profile?.membership_tier === 'free' && (
                  <div className="pt-4 border-t">
                    <p className="text-sm text-gray-500">
                      중개사 정보는 프리미엄 회원만 확인 가능합니다
                    </p>
                    <Link href="/pricing">
                      <Button size="sm" variant="outline" className="mt-2">
                        업그레이드
                      </Button>
                    </Link>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Recent Transactions - Same Type Only */}
        <Card className="mb-6">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>최근 실거래 내역</CardTitle>
              <Badge variant="info">동일 평형({formatArea(listing.area)})</Badge>
            </div>
          </CardHeader>
          <CardContent>
            {recentTransactions.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left py-2 px-3 text-gray-500 font-medium">
                        거래일
                      </th>
                      <th className="text-right py-2 px-3 text-gray-500 font-medium">
                        가격
                      </th>
                      <th className="text-right py-2 px-3 text-gray-500 font-medium">
                        면적
                      </th>
                      <th className="text-right py-2 px-3 text-gray-500 font-medium">
                        층
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentTransactions.map((tx, i) => (
                      <tr key={i} className="border-b last:border-0">
                        <td className="py-3 px-3">
                          {formatDealDate(tx.deal_date)}
                        </td>
                        <td className="py-3 px-3 text-right font-medium">
                          {formatPrice(tx.deal_amount)}
                        </td>
                        <td className="py-3 px-3 text-right text-gray-600">
                          {formatArea(tx.area)}
                        </td>
                        <td className="py-3 px-3 text-right text-gray-600">
                          {tx.floor}층
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <p>동일 평형({formatArea(listing.area)})의 거래 내역이 없습니다.</p>
                {transactions.length > 0 && (
                  <p className="text-sm mt-2">
                    이 아파트의 다른 평형 거래는 {transactions.length}건 있습니다.
                  </p>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row gap-4">
          <Link href={`/analysis/${listing.id}`} className="flex-1">
            <Button className="w-full" size="lg">
              <BarChart3 className="w-5 h-5 mr-2" />
              유사 아파트 비교 분석
            </Button>
          </Link>
          {getNaverListingUrl(listing.naver_complex_no, listing.latitude, listing.longitude) && (
            <a
              href={getNaverListingUrl(listing.naver_complex_no, listing.latitude, listing.longitude)!}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1"
            >
              <Button variant="outline" className="w-full" size="lg">
                <ExternalLink className="w-5 h-5 mr-2" />
                네이버 부동산에서 보기
              </Button>
            </a>
          )}
          <Button variant="ghost" size="lg" onClick={() => router.back()}>
            목록으로
          </Button>
        </div>
      </div>
    </div>
  )
}
