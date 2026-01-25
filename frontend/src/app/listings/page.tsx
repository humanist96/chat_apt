'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { ExternalLink } from 'lucide-react'
import { api } from '@/lib/api'
import type { Listing, SearchFilters } from '@/types'
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

const PRICE_RANGES = [
  { min: 0, max: 0, label: '전체 가격' },
  { min: 0, max: 50000, label: '5억 이하' },
  { min: 50000, max: 100000, label: '5억 ~ 10억' },
  { min: 100000, max: 150000, label: '10억 ~ 15억' },
  { min: 150000, max: 200000, label: '15억 ~ 20억' },
  { min: 200000, max: 0, label: '20억 이상' },
]

const AREA_RANGES = [
  { min: 0, max: 0, label: '전체 면적' },
  { min: 0, max: 60, label: '60㎡ 이하 (18평)' },
  { min: 60, max: 85, label: '60~85㎡ (25평)' },
  { min: 85, max: 115, label: '85~115㎡ (34평)' },
  { min: 115, max: 0, label: '115㎡ 이상 (35평+)' },
]

interface ListingWithApartment extends Listing {
  apartment_name?: string
  dong_code?: string
}

function ListingCard({ listing }: { listing: ListingWithApartment }) {
  const regionName = listing.dong_code ? DONG_CODE_NAMES[listing.dong_code] || listing.dong_code : ''
  const naverUrl = getNaverListingUrl(listing.naver_complex_no, listing.latitude, listing.longitude)

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 hover:shadow-md transition-shadow">
      <div className="flex justify-between items-start mb-3">
        <div>
          <Link href={`/listing/${listing.id}`} className="hover:text-blue-600">
            <h3 className="font-bold text-gray-900">{listing.apartment_name || `아파트 #${listing.apartment_id}`}</h3>
          </Link>
          <p className="text-sm text-gray-500">{regionName}</p>
        </div>
        <span className={`px-2 py-1 text-xs font-medium rounded-full ${
          listing.is_active
            ? 'bg-green-100 text-green-800'
            : 'bg-gray-100 text-gray-600'
        }`}>
          {listing.is_active ? '매물 가능' : '거래완료'}
        </span>
      </div>

      <Link href={`/listing/${listing.id}`}>
        <div className="text-2xl font-bold text-blue-600 mb-3 hover:text-blue-700">
          {formatPrice(listing.price)}
        </div>
      </Link>

      <div className="grid grid-cols-2 gap-2 text-sm text-gray-600">
        <div>
          <span className="text-gray-400">면적</span>
          <p className="font-medium text-gray-800">{formatArea(listing.area)}</p>
        </div>
        <div>
          <span className="text-gray-400">층수</span>
          <p className="font-medium text-gray-800">{listing.floor ? `${listing.floor}층` : '-'}</p>
        </div>
        <div>
          <span className="text-gray-400">방향</span>
          <p className="font-medium text-gray-800">{listing.direction || '-'}</p>
        </div>
        <div>
          <span className="text-gray-400">매물번호</span>
          <p className="font-medium text-gray-800 truncate">{listing.article_no || '-'}</p>
        </div>
      </div>

      {listing.description && (
        <p className="mt-3 text-sm text-gray-600 line-clamp-2 border-t pt-3">
          {listing.description}
        </p>
      )}

      {/* Action buttons */}
      <div className="mt-3 pt-3 border-t flex gap-2">
        <Link
          href={`/listing/${listing.id}`}
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
  )
}

export default function ListingsPage() {
  const [listings, setListings] = useState<ListingWithApartment[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState<SearchFilters>({})
  const [priceRangeIdx, setPriceRangeIdx] = useState(0)
  const [areaRangeIdx, setAreaRangeIdx] = useState(0)

  useEffect(() => {
    async function fetchData() {
      setLoading(true)
      setError(null)

      try {
        const priceRange = PRICE_RANGES[priceRangeIdx]
        const areaRange = AREA_RANGES[areaRangeIdx]

        const searchFilters: SearchFilters = { ...filters }

        if (priceRange.min > 0) searchFilters.min_price = priceRange.min
        if (priceRange.max > 0) searchFilters.max_price = priceRange.max
        if (areaRange.min > 0) searchFilters.min_area = areaRange.min
        if (areaRange.max > 0) searchFilters.max_area = areaRange.max

        const data = await api.getListings(searchFilters)
        setListings(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : '데이터를 불러오는데 실패했습니다.')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [filters, priceRangeIdx, areaRangeIdx])

  const activeCount = listings.filter(l => l.is_active).length

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">매물 목록</h1>
        <p className="text-gray-600">
          수집된 네이버 부동산 호가 데이터를 조회합니다.
        </p>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">지역</label>
            <select
              value={filters.dong_code || ''}
              onChange={(e) => setFilters({ ...filters, dong_code: e.target.value || undefined })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              {REGIONS.map((region) => (
                <option key={region.code} value={region.code}>
                  {region.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">가격대</label>
            <select
              value={priceRangeIdx}
              onChange={(e) => setPriceRangeIdx(Number(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              {PRICE_RANGES.map((range, idx) => (
                <option key={idx} value={idx}>
                  {range.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">면적</label>
            <select
              value={areaRangeIdx}
              onChange={(e) => setAreaRangeIdx(Number(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              {AREA_RANGES.map((range, idx) => (
                <option key={idx} value={idx}>
                  {range.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Summary */}
      <div className="flex items-center justify-between mb-4">
        <p className="text-gray-600">
          총 <span className="font-bold text-gray-900">{listings.length}</span>건의 매물
          (활성: <span className="text-green-600 font-medium">{activeCount}</span>건)
        </p>
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
      ) : listings.length === 0 ? (
        <div className="bg-gray-50 rounded-lg p-8 text-center">
          <p className="text-gray-600">조건에 맞는 매물이 없습니다.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {listings.map((listing) => (
            <ListingCard key={listing.id} listing={listing} />
          ))}
        </div>
      )}
    </div>
  )
}
