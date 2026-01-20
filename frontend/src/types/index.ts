// API Response Types

export interface Apartment {
  id: number
  name: string
  address: string
  dong_code: string
  latitude: number
  longitude: number
  total_units: number
  built_year: number
}

export interface Listing {
  id: number
  apartment_id: number
  article_no: string
  trade_type: string
  price: number
  area: number
  floor: number
  direction: string
  description: string
  realtor_name: string
  is_active: boolean
}

export interface Transaction {
  id: number
  apartment_id: number
  deal_amount: number
  area: number
  floor: number
  deal_year: number
  deal_month: number
  deal_day: number
}

export interface Recommendation {
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

export interface SimilarApartment {
  id: number
  name: string
  similarity_score: number
  location_score: number
  area_score: number
  correlation_score: number
}

export interface ComparisonReport {
  listing_id: number
  listing_price: number
  listing_price_per_pyeong: number
  similar_avg_price_per_pyeong: number
  gap_percent: number
  is_undervalued: boolean
  comparison_results: SimilarApartmentComparison[]
}

export interface SimilarApartmentComparison {
  apartment_id: number
  apartment_name: string
  avg_price_per_pyeong: number
  gap_percent: number
  similarity_score: number
}

export interface PriceTrendData {
  year_month: string
  avg_price: number
  avg_price_per_pyeong: number
  transaction_count: number
}

// User & Auth Types

export interface User {
  id: string
  email: string
  name: string
  membership_tier: 'free' | 'basic' | 'premium'
  created_at: string
}

export interface Subscription {
  id: number
  plan: string
  status: string
  current_period_start: string
  current_period_end: string
}

// API Request Types

export interface SearchFilters {
  dong_code?: string
  min_price?: number
  max_price?: number
  min_area?: number
  max_area?: number
  trade_type?: string
}

export interface PaginationParams {
  limit?: number
  offset?: number
}

// API Response Wrapper

export interface ApiResponse<T> {
  data: T
  total_count?: number
  page?: number
  limit?: number
}

export interface ApiError {
  detail: string
  status_code: number
}
