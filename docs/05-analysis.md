# 5. 분석 엔진

## 5.1 유사 매물 비교 분석

> 대상 아파트의 호가가 시세 흐름이 유사했던 인근 아파트들과 비교하여 얼마나 저평가되어 있는지 분석

### 유사도 계산 요소

| 요소 | 가중치 | 설명 |
|------|--------|------|
| 지역 근접성 | 30% | 동일 구/동 또는 반경 2km 이내 |
| 평형 유사성 | 25% | 전용면적 ±5평 이내 |
| 시세 흐름 상관관계 | 25% | 과거 실거래가 추이의 피어슨 상관계수 |
| 단지 규모 | 10% | 세대수 유사성 |
| 건축연도 | 10% | 준공연도 ±5년 이내 |

### 유사 매물 선정 알고리즘

```python
import numpy as np
from scipy.stats import pearsonr
from dataclasses import dataclass

@dataclass
class SimilarityScore:
    apartment_id: int
    apartment_name: str
    total_score: float
    location_score: float
    area_score: float
    correlation_score: float
    scale_score: float
    age_score: float

class SimilarApartmentFinder:
    """유사 아파트 탐색 엔진"""

    def __init__(self):
        self.weights = {
            'location': 0.30,
            'area': 0.25,
            'correlation': 0.25,
            'scale': 0.10,
            'age': 0.10,
        }

    def find_similar_apartments(
        self,
        target_apt: Apartment,
        candidates: list[Apartment],
        top_n: int = 5
    ) -> list[SimilarityScore]:
        """
        대상 아파트와 유사한 아파트 목록 반환

        Args:
            target_apt: 분석 대상 아파트
            candidates: 비교 후보 아파트 목록
            top_n: 반환할 유사 아파트 수

        Returns:
            유사도 점수가 높은 순으로 정렬된 아파트 목록
        """
        scores = []

        for candidate in candidates:
            if candidate.id == target_apt.id:
                continue

            score = self._calculate_similarity(target_apt, candidate)
            scores.append(score)

        # 유사도 높은 순 정렬
        scores.sort(key=lambda x: x.total_score, reverse=True)
        return scores[:top_n]

    def _calculate_similarity(
        self,
        target: Apartment,
        candidate: Apartment
    ) -> SimilarityScore:
        """개별 아파트 간 유사도 계산"""

        # 1. 지역 근접성 (거리 기반)
        distance = self._haversine_distance(
            target.latitude, target.longitude,
            candidate.latitude, candidate.longitude
        )
        location_score = max(0, 100 - (distance / 2) * 100)  # 2km = 0점

        # 2. 평형 유사성
        area_diff = abs(target.area_pyeong - candidate.area_pyeong)
        area_score = max(0, 100 - (area_diff / 5) * 100)  # 5평 차이 = 0점

        # 3. 시세 흐름 상관관계
        correlation_score = self._calculate_price_correlation(
            target.id, candidate.id
        )

        # 4. 단지 규모 유사성
        scale_ratio = min(target.total_units, candidate.total_units) / \
                      max(target.total_units, candidate.total_units)
        scale_score = scale_ratio * 100

        # 5. 건축연도 유사성
        age_diff = abs(target.built_year - candidate.built_year)
        age_score = max(0, 100 - (age_diff / 5) * 100)  # 5년 차이 = 0점

        # 가중 평균 계산
        total_score = (
            location_score * self.weights['location'] +
            area_score * self.weights['area'] +
            correlation_score * self.weights['correlation'] +
            scale_score * self.weights['scale'] +
            age_score * self.weights['age']
        )

        return SimilarityScore(
            apartment_id=candidate.id,
            apartment_name=candidate.name,
            total_score=total_score,
            location_score=location_score,
            area_score=area_score,
            correlation_score=correlation_score,
            scale_score=scale_score,
            age_score=age_score,
        )

    def _calculate_price_correlation(
        self,
        apt_id_1: int,
        apt_id_2: int,
        years: int = 5
    ) -> float:
        """
        두 아파트의 실거래가 추이 상관관계 계산
        월별 평균 평당가 기준
        """
        # 월별 평균 평당가 시계열 데이터 조회
        prices_1 = self._get_monthly_prices(apt_id_1, years)
        prices_2 = self._get_monthly_prices(apt_id_2, years)

        # 공통 기간만 추출
        common_months = set(prices_1.keys()) & set(prices_2.keys())
        if len(common_months) < 12:  # 최소 1년 데이터 필요
            return 0

        series_1 = [prices_1[m] for m in sorted(common_months)]
        series_2 = [prices_2[m] for m in sorted(common_months)]

        # 피어슨 상관계수 계산
        correlation, _ = pearsonr(series_1, series_2)

        # 0-100 스케일로 변환 (상관계수 0.5 이상만 유의미)
        return max(0, (correlation - 0.5) * 200)

    def _haversine_distance(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """두 좌표 간 거리 계산 (km)"""
        R = 6371  # 지구 반경 (km)

        lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))

        return R * c
```

