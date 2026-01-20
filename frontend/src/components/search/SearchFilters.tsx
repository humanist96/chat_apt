'use client'

import { Search } from 'lucide-react'

interface Filters {
  dongCode: string
  minPrice?: number
  maxPrice?: number
  minArea?: number
  maxArea?: number
}

interface SearchFiltersProps {
  filters: Filters
  onFiltersChange: (filters: Filters) => void
}

const REGIONS = [
  { code: '', name: '전체 지역' },
  { code: '11680', name: '서울 강남구' },
  { code: '11650', name: '서울 서초구' },
  { code: '11710', name: '서울 송파구' },
  { code: '11740', name: '서울 강동구' },
  { code: '11440', name: '서울 마포구' },
  { code: '41135', name: '경기 성남시 분당구' },
  { code: '41465', name: '경기 용인시 수지구' },
]

const PRICE_OPTIONS = [
  { value: undefined, label: '제한 없음' },
  { value: 30000, label: '3억' },
  { value: 50000, label: '5억' },
  { value: 70000, label: '7억' },
  { value: 100000, label: '10억' },
  { value: 150000, label: '15억' },
  { value: 200000, label: '20억' },
]

const AREA_OPTIONS = [
  { value: undefined, label: '제한 없음' },
  { value: 59, label: '59㎡ (18평)' },
  { value: 84, label: '84㎡ (25평)' },
  { value: 114, label: '114㎡ (34평)' },
  { value: 135, label: '135㎡ (41평)' },
]

export function SearchFilters({ filters, onFiltersChange }: SearchFiltersProps) {
  const handleChange = (key: keyof Filters, value: string | number | undefined) => {
    onFiltersChange({
      ...filters,
      [key]: value,
    })
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
      {/* Region Select */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          지역
        </label>
        <select
          value={filters.dongCode}
          onChange={(e) => handleChange('dongCode', e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        >
          {REGIONS.map((region) => (
            <option key={region.code} value={region.code}>
              {region.name}
            </option>
          ))}
        </select>
      </div>

      {/* Min Price */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          최소 가격
        </label>
        <select
          value={filters.minPrice ?? ''}
          onChange={(e) => handleChange('minPrice', e.target.value ? Number(e.target.value) : undefined)}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        >
          {PRICE_OPTIONS.map((option) => (
            <option key={option.label} value={option.value ?? ''}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      {/* Max Price */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          최대 가격
        </label>
        <select
          value={filters.maxPrice ?? ''}
          onChange={(e) => handleChange('maxPrice', e.target.value ? Number(e.target.value) : undefined)}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        >
          {PRICE_OPTIONS.map((option) => (
            <option key={option.label} value={option.value ?? ''}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      {/* Min Area */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          최소 면적
        </label>
        <select
          value={filters.minArea ?? ''}
          onChange={(e) => handleChange('minArea', e.target.value ? Number(e.target.value) : undefined)}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        >
          {AREA_OPTIONS.map((option) => (
            <option key={option.label} value={option.value ?? ''}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      {/* Search Button */}
      <div className="flex items-end">
        <button
          type="button"
          className="w-full bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 transition flex items-center justify-center space-x-2"
        >
          <Search className="w-5 h-5" />
          <span>검색</span>
        </button>
      </div>
    </div>
  )
}
