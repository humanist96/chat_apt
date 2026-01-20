import { BarChart3, Search, Bell, Shield } from 'lucide-react'

const FEATURES = [
  {
    icon: Search,
    title: '스마트 매물 검색',
    description: '네이버 부동산 데이터를 실시간으로 수집하여 최신 매물 정보를 제공합니다.',
  },
  {
    icon: BarChart3,
    title: '유사 매물 비교 분석',
    description: '동일 단지, 인근 단지의 유사 면적 매물과 가격을 비교 분석합니다.',
  },
  {
    icon: Bell,
    title: '급매 알림',
    description: '설정한 조건의 저평가 매물이 등록되면 즉시 알림을 받을 수 있습니다.',
  },
  {
    icon: Shield,
    title: '실거래가 검증',
    description: '국토교통부 실거래가 데이터와 비교하여 적정 가격을 검증합니다.',
  },
]

export function FeatureSection() {
  return (
    <section className="py-12">
      <h2 className="text-2xl font-bold text-center mb-8">주요 기능</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {FEATURES.map((feature, index) => (
          <div
            key={index}
            className="bg-white rounded-xl p-6 shadow-sm border border-gray-100 hover:shadow-md transition-shadow"
          >
            <div className="w-12 h-12 bg-primary-100 rounded-lg flex items-center justify-center mb-4">
              <feature.icon className="w-6 h-6 text-primary-600" />
            </div>
            <h3 className="font-semibold text-lg mb-2">{feature.title}</h3>
            <p className="text-gray-600 text-sm">{feature.description}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
