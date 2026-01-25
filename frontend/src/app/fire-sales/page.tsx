'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { ExternalLink } from 'lucide-react'
import { api } from '@/lib/api'
import type { FireSale, FireSalesResponse } from '@/types'
import { DONG_CODE_NAMES, getNaverListingUrl } from '@/types'
import { formatPrice, formatArea } from '@/lib/utils'

const REGIONS = [
  { code: '', name: '전체 지역' },
  { code: '11680', name: '강남구' },
  { code: '11650', name: '서초구' },
  { code: '11710', name: '송파구' },
  { code: '11740', name: '강동구' },
  { code: '11440', name: '마포구' },
  { code: '11170', name: '용산구' },
]

const DISCOUNT_OPTIONS = [
  { value: 10, label: '10% 이상' },
  { value: 15, label: '15% 이상' },
  { value: 20, label: '20% 이상' },
  { value: 30, label: '30% 이상' },
]

function UrgencyBadge({ level }: { level: string }) {
  const colors = {
    HIGH: 'bg-red-100 text-red-800 border-red-200',
    MEDIUM: 'bg-orange-100 text-orange-800 border-orange-200',
    LOW: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  }

  const labels = {
    HIGH: '급매',
    MEDIUM: '관심',
    LOW: '저가',
  }

  return (
    <span className={`px-2 py-1 text-xs font-semibold rounded-full border ${colors[level as keyof typeof colors]}`}>
      {labels[level as keyof typeof labels]}
    </span>
  )
}

function FireSaleCard({ sale }: { sale: FireSale }) {
  const regionName = DONG_CODE_NAMES[sale.dong_code] || sale.dong_code
  const naverUrl = getNaverListingUrl(sale.naver_complex_no, sale.latitude, sale.longitude)

  return (
    <div className="bg-white rounded-lg shadow-md border border-gray-200 p-5 hover:shadow-lg transition-shadow">
      <div className="flex justify-between items-start mb-3">
        <div>
          <Link href={`/listing/${sale.listing_id}`} className="hover:text-blue-600">
            <h3 className="text-lg font-bold text-gray-900">{sale.apartment_name}</h3>
          </Link>
          <p className="text-sm text-gray-500">{regionName}</p>
        </div>
        <UrgencyBadge level={sale.urgency_level} />
      </div>

      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <span className="text-gray-600">현재 호가</span>
          <span className="text-xl font-bold text-blue-600">{formatPrice(sale.asking_price)}</span>
        </div>

        <div className="flex justify-between items-center">
          <span className="text-gray-600">전고점</span>
          <span className="text-lg text-gray-800 line-through">{formatPrice(sale.all_time_high)}</span>
        </div>

        <div className="flex justify-between items-center bg-red-50 rounded-lg p-2">
          <span className="text-red-700 font-medium">할인율</span>
          <span className="text-2xl font-bold text-red-600">-{sale.discount_rate.toFixed(1)}%</span>
        </div>

        <div className="pt-3 border-t border-gray-100 grid grid-cols-2 gap-2 text-sm">
          <div>
            <span className="text-gray-500">면적</span>
            <p className="font-medium">{formatArea(sale.area)}</p>
          </div>
          <div>
            <span className="text-gray-500">층</span>
            <p className="font-medium">{sale.floor ? `${sale.floor}층` : '-'}</p>
          </div>
          <div className="col-span-2">
            <span className="text-gray-500">전고점 날짜</span>
            <p className="font-medium">{sale.all_time_high_date}</p>
          </div>
        </div>

        {/* Action buttons */}
        <div className="pt-3 border-t flex gap-2">
          <Link
            href={`/listing/${sale.listing_id}`}
            className="flex-1 text-center px-3 py-2 text-sm font-medium text-blue-600 bg-blue-50 rounded-lg hover:bg-blue-100 transition"
          >
            상세보기
          </Link>
          {naverUrl && (
            <a
              href={naverUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-1 px-3 py-2 text-sm font-medium text-green-600 bg-green-50 rounded-lg hover:bg-green-100 transition"
            >
              <ExternalLink className="w-4 h-4" />
              네이버
            </a>
          )}
        </div>
      </div>
    </div>
  )
}

export default function FireSalesPage() {
  const [fireSales, setFireSales] = useState<FireSale[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedRegion, setSelectedRegion] = useState('')
  const [minDiscount, setMinDiscount] = useState(15)

  useEffect(() => {
    async function fetchData() {
      setLoading(true)
      setError(null)

      try {
        const response = await api.getFireSales(
          selectedRegion || undefined,
          minDiscount,
          100
        )
        setFireSales(response.fire_sales)
      } catch (err) {
        setError(err instanceof Error ? err.message : '데이터를 불러오는데 실패했습니다.')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [selectedRegion, minDiscount])

  const highCount = fireSales.filter(s => s.urgency_level === 'HIGH').length
  const mediumCount = fireSales.filter(s => s.urgency_level === 'MEDIUM').length

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">급매 매물 탐지</h1>
        <p className="text-gray-600">
          전고점 대비 할인된 매물을 찾아보세요. 높은 할인율은 급매 가능성을 나타냅니다.
        </p>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-6">
        <div className="flex flex-wrap gap-4">
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-gray-700 mb-1">지역</label>
            <select
              value={selectedRegion}
              onChange={(e) => setSelectedRegion(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              {REGIONS.map((region) => (
                <option key={region.code} value={region.code}>
                  {region.name}
                </option>
              ))}
            </select>
          </div>

          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-gray-700 mb-1">최소 할인율</label>
            <select
              value={minDiscount}
              onChange={(e) => setMinDiscount(Number(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              {DISCOUNT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-red-50 rounded-lg p-4 text-center">
          <p className="text-3xl font-bold text-red-600">{highCount}</p>
          <p className="text-sm text-red-700">급매 (20%+)</p>
        </div>
        <div className="bg-orange-50 rounded-lg p-4 text-center">
          <p className="text-3xl font-bold text-orange-600">{mediumCount}</p>
          <p className="text-sm text-orange-700">관심 (15%+)</p>
        </div>
        <div className="bg-blue-50 rounded-lg p-4 text-center">
          <p className="text-3xl font-bold text-blue-600">{fireSales.length}</p>
          <p className="text-sm text-blue-700">전체 매물</p>
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent"></div>
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
          {error}
        </div>
      ) : fireSales.length === 0 ? (
        <div className="bg-gray-50 rounded-lg p-8 text-center">
          <p className="text-gray-600">조건에 맞는 급매 매물이 없습니다.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {fireSales.map((sale) => (
            <FireSaleCard key={sale.listing_id} sale={sale} />
          ))}
        </div>
      )}
    </div>
  )
}
