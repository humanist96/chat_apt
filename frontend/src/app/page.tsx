'use client'

import { useState } from 'react'
import { SearchFilters } from '@/components/search/SearchFilters'
import { RecommendationList } from '@/components/recommendations/RecommendationList'
import { PricingSection } from '@/components/home/PricingSection'
import { FeatureSection } from '@/components/home/FeatureSection'

export default function HomePage() {
  const [filters, setFilters] = useState({
    dongCode: '',
    minPrice: undefined as number | undefined,
    maxPrice: undefined as number | undefined,
    minArea: undefined as number | undefined,
    maxArea: undefined as number | undefined,
  })

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Hero Section */}
      <section className="text-center py-12 mb-8">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          아파트 저평가 매물 분석
        </h1>
        <p className="text-xl text-gray-600 max-w-2xl mx-auto">
          네이버 부동산 호가와 실거래가를 분석하여
          <br />
          <span className="text-primary-600 font-semibold">유사 매물 대비 저렴한 급매물</span>을 찾아드립니다.
        </p>
      </section>

      {/* Search Section */}
      <section className="bg-white rounded-xl shadow-lg p-6 mb-8">
        <h2 className="text-xl font-semibold mb-4">매물 검색</h2>
        <SearchFilters filters={filters} onFiltersChange={setFilters} />
      </section>

      {/* Recommendations */}
      <section className="mb-12">
        <h2 className="text-2xl font-bold mb-6">추천 매물</h2>
        <RecommendationList filters={filters} />
      </section>

      {/* Features */}
      <FeatureSection />

      {/* Pricing */}
      <PricingSection />
    </div>
  )
}