---

## 5.2 비교 분석 리포트

### 리포트 UI 구성

```
┌─────────────────────────────────────────────────────────────────┐
│                   저평가 아파트 분석 보고서                       │
├─────────────────────────────────────────────────────────────────┤
│  대상 아파트: 서초래미안                                          │
│  ├─ 평형: 129.54m² (39.2평)                                     │
│  ├─ 최근 호가: 34.0억원 (평당 8,673만원)                         │
│  ├─ 최근 실거래가: 30.8억원 (평당 7,862만원)                     │
│  ├─ 주소: 서울특별시 서초구 서초대로65길 13-10                    │
│  ├─ 세대수: 1,129세대                                           │
│  └─ 사용승인일: 2003.05.10                                      │
├─────────────────────────────────────────────────────────────────┤
│                      상세 비교 분석                               │
│  과거 시세 흐름이 유사했던 같은 평형(39.2평)                      │
│  아파트들과의 현재 가격 차이를 비교합니다.                         │
├─────────────────────────────────────────────────────────────────┤
│  비교 1: 서초래미안 vs 서초교대e편한세상                          │
│  ├─ 위치: 서울 서초구 서초동                                     │
│  ├─ 시세 상관관계: 94.2%                                        │
│  └─ [차트: 실거래가 추이 비교]                                   │
│      - 파란 실선: 서초래미안 실거래가                             │
│      - 회색 점선: 서초교대e편한세상 실거래가                       │
│      - 빨간 점: 서초래미안 현재 매물호가                          │
├─────────────────────────────────────────────────────────────────┤
│  비교 2: 서초래미안 vs 래미안삼성2차                              │
│  ├─ 위치: 서울 강남구 삼성동                                     │
│  └─ [차트: 실거래가 추이 비교]                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 비교 분석 데이터 구조

```python
@dataclass
class ComparisonAnalysis:
    """유사 매물 비교 분석 결과"""
    target_apartment: ApartmentInfo
    target_listing: ListingInfo
    comparisons: list[ApartmentComparison]
    analysis_date: datetime
    recommendation_summary: str

@dataclass
class ApartmentComparison:
    """개별 아파트 비교 결과"""
    similar_apartment: ApartmentInfo
    similarity_score: float
    price_trend_correlation: float

    # 현재 가격 비교
    target_current_price_per_pyeong: int      # 대상 아파트 평당가 (호가)
    similar_current_price_per_pyeong: int     # 비교 아파트 평당가 (최근 실거래)
    price_gap_percent: float                  # 가격 차이 (%)

    # 시계열 데이터 (차트용)
    target_price_history: list[PricePoint]    # 대상 아파트 실거래 이력
    similar_price_history: list[PricePoint]   # 비교 아파트 실거래 이력
    target_listing_point: PricePoint          # 현재 매물 호가 (차트 표시용)

@dataclass
class PricePoint:
    """가격 시점 데이터"""
    date: date
    price: int                    # 거래가 (만원)
    price_per_pyeong: int         # 평당가 (만원)
    is_listing: bool = False      # 매물 호가 여부
```

---

## 5.3 저평가 판단 로직

```python
class UndervaluationAnalyzer:
    """저평가 매물 분석기"""

    def analyze(
        self,
        target_listing: Listing,
        similar_apartments: list[SimilarityScore]
    ) -> UndervaluationResult:
        """
        유사 매물 대비 저평가 여부 분석

        Returns:
            저평가 분석 결과 (저평가율, 추천 여부, 근거)
        """
        target_price_per_pyeong = target_listing.price / target_listing.area_pyeong

        comparison_results = []
        for similar in similar_apartments:
            # 유사 아파트의 최근 실거래 평당가
            recent_price = self._get_recent_avg_price_per_pyeong(
                similar.apartment_id,
                months=6
            )

            # 가격 갭 계산
            gap_percent = ((target_price_per_pyeong - recent_price) / recent_price) * 100

            comparison_results.append({
                'apartment_name': similar.apartment_name,
                'similarity_score': similar.total_score,
                'recent_price_per_pyeong': recent_price,
                'gap_percent': gap_percent,
            })

        # 가중 평균 저평가율 계산 (유사도를 가중치로 사용)
        total_weight = sum(c['similarity_score'] for c in comparison_results)
        weighted_gap = sum(
            c['gap_percent'] * c['similarity_score']
            for c in comparison_results
        ) / total_weight

        # 저평가 판정
        is_undervalued = weighted_gap < -5  # 5% 이상 저렴하면 저평가

        return UndervaluationResult(
            target_price_per_pyeong=target_price_per_pyeong,
            weighted_gap_percent=weighted_gap,
            is_undervalued=is_undervalued,
            comparisons=comparison_results,
            recommendation=self._generate_recommendation(weighted_gap),
        )

    def _generate_recommendation(self, gap_percent: float) -> str:
        """저평가율에 따른 추천 메시지 생성"""
        if gap_percent < -15:
            return "🔥 강력 추천: 유사 매물 대비 15% 이상 저평가"
        elif gap_percent < -10:
            return "⭐ 추천: 유사 매물 대비 10-15% 저평가"
        elif gap_percent < -5:
            return "👍 관심: 유사 매물 대비 5-10% 저평가"
        elif gap_percent < 5:
            return "➖ 적정가: 유사 매물과 비슷한 수준"
        else:
            return "⚠️ 주의: 유사 매물 대비 고평가"
