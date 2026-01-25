'use client'

import { useMemo } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceDot,
} from 'recharts'
import type { PriceTrendData } from '@/types'

interface ComparisonChartData {
  targetTrend: PriceTrendData[]
  comparisonTrends: {
    name: string
    data: PriceTrendData[]
    color: string
  }[]
  currentAskingPrice?: number
  currentAskingPricePerPyeong?: number
}

interface PriceComparisonChartProps {
  data: ComparisonChartData
  className?: string
}

export function PriceComparisonChart({ data, className }: PriceComparisonChartProps) {
  const { targetTrend, comparisonTrends, currentAskingPricePerPyeong } = data

  // Merge all data into a single dataset for the chart
  const chartData = useMemo(() => {
    const dataMap = new Map<string, any>()

    // Add target apartment data
    targetTrend.forEach((item) => {
      dataMap.set(item.year_month, {
        year_month: item.year_month,
        target: item.avg_price_per_pyeong,
      })
    })

    // Add comparison apartments data
    comparisonTrends.forEach((apt, index) => {
      apt.data.forEach((item) => {
        const existing = dataMap.get(item.year_month) || { year_month: item.year_month }
        existing[`comparison_${index}`] = item.avg_price_per_pyeong
        dataMap.set(item.year_month, existing)
      })
    })

    // Sort by year_month
    return Array.from(dataMap.values()).sort((a, b) =>
      a.year_month.localeCompare(b.year_month)
    )
  }, [targetTrend, comparisonTrends])

  // Find the latest month for the reference dot
  const latestMonth = chartData.length > 0 ? chartData[chartData.length - 1].year_month : null

  const formatYAxis = (value: number) => {
    if (value >= 10000) {
      return `${(value / 10000).toFixed(1)}억`
    }
    return `${value.toLocaleString()}만`
  }

  const formatTooltip = (value: number) => {
    return `${value.toLocaleString()}만원/평`
  }

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload) return null

    return (
      <div className="bg-white p-3 rounded-lg shadow-lg border border-gray-200">
        <p className="font-medium text-gray-900 mb-2">{label}</p>
        {payload.map((entry: any, index: number) => (
          <p
            key={index}
            className="text-sm"
            style={{ color: entry.color }}
          >
            {entry.name}: {formatTooltip(entry.value)}
          </p>
        ))}
      </div>
    )
  }

  if (chartData.length === 0) {
    return (
      <div className={`flex items-center justify-center h-64 bg-gray-50 rounded-xl ${className}`}>
        <p className="text-gray-500">가격 추이 데이터가 없습니다</p>
      </div>
    )
  }

  return (
    <div className={className}>
      <ResponsiveContainer width="100%" height={400}>
        <LineChart
          data={chartData}
          margin={{ top: 20, right: 30, left: 20, bottom: 10 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis
            dataKey="year_month"
            tick={{ fontSize: 12, fill: '#6b7280' }}
            tickLine={{ stroke: '#e5e7eb' }}
            axisLine={{ stroke: '#e5e7eb' }}
          />
          <YAxis
            tickFormatter={formatYAxis}
            tick={{ fontSize: 12, fill: '#6b7280' }}
            tickLine={{ stroke: '#e5e7eb' }}
            axisLine={{ stroke: '#e5e7eb' }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ paddingTop: 20 }}
            formatter={(value) => <span className="text-sm text-gray-700">{value}</span>}
          />

          {/* Target apartment line - solid blue */}
          <Line
            type="monotone"
            dataKey="target"
            name="대상 아파트"
            stroke="#2563eb"
            strokeWidth={3}
            dot={{ fill: '#2563eb', strokeWidth: 2, r: 4 }}
            activeDot={{ r: 6 }}
          />

          {/* Comparison apartment lines - dashed gray */}
          {comparisonTrends.map((apt, index) => (
            <Line
              key={index}
              type="monotone"
              dataKey={`comparison_${index}`}
              name={apt.name}
              stroke={apt.color}
              strokeWidth={2}
              strokeDasharray="5 5"
              dot={false}
              activeDot={{ r: 4 }}
            />
          ))}

          {/* Current asking price dot */}
          {currentAskingPricePerPyeong && latestMonth && (
            <ReferenceDot
              x={latestMonth}
              y={currentAskingPricePerPyeong}
              r={8}
              fill="#ef4444"
              stroke="#fff"
              strokeWidth={2}
            />
          )}
        </LineChart>
      </ResponsiveContainer>

      {/* Legend for current asking price */}
      {currentAskingPricePerPyeong && (
        <div className="mt-4 flex items-center justify-center gap-6 text-sm">
          <div className="flex items-center gap-2">
            <div className="w-4 h-0.5 bg-primary-600" />
            <span className="text-gray-600">대상 아파트 실거래가</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-0.5 bg-gray-400 border-dashed" style={{ borderTopStyle: 'dashed' }} />
            <span className="text-gray-600">비교 아파트</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-red-500" />
            <span className="text-gray-600">현재 호가</span>
          </div>
        </div>
      )}
    </div>
  )
}
