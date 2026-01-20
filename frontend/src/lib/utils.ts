import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * Merge Tailwind CSS classes with clsx
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Format price in Korean currency style
 * @param price - Price in 만원 (10,000 KRW units)
 */
export function formatPrice(price: number): string {
  if (price >= 10000) {
    const billion = Math.floor(price / 10000)
    const remainder = price % 10000
    if (remainder > 0) {
      return `${billion}억 ${remainder.toLocaleString()}만`
    }
    return `${billion}억`
  }
  return `${price.toLocaleString()}만`
}

/**
 * Format area from m² to 평
 * @param areaM2 - Area in square meters
 */
export function formatArea(areaM2: number): string {
  const pyeong = Math.round(areaM2 / 3.306)
  return `${areaM2}㎡ (${pyeong}평)`
}

/**
 * Calculate 평 from m²
 */
export function toPyeong(areaM2: number): number {
  return Math.round(areaM2 / 3.306)
}

/**
 * Format date string
 */
export function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

/**
 * Format percentage with sign
 */
export function formatPercent(value: number, decimals: number = 1): string {
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(decimals)}%`
}

/**
 * Get color class based on value (positive/negative)
 */
export function getValueColor(value: number): string {
  if (value < 0) return 'text-green-600'
  if (value > 0) return 'text-red-600'
  return 'text-gray-600'
}

/**
 * Get score color class
 */
export function getScoreColor(score: number): string {
  if (score >= 80) return 'text-green-600 bg-green-100'
  if (score >= 60) return 'text-yellow-600 bg-yellow-100'
  return 'text-red-600 bg-red-100'
}

/**
 * Debounce function
 */
export function debounce<T extends (...args: any[]) => void>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout | null = null

  return function executedFunction(...args: Parameters<T>) {
    if (timeout) {
      clearTimeout(timeout)
    }
    timeout = setTimeout(() => func(...args), wait)
  }
}
