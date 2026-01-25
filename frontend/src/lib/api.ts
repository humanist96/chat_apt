import type {
  Recommendation,
  Apartment,
  Listing,
  ComparisonReport,
  PriceTrendData,
  SimilarApartment,
  SearchFilters,
  FireSalesResponse,
  FireSale,
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
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
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

  // Fire Sales
  async getFireSales(
    dongCode?: string,
    minDiscountRate: number = 15,
    limit: number = 50
  ): Promise<FireSalesResponse> {
    const params = new URLSearchParams()
    params.append('min_discount_rate', minDiscountRate.toString())
    params.append('limit', limit.toString())
    if (dongCode) params.append('dong_code', dongCode)

    return this.request<FireSalesResponse>(`/api/analysis/fire-sales?${params}`)
  }

  async getFireSaleAnalysis(listingId: number): Promise<FireSale> {
    return this.request<FireSale>(`/api/analysis/fire-sales/${listingId}`)
  }

  // Dashboard Stats
  async getDashboardStats(): Promise<{
    apartments: number
    listings: number
    transactions: number
    fire_sales: number
  }> {
    // Aggregate stats from multiple endpoints
    const [apartments, listings] = await Promise.all([
      this.request<{ total: number }>('/api/apartments/count').catch(() => ({ total: 0 })),
      this.request<{ total: number }>('/api/listings/count').catch(() => ({ total: 0 })),
    ])

    const fireSales = await this.getFireSales(undefined, 15, 100).catch(() => ({ total_count: 0 }))

    return {
      apartments: apartments.total || 0,
      listings: listings.total || 0,
      transactions: 0,
      fire_sales: fireSales.total_count || 0,
    }
  }

  // Auth
  async getCurrentUser(): Promise<any> {
    return this.request('/api/auth/me')
  }

  async updateProfile(data: { name?: string; avatar_url?: string }): Promise<any> {
    return this.request('/api/auth/me', {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  }

  // Favorites
  async getFavoriteListings(): Promise<any[]> {
    return this.request('/api/favorites/listings')
  }

  async addFavoriteListing(listingId: number): Promise<void> {
    await this.request('/api/favorites/listings', {
      method: 'POST',
      body: JSON.stringify({ listing_id: listingId }),
    })
  }

  async removeFavoriteListing(listingId: number): Promise<void> {
    await this.request(`/api/favorites/listings/${listingId}`, {
      method: 'DELETE',
    })
  }

  async checkFavoriteStatus(listingId: number): Promise<{ is_favorite: boolean }> {
    return this.request(`/api/favorites/listings/${listingId}/status`)
  }

  async getFavoriteRegions(): Promise<any[]> {
    return this.request('/api/favorites/regions')
  }

  async addFavoriteRegion(dongCode: string, regionName?: string): Promise<void> {
    await this.request('/api/favorites/regions', {
      method: 'POST',
      body: JSON.stringify({ dong_code: dongCode, region_name: regionName }),
    })
  }

  async removeFavoriteRegion(dongCode: string): Promise<void> {
    await this.request(`/api/favorites/regions/${dongCode}`, {
      method: 'DELETE',
    })
  }

  // Payments
  async confirmPayment(data: {
    paymentKey: string
    orderId: string
    amount: number
  }): Promise<{ status: string; payment_key: string; amount: number; receipt_url?: string }> {
    return this.request('/api/payments/confirm', {
      method: 'POST',
      body: JSON.stringify({
        payment_key: data.paymentKey,
        order_id: data.orderId,
        amount: data.amount,
      }),
    })
  }

  async createSubscription(data: {
    plan: string
    authKey: string
  }): Promise<any> {
    return this.request('/api/payments/subscription', {
      method: 'POST',
      body: JSON.stringify({
        plan: data.plan,
        auth_key: data.authKey,
      }),
    })
  }

  async getSubscription(): Promise<any> {
    return this.request('/api/payments/subscription')
  }

  async cancelSubscription(): Promise<{ message: string; ends_at: string }> {
    return this.request('/api/payments/subscription/cancel', {
      method: 'POST',
    })
  }

  async getPaymentHistory(limit: number = 20): Promise<any[]> {
    return this.request(`/api/payments/history?limit=${limit}`)
  }
}

export const api = new ApiClient(API_BASE_URL)
