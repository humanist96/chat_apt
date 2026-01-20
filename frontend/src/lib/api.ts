import type {
  Recommendation,
  Apartment,
  Listing,
  ComparisonReport,
  PriceTrendData,
  SimilarApartment,
  SearchFilters,
} from '@/types'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

class ApiClient {
  private baseUrl: string
  private token: string | null = null

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl
  }

  setToken(token: string | null) {
    this.token = token
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    }

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`
    }

    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers,
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
      throw new Error(error.detail || `HTTP ${response.status}`)
    }

    return response.json()
  }

  // Apartments
  async getApartments(filters?: SearchFilters): Promise<Apartment[]> {
    const params = new URLSearchParams()
    if (filters?.dong_code) params.append('dong_code', filters.dong_code)
    if (filters?.min_price) params.append('min_price', filters.min_price.toString())
    if (filters?.max_price) params.append('max_price', filters.max_price.toString())

    return this.request<Apartment[]>(`/api/apartments?${params}`)
  }

  async getApartment(id: number): Promise<Apartment> {
    return this.request<Apartment>(`/api/apartments/${id}`)
  }

  // Listings
  async getListings(filters?: SearchFilters): Promise<Listing[]> {
    const params = new URLSearchParams()
    if (filters?.dong_code) params.append('dong_code', filters.dong_code)
    if (filters?.min_price) params.append('min_price', filters.min_price.toString())
    if (filters?.max_price) params.append('max_price', filters.max_price.toString())
    if (filters?.min_area) params.append('min_area', filters.min_area.toString())
    if (filters?.max_area) params.append('max_area', filters.max_area.toString())

    return this.request<Listing[]>(`/api/listings?${params}`)
  }

  async getListing(id: number): Promise<Listing> {
    return this.request<Listing>(`/api/listings/${id}`)
  }

  // Recommendations
  async getTopRecommendations(
    filters?: SearchFilters,
    limit: number = 20
  ): Promise<{ recommendations: Recommendation[]; total_count: number }> {
    const params = new URLSearchParams()
    params.append('limit', limit.toString())
    if (filters?.dong_code) params.append('dong_code', filters.dong_code)
    if (filters?.min_price) params.append('min_price', filters.min_price.toString())
    if (filters?.max_price) params.append('max_price', filters.max_price.toString())
    if (filters?.min_area) params.append('min_area', filters.min_area.toString())
    if (filters?.max_area) params.append('max_area', filters.max_area.toString())

    return this.request(`/api/recommendations/top?${params}`)
  }

  async getUndervaluedListings(
    dongCode?: string,
    limit: number = 20
  ): Promise<Recommendation[]> {
    const params = new URLSearchParams()
    params.append('limit', limit.toString())
    if (dongCode) params.append('dong_code', dongCode)

    return this.request<Recommendation[]>(`/api/recommendations/undervalued?${params}`)
  }

  // Analysis
  async getSimilarApartments(apartmentId: number): Promise<SimilarApartment[]> {
    return this.request<SimilarApartment[]>(`/api/analysis/similar/${apartmentId}`)
  }

  async getComparisonReport(listingId: number): Promise<ComparisonReport> {
    return this.request<ComparisonReport>(`/api/analysis/comparison/${listingId}`)
  }

  async getPriceTrend(
    apartmentId: number,
    months: number = 24
  ): Promise<PriceTrendData[]> {
    return this.request<PriceTrendData[]>(
      `/api/analysis/price-trend/${apartmentId}?months=${months}`
    )
  }

  // Transactions
  async getTransactions(apartmentId: number): Promise<any[]> {
    return this.request(`/api/transactions?apartment_id=${apartmentId}`)
  }
}

export const api = new ApiClient(API_BASE_URL)
