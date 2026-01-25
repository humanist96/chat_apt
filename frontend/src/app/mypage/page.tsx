'use client'

import { Suspense, useEffect, useState, useCallback } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import {
  User,
  Heart,
  MapPin,
  CreditCard,
  Edit2,
  Check,
  X,
  Trash2,
} from 'lucide-react'
import { useAuth, useRequireAuth } from '@/contexts/AuthContext'
import { useToast } from '@/components/ui'
import { api } from '@/lib/api'
import { formatPrice, formatArea } from '@/lib/utils'
import {
  Button,
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Badge,
  Input,
  ListSkeleton,
} from '@/components/ui'
import { DONG_CODE_NAMES } from '@/types'

type TabType = 'profile' | 'favorites' | 'regions' | 'billing'

interface FavoriteListing {
  id: number
  listing_id: number
  apartment_name: string | null
  price: number | null
  area: number | null
  floor: number | null
  created_at: string
}

interface FavoriteRegion {
  id: number
  dong_code: string | null
  region_name: string | null
  created_at: string
}

function MyPageContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { isAuthenticated, isLoading: authLoading, user, profile, updateProfile } = useRequireAuth()
  const { success, error: showError } = useToast()

  const [activeTab, setActiveTab] = useState<TabType>('profile')
  const [isEditing, setIsEditing] = useState(false)
  const [editName, setEditName] = useState('')
  const [isSaving, setIsSaving] = useState(false)

  const [favorites, setFavorites] = useState<FavoriteListing[]>([])
  const [regions, setRegions] = useState<FavoriteRegion[]>([])
  const [isLoadingFavorites, setIsLoadingFavorites] = useState(false)
  const [isLoadingRegions, setIsLoadingRegions] = useState(false)

  useEffect(() => {
    const tab = searchParams.get('tab')
    if (tab && ['profile', 'favorites', 'regions', 'billing'].includes(tab)) {
      setActiveTab(tab as TabType)
    }
  }, [searchParams])

  const loadFavorites = useCallback(async () => {
    setIsLoadingFavorites(true)
    try {
      const data = await api.getFavoriteListings()
      setFavorites(data)
    } catch (err) {
      console.error('Failed to load favorites:', err)
    } finally {
      setIsLoadingFavorites(false)
    }
  }, [])

  const loadRegions = useCallback(async () => {
    setIsLoadingRegions(true)
    try {
      const data = await api.getFavoriteRegions()
      setRegions(data)
    } catch (err) {
      console.error('Failed to load regions:', err)
    } finally {
      setIsLoadingRegions(false)
    }
  }, [])

  useEffect(() => {
    if (!isAuthenticated) return

    if (activeTab === 'favorites') {
      loadFavorites()
    } else if (activeTab === 'regions') {
      loadRegions()
    }
  }, [activeTab, isAuthenticated, loadFavorites, loadRegions])

  const handleEditStart = () => {
    setEditName(profile?.name || '')
    setIsEditing(true)
  }

  const handleEditCancel = () => {
    setIsEditing(false)
    setEditName('')
  }

  const handleEditSave = async () => {
    setIsSaving(true)
    try {
      await updateProfile({ name: editName })
      setIsEditing(false)
      success('프로필이 업데이트되었습니다')
    } catch (err) {
      showError('저장 실패', err instanceof Error ? err.message : '오류가 발생했습니다')
    } finally {
      setIsSaving(false)
    }
  }

  const handleRemoveFavorite = async (listingId: number) => {
    try {
      await api.removeFavoriteListing(listingId)
      setFavorites((prev) => prev.filter((f) => f.listing_id !== listingId))
      success('관심 매물에서 제거되었습니다')
    } catch (err) {
      showError('삭제 실패', err instanceof Error ? err.message : '오류가 발생했습니다')
    }
  }

  const handleRemoveRegion = async (dongCode: string) => {
    try {
      await api.removeFavoriteRegion(dongCode)
      setRegions((prev) => prev.filter((r) => r.dong_code !== dongCode))
      success('관심 지역에서 제거되었습니다')
    } catch (err) {
      showError('삭제 실패', err instanceof Error ? err.message : '오류가 발생했습니다')
    }
  }

  const tabs = [
    { id: 'profile' as const, label: '프로필', icon: User },
    { id: 'favorites' as const, label: '관심 매물', icon: Heart },
    { id: 'regions' as const, label: '관심 지역', icon: MapPin },
    { id: 'billing' as const, label: '결제 내역', icon: CreditCard },
  ]

  const tierLabels = {
    free: '무료',
    basic: '베이직',
    premium: '프리미엄',
  }

  const tierColors = {
    free: 'default' as const,
    basic: 'info' as const,
    premium: 'warning' as const,
  }

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-primary-600 border-t-transparent" />
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-2xl font-bold text-gray-900 mb-8">마이페이지</h1>

        <div className="flex flex-col md:flex-row gap-8">
          <div className="md:w-48 flex-shrink-0">
            <nav className="space-y-1">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-left transition-colors ${
                    activeTab === tab.id
                      ? 'bg-primary-50 text-primary-700 font-medium'
                      : 'text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  <tab.icon className="w-5 h-5" />
                  <span>{tab.label}</span>
                </button>
              ))}
            </nav>
          </div>

          <div className="flex-1">
            {activeTab === 'profile' && (
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle>프로필 정보</CardTitle>
                    {!isEditing && (
                      <Button variant="ghost" size="sm" onClick={handleEditStart}>
                        <Edit2 className="w-4 h-4 mr-1" />
                        수정
                      </Button>
                    )}
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-6">
                    <div className="flex items-center gap-4">
                      <div className="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center">
                        <User className="w-8 h-8 text-primary-600" />
                      </div>
                      <div className="flex-1">
                        {isEditing ? (
                          <div className="flex items-center gap-2">
                            <Input
                              value={editName}
                              onChange={(e) => setEditName(e.target.value)}
                              placeholder="이름"
                              className="max-w-xs"
                            />
                            <Button size="sm" onClick={handleEditSave} isLoading={isSaving}>
                              <Check className="w-4 h-4" />
                            </Button>
                            <Button size="sm" variant="ghost" onClick={handleEditCancel}>
                              <X className="w-4 h-4" />
                            </Button>
                          </div>
                        ) : (
                          <>
                            <p className="font-semibold text-lg">{profile?.name || '이름 없음'}</p>
                            <p className="text-gray-500">{user?.email}</p>
                          </>
                        )}
                      </div>
                    </div>

                    <div className="p-4 bg-gray-50 rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-gray-600">현재 요금제</span>
                        <Badge variant={tierColors[profile?.membership_tier || 'free']}>
                          {tierLabels[profile?.membership_tier || 'free']}
                        </Badge>
                      </div>
                      {profile?.membership_tier === 'free' && (
                        <Link href="/pricing">
                          <Button size="sm" className="mt-2">업그레이드</Button>
                        </Link>
                      )}
                    </div>

                    <div className="space-y-3">
                      <div className="flex justify-between py-2 border-b">
                        <span className="text-gray-500">이메일</span>
                        <span>{user?.email}</span>
                      </div>
                      <div className="flex justify-between py-2 border-b">
                        <span className="text-gray-500">가입일</span>
                        <span>
                          {profile?.created_at
                            ? new Date(profile.created_at).toLocaleDateString('ko-KR')
                            : '-'}
                        </span>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {activeTab === 'favorites' && (
              <Card>
                <CardHeader>
                  <CardTitle>관심 매물 ({favorites.length})</CardTitle>
                </CardHeader>
                <CardContent>
                  {isLoadingFavorites ? (
                    <ListSkeleton count={3} />
                  ) : favorites.length === 0 ? (
                    <div className="text-center py-8">
                      <Heart className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                      <p className="text-gray-500">저장된 관심 매물이 없습니다</p>
                      <Link href="/listings">
                        <Button variant="outline" className="mt-4">매물 둘러보기</Button>
                      </Link>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {favorites.map((fav) => (
                        <div key={fav.id} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                          <Link href={`/listing/${fav.listing_id}`} className="flex-1 hover:opacity-80 transition">
                            <p className="font-medium text-gray-900">{fav.apartment_name || '알 수 없는 매물'}</p>
                            <div className="flex items-center gap-3 text-sm text-gray-500 mt-1">
                              {fav.price && <span>{formatPrice(fav.price)}</span>}
                              {fav.area && <span>{formatArea(fav.area)}</span>}
                              {fav.floor && <span>{fav.floor}층</span>}
                            </div>
                          </Link>
                          <button
                            onClick={() => handleRemoveFavorite(fav.listing_id)}
                            className="p-2 text-gray-400 hover:text-red-500 transition"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {activeTab === 'regions' && (
              <Card>
                <CardHeader>
                  <CardTitle>관심 지역 ({regions.length})</CardTitle>
                </CardHeader>
                <CardContent>
                  {isLoadingRegions ? (
                    <ListSkeleton count={3} />
                  ) : regions.length === 0 ? (
                    <div className="text-center py-8">
                      <MapPin className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                      <p className="text-gray-500">저장된 관심 지역이 없습니다</p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {regions.map((region) => (
                        <div key={region.id} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                          <div className="flex items-center gap-3">
                            <MapPin className="w-5 h-5 text-primary-500" />
                            <span className="font-medium">
                              {region.region_name ||
                                DONG_CODE_NAMES[region.dong_code || ''] ||
                                region.dong_code}
                            </span>
                          </div>
                          <button
                            onClick={() => region.dong_code && handleRemoveRegion(region.dong_code)}
                            className="p-2 text-gray-400 hover:text-red-500 transition"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}

                  {profile?.membership_tier === 'free' && regions.length >= 3 && (
                    <div className="mt-4 p-4 bg-yellow-50 rounded-lg">
                      <p className="text-sm text-yellow-700">
                        무료 회원은 최대 3개 지역만 저장할 수 있습니다.
                        <Link href="/pricing" className="font-medium underline ml-1">업그레이드</Link>
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {activeTab === 'billing' && (
              <Card>
                <CardHeader>
                  <CardTitle>결제 내역</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-center py-8">
                    <CreditCard className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                    <p className="text-gray-500">결제 내역이 없습니다</p>
                    {profile?.membership_tier === 'free' && (
                      <Link href="/pricing">
                        <Button className="mt-4">요금제 둘러보기</Button>
                      </Link>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default function MyPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-primary-600 border-t-transparent" />
        </div>
      }
    >
      <MyPageContent />
    </Suspense>
  )
}
