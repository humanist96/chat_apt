'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { api } from '@/lib/api'
import type { FireSale } from '@/types'
import { DONG_CODE_NAMES } from '@/types'
import { formatPrice } from '@/lib/utils'

interface DashboardData {
  totalListings: number
  totalFireSales: number
  regionStats: { dong_code: string; count: number }[]
  topFireSales: FireSale[]
}

function StatCard({
  title,
  value,
  icon,
  color,
  link,
}: {
  title: string
  value: string | number
  icon: string
  color: string
  link?: string
}) {
  const content = (
    <div className={`bg-white rounded-xl shadow-sm border border-gray-200 p-6 ${link ? 'hover:shadow-md transition-shadow cursor-pointer' : ''}`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500 mb-1">{title}</p>
          <p className={`text-3xl font-bold ${color}`}>{value}</p>
        </div>
        <div className={`text-4xl ${color} opacity-20`}>{icon}</div>
      </div>
    </div>
  )

  if (link) {
    return <Link href={link}>{content}</Link>
  }
  return content
}

function TopFireSalesList({ sales }: { sales: FireSale[] }) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold text-gray-900">TOP 급매 매물</h3>
        <Link href="/fire-sales" className="text-blue-600 text-sm hover:underline">
          전체보기 &rarr;
        </Link>
      </div>

      <div className="space-y-3">
        {sales.map((sale, idx) => (
          <div
            key={sale.listing_id}
            className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
          >
            <div className="flex items-center gap-3">
              <span className={`w-8 h-8 rounded-full flex items-center justify-center text-white font-bold ${
                idx === 0 ? 'bg-red-500' : idx === 1 ? 'bg-orange-500' : idx === 2 ? 'bg-yellow-500' : 'bg-gray-400'
              }`}>
                {idx + 1}
              </span>
              <div>
                <p className="font-medium text-gray-900">{sale.apartment_name}</p>
                <p className="text-sm text-gray-500">
                  {DONG_CODE_NAMES[sale.dong_code] || sale.dong_code}
                </p>
              </div>
            </div>
            <div className="text-right">
              <p className="font-bold text-blue-600">{formatPrice(sale.asking_price)}</p>
              <p className="text-sm text-red-600 font-medium">-{sale.discount_rate.toFixed(1)}%</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function RegionStats({ stats }: { stats: { dong_code: string; count: number }[] }) {
  const maxCount = Math.max(...stats.map(s => s.count), 1)

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <h3 className="text-lg font-bold text-gray-900 mb-4">지역별 매물 현황</h3>

      <div className="space-y-3">
        {stats.map((stat) => (
          <div key={stat.dong_code}>
            <div className="flex justify-between text-sm mb-1">
              <span className="text-gray-700 font-medium">
                {DONG_CODE_NAMES[stat.dong_code] || stat.dong_code}
              </span>
              <span className="text-gray-500">{stat.count}건</span>
            </div>
            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 rounded-full"
                style={{ width: `${(stat.count / maxCount) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData>({
    totalListings: 0,
    totalFireSales: 0,
    regionStats: [],
    topFireSales: [],
  })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchData() {
      try {
        // Fetch fire sales data
        const fireSalesResponse = await api.getFireSales(undefined, 10, 100)

        // Calculate region stats from fire sales
        const regionMap = new Map<string, number>()
        fireSalesResponse.fire_sales.forEach(sale => {
          const count = regionMap.get(sale.dong_code) || 0
          regionMap.set(sale.dong_code, count + 1)
        })

        const regionStats = Array.from(regionMap.entries())
          .map(([dong_code, count]) => ({ dong_code, count }))
          .sort((a, b) => b.count - a.count)

        // Get listings count (we'll estimate from fire sales data)
        let totalListings = 0
        try {
          const listings = await api.getListings({})
          totalListings = listings.length
        } catch {
          totalListings = fireSalesResponse.total_count * 5 // estimate
        }

        setData({
          totalListings,
          totalFireSales: fireSalesResponse.total_count,
          regionStats,
          topFireSales: fireSalesResponse.fire_sales.slice(0, 5),
        })
      } catch (err) {
        console.error('Failed to fetch dashboard data:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [])

  if (loading) {
    return (
      <div className="flex justify-center items-center h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent"></div>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">대시보드</h1>
        <p className="text-gray-600">
          수집된 부동산 데이터 현황을 한눈에 확인하세요.
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          title="전체 매물"
          value={data.totalListings.toLocaleString()}
          icon="🏠"
          color="text-blue-600"
          link="/listings"
        />
        <StatCard
          title="급매 매물"
          value={data.totalFireSales}
          icon="🔥"
          color="text-red-600"
          link="/fire-sales"
        />
        <StatCard
          title="분석 지역"
          value={data.regionStats.length}
          icon="📍"
          color="text-green-600"
        />
        <StatCard
          title="최고 할인율"
          value={data.topFireSales[0] ? `-${data.topFireSales[0].discount_rate.toFixed(1)}%` : '-'}
          icon="📉"
          color="text-orange-600"
        />
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <TopFireSalesList sales={data.topFireSales} />
        <RegionStats stats={data.regionStats} />
      </div>

      {/* Quick Actions */}
      <div className="mt-8 bg-gradient-to-r from-blue-500 to-blue-600 rounded-xl p-6 text-white">
        <h3 className="text-xl font-bold mb-2">빠른 시작</h3>
        <p className="text-blue-100 mb-4">
          급매 매물을 찾거나 전체 매물 목록을 확인해보세요.
        </p>
        <div className="flex gap-4">
          <Link
            href="/fire-sales"
            className="px-4 py-2 bg-white text-blue-600 rounded-lg font-medium hover:bg-blue-50 transition-colors"
          >
            급매 매물 보기
          </Link>
          <Link
            href="/listings"
            className="px-4 py-2 bg-blue-400 text-white rounded-lg font-medium hover:bg-blue-300 transition-colors"
          >
            전체 매물 보기
          </Link>
        </div>
      </div>
    </div>
  )
}