```

---

## 5.4 추천 점수 계산

```python
def calculate_recommendation_score(listing, transactions):
    """
    추천 점수 계산 (0-100점)
    """
    score = 50  # 기본 점수

    # 1. 최근 실거래가 대비 호가 비교 (최대 ±30점)
    recent_avg = get_recent_avg_price(transactions, months=6)
    price_gap_rate = (listing.price - recent_avg) / recent_avg * 100

    if price_gap_rate < -10:  # 10% 이상 저렴
        score += 30
    elif price_gap_rate < -5:  # 5-10% 저렴
        score += 20
    elif price_gap_rate < 0:   # 0-5% 저렴
        score += 10
    elif price_gap_rate < 5:   # 0-5% 비쌈
        score -= 5
    else:                      # 5% 이상 비쌈
        score -= 15

    # 2. 거래 활성도 (최대 ±10점)
    transaction_count = count_recent_transactions(transactions, months=3)
    if transaction_count >= 5:
        score += 10
    elif transaction_count >= 2:
        score += 5
    else:
        score -= 5  # 거래가 너무 없으면 감점

    # 3. 매물 등록 기간 (최대 ±10점)
    days_listed = (today - listing.created_at).days
    if days_listed > 90:      # 장기 미거래 매물
        score += 10           # 협상 여지 있음
    elif days_listed > 30:
        score += 5

    return max(0, min(100, score))
```

### 필터링 기준

| 필터 | 설명 | 기본값 |
|------|------|--------|
| 지역 | 시/구/동 선택 | 필수 |
| 면적 | 전용면적 범위 | 전체 |
| 가격 | 호가 범위 | 전체 |
| 층수 | 선호 층수 | 전체 |
| 할인율 | 최소 할인율 | 0% |
| 추천점수 | 최소 점수 | 60점 |

---

## 5.5 가격 추이 시각화 (차트)

### 프론트엔드 차트 컴포넌트

```typescript
// PriceComparisonChart.tsx
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, ReferenceDot } from 'recharts';

interface PriceComparisonChartProps {
  targetName: string;
  similarName: string;
  targetHistory: PricePoint[];
  similarHistory: PricePoint[];
  currentListingPrice: PricePoint;
}

export function PriceComparisonChart({
  targetName,
  similarName,
  targetHistory,
  similarHistory,
  currentListingPrice,
}: PriceComparisonChartProps) {
  // 데이터 병합 (날짜 기준)
  const mergedData = mergeTimeSeriesData(targetHistory, similarHistory);

  return (
    <LineChart width={800} height={400} data={mergedData}>
      <XAxis dataKey="date" />
      <YAxis
        label={{ value: '매매가 (억원)', angle: -90 }}
        tickFormatter={(v) => `${(v / 10000).toFixed(1)}`}
      />
      <Tooltip formatter={(v) => `${(v / 10000).toFixed(2)}억원`} />
      <Legend />

      {/* 대상 아파트 실거래가 - 파란 실선 */}
      <Line
        type="monotone"
        dataKey="targetPrice"
        name={`${targetName} 실거래가`}
        stroke="#2563eb"
        strokeWidth={2}
        dot={{ r: 3 }}
      />

      {/* 비교 아파트 실거래가 - 회색 점선 */}
      <Line
        type="monotone"
        dataKey="similarPrice"
        name={`${similarName} 실거래가`}
        stroke="#6b7280"
        strokeWidth={2}
        strokeDasharray="5 5"
        dot={{ r: 3 }}
      />

      {/* 현재 매물 호가 - 빨간 점 */}
      <ReferenceDot
        x={currentListingPrice.date}
        y={currentListingPrice.price}
        r={8}
        fill="#ef4444"
        stroke="#fff"
        strokeWidth={2}
        label={{ value: '매물호가', position: 'top' }}
      />
    </LineChart>
  );
}
```
