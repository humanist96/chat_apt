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

// Default timeout of 30 seconds
const DEFAULT_TIMEOUT = 30000

// Retry configuration
const MAX_RETRIES = 3
const RETRY_DELAY_BASE = 1000 // 1 second

interface RetryConfig {
  maxRetries?: number
  retryDelay?: number
  retryStatusCodes?: number[]
}

class ApiError extends Error {
  constructor(
    message: string,
    public statusCode: number,
    public detail?: string
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

class ApiClient {
  private baseUrl: string
  private token: string | null = null
  private refreshToken: string | null = null
  private onTokenRefresh?: (newToken: string) => void

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl
  }

  setToken(token: string | null) {
    this.token = token
  }

  setRefreshToken(refreshToken: string | null) {
    this.refreshToken = refreshToken
  }

  setOnTokenRefresh(callback: (newToken: string) => void) {
    this.onTokenRefresh = callback
  }

  private async sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms))
  }

  private async fetchWithTimeout(
    url: string,
    options: RequestInit,
    timeout: number
  ): Promise<Response> {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeout)

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
      })
      return response
    } finally {
      clearTimeout(timeoutId)
    }
  }

  private shouldRetry(statusCode: number, retryStatusCodes: number[]): boolean {
    return retryStatusCodes.includes(statusCode)
  }

  private async attemptTokenRefresh(): Promise<boolean> {
    if (!this.refreshToken) {
      return false
    }

    try {
      const response = await fetch(`${this.baseUrl}/api/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ refresh_token: this.refreshToken }),
      })

      if (response.ok) {
        const data = await response.json()
        if (data.access_token) {
          this.token = data.access_token
          if (this.onTokenRefresh) {
            this.onTokenRefresh(data.access_token)
          }
          return true
        }
      }
    } catch {
      // Token refresh failed
    }

    return false
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    retryConfig: RetryConfig = {}
  ): Promise<T> {
    const {
      maxRetries = MAX_RETRIES,
      retryDelay = RETRY_DELAY_BASE,
      retryStatusCodes = [408, 429, 500, 502, 503, 504],
    } = retryConfig

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    }

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`
    }

    let lastError: Error | null = null

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        const response = await this.fetchWithTimeout(
          `${this.baseUrl}${endpoint}`,
          {
            ...options,
            headers,
          },
          DEFAULT_TIMEOUT
        )

        // Handle 401 Unauthorized - attempt token refresh
        if (response.status === 401 && attempt === 0 && this.refreshToken) {
          const refreshed = await this.attemptTokenRefresh()
          if (refreshed) {
            // Update headers with new token and retry
            headers['Authorization'] = `Bearer ${this.token}`
            continue
          }
        }

        if (!response.ok) {
          const errorBody = await response.json().catch(() => ({ detail: 'Unknown error' }))

          // Check if we should retry this status code
          if (
            attempt < maxRetries &&
            this.shouldRetry(response.status, retryStatusCodes)
          ) {
            // Exponential backoff with jitter
            const delay = retryDelay * Math.pow(2, attempt) + Math.random() * 1000
            await this.sleep(delay)
            continue
          }

          throw new ApiError(
            errorBody.detail || `HTTP ${response.status}`,
            response.status,
            errorBody.detail
          )
        }

        return response.json()
      } catch (error) {
        lastError = error as Error

        // Handle abort/timeout errors
        if (error instanceof Error && error.name === 'AbortError') {
          throw new ApiError('Request timeout', 408, 'The request timed out')
        }

        // Handle network errors with retry
        if (
          error instanceof TypeError &&
          error.message.includes('fetch') &&
          attempt < maxRetries
        ) {
          const delay = retryDelay * Math.pow(2, attempt) + Math.random() * 1000
          await this.sleep(delay)
          continue
        }

        // Re-throw ApiErrors immediately
        if (error instanceof ApiError) {
          throw error
        }
      }
    }

    // All retries exhausted
    throw lastError || new Error('Request failed after retries')
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
