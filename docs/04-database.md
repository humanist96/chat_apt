# 4. 데이터베이스 설계

## 4.1 ERD

```
┌─────────────────────┐       ┌─────────────────────┐
│     apartments      │       │     transactions    │
├─────────────────────┤       ├─────────────────────┤
│ id (PK)             │       │ id (PK)             │
│ naver_complex_no    │◄──┐   │ apartment_id (FK)   │
│ name                │   │   │ deal_amount         │
│ address             │   │   │ deal_date           │
│ dong_code           │   │   │ floor               │
│ total_units         │   │   │ area                │
│ built_year          │   └───│ created_at          │
│ latitude            │       └─────────────────────┘
│ longitude           │
│ created_at          │       ┌─────────────────────┐
│ updated_at          │       │      listings       │
└─────────────────────┘       ├─────────────────────┤
          ▲                   │ id (PK)             │
          │                   │ apartment_id (FK)   │
          │                   │ article_no          │
          │                   │ trade_type          │
          │                   │ price               │
          │                   │ area                │
          └───────────────────│ floor               │
                              │ direction           │
                              │ description         │
                              │ realtor_name        │
                              │ realtor_phone       │
                              │ is_active           │
                              │ created_at          │
                              │ updated_at          │
                              └─────────────────────┘

┌─────────────────────┐       ┌─────────────────────┐
│  similar_apartments │       │ comparison_analysis │
├─────────────────────┤       ├─────────────────────┤
│ id (PK)             │       │ id (PK)             │
│ apartment_id (FK)   │       │ listing_id (FK)     │
│ similar_apt_id (FK) │       │ similar_apt_id (FK) │
│ similarity_score    │       │ target_price_pyeong │
│ location_score      │       │ similar_price_pyeong│
│ area_score          │       │ price_gap_percent   │
│ correlation_score   │       │ analyzed_at         │
│ scale_score         │       └─────────────────────┘
│ age_score           │
│ calculated_at       │
└─────────────────────┘
```

---

## 4.2 핵심 테이블 정의

### 아파트 마스터 테이블

```sql
CREATE TABLE apartments (
    id SERIAL PRIMARY KEY,
    naver_complex_no VARCHAR(20) UNIQUE,
    name VARCHAR(100) NOT NULL,
    address VARCHAR(200),
    dong_code VARCHAR(10),
    total_units INTEGER,
    built_year INTEGER,
    latitude DECIMAL(10, 7),
    longitude DECIMAL(10, 7),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스
CREATE INDEX idx_apartments_dong_code ON apartments(dong_code);
CREATE INDEX idx_apartments_name ON apartments(name);
```

### 실거래가 테이블

```sql
CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,
    apartment_id INTEGER REFERENCES apartments(id),
    deal_amount BIGINT NOT NULL,
    deal_date DATE NOT NULL,
    floor INTEGER,
    area DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(apartment_id, deal_date, floor, area, deal_amount)
);

-- 인덱스
CREATE INDEX idx_transactions_apartment_id ON transactions(apartment_id);
CREATE INDEX idx_transactions_deal_date ON transactions(deal_date DESC);
CREATE INDEX idx_transactions_area ON transactions(area);
```

### 매물 정보 테이블

```sql
CREATE TABLE listings (
    id SERIAL PRIMARY KEY,
    apartment_id INTEGER REFERENCES apartments(id),
    article_no VARCHAR(30) UNIQUE,
    trade_type VARCHAR(10),
    price BIGINT NOT NULL,
    area DECIMAL(10, 2),
    floor INTEGER,
    direction VARCHAR(20),
    description TEXT,
    realtor_name VARCHAR(50),
    realtor_phone VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스
CREATE INDEX idx_listings_apartment_id ON listings(apartment_id);
CREATE INDEX idx_listings_is_active ON listings(is_active);
CREATE INDEX idx_listings_price ON listings(price);
```

### 분석 결과 테이블

```sql
CREATE TABLE analysis_results (
    id SERIAL PRIMARY KEY,
    listing_id INTEGER REFERENCES listings(id),
    avg_transaction_price BIGINT,
    price_gap BIGINT,
    discount_rate DECIMAL(5, 2),
    recommendation_score DECIMAL(5, 2),
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_analysis_results_listing_id ON analysis_results(listing_id);
CREATE INDEX idx_analysis_results_score ON analysis_results(recommendation_score DESC);
```

---

## 4.3 유사 매물 분석 테이블

### 유사 아파트 매핑 테이블

```sql
CREATE TABLE similar_apartments (
    id SERIAL PRIMARY KEY,
    apartment_id INTEGER REFERENCES apartments(id),
    similar_apartment_id INTEGER REFERENCES apartments(id),
    similarity_score DECIMAL(5, 2),          -- 종합 유사도 점수
    location_score DECIMAL(5, 2),            -- 지역 근접성 점수
    area_score DECIMAL(5, 2),                -- 평형 유사성 점수
    correlation_score DECIMAL(5, 2),         -- 시세 상관관계 점수
    scale_score DECIMAL(5, 2),               -- 단지 규모 유사성 점수
    age_score DECIMAL(5, 2),                 -- 건축연도 유사성 점수
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(apartment_id, similar_apartment_id)
);

CREATE INDEX idx_similar_apartments_apartment_id ON similar_apartments(apartment_id);
CREATE INDEX idx_similar_apartments_score ON similar_apartments(similarity_score DESC);
```

### 유사 매물 비교 분석 결과 테이블

```sql
CREATE TABLE comparison_analysis (
    id SERIAL PRIMARY KEY,
    listing_id INTEGER REFERENCES listings(id),
    similar_apartment_id INTEGER REFERENCES apartments(id),
    target_price_per_pyeong BIGINT,          -- 대상 매물 평당가
    similar_price_per_pyeong BIGINT,         -- 비교 아파트 최근 평당가
    price_gap_percent DECIMAL(5, 2),         -- 가격 차이 (%)
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_comparison_analysis_listing ON comparison_analysis(listing_id);
```

### 월별 평균 시세 캐시 테이블

```sql
-- 상관관계 계산용 캐시
CREATE TABLE monthly_price_cache (
    id SERIAL PRIMARY KEY,
    apartment_id INTEGER REFERENCES apartments(id),
    area_pyeong DECIMAL(5, 1),               -- 평형대
    year_month VARCHAR(7),                   -- YYYY-MM
    avg_price BIGINT,                        -- 평균 거래가
    avg_price_per_pyeong BIGINT,             -- 평균 평당가
    transaction_count INTEGER,               -- 거래 건수
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(apartment_id, area_pyeong, year_month)
);

CREATE INDEX idx_monthly_price_cache_apartment ON monthly_price_cache(apartment_id, year_month);
```

---

## 4.4 사용자 관련 테이블

### 사용자 프로필 테이블

```sql
-- Supabase auth.users 확장
CREATE TABLE user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email VARCHAR(255),
    name VARCHAR(100),
    avatar_url TEXT,
    membership_tier VARCHAR(20) DEFAULT 'free',  -- free, basic, premium
    subscription_expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 사용자 관심 지역

```sql
CREATE TABLE user_favorite_regions (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES user_profiles(id) ON DELETE CASCADE,
    dong_code VARCHAR(10),
    region_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_user_favorite_regions_user_id ON user_favorite_regions(user_id);
```

### 사용자 관심 매물

```sql
CREATE TABLE user_favorite_listings (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES user_profiles(id) ON DELETE CASCADE,
    listing_id INTEGER REFERENCES listings(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, listing_id)
);

CREATE INDEX idx_user_favorite_listings_user_id ON user_favorite_listings(user_id);
```

### API 사용량 추적

```sql
CREATE TABLE user_api_usage (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES user_profiles(id),
    endpoint VARCHAR(100),
    request_count INTEGER DEFAULT 1,
    usage_date DATE DEFAULT CURRENT_DATE,
    UNIQUE(user_id, endpoint, usage_date)
);

CREATE INDEX idx_user_api_usage_user_date ON user_api_usage(user_id, usage_date);
```

---

## 4.5 결제 관련 테이블

### 구독 정보 테이블

```sql
CREATE TABLE subscriptions (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES user_profiles(id) ON DELETE CASCADE,
    plan VARCHAR(20) NOT NULL,              -- basic, premium
    status VARCHAR(20) DEFAULT 'active',    -- active, cancelled, expired
    billing_key VARCHAR(100),               -- 토스페이먼츠 빌링키
    current_period_start TIMESTAMP,
    current_period_end TIMESTAMP,
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX idx_subscriptions_status ON subscriptions(status);
```

### 결제 이력 테이블

```sql
CREATE TABLE payment_history (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES user_profiles(id),
    subscription_id INTEGER REFERENCES subscriptions(id),
    amount INTEGER NOT NULL,
    currency VARCHAR(3) DEFAULT 'KRW',
    status VARCHAR(20),                     -- success, failed, refunded
    payment_key VARCHAR(100),               -- 토스페이먼츠 결제키
    order_id VARCHAR(100),
    paid_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_payment_history_user_id ON payment_history(user_id);
CREATE INDEX idx_payment_history_subscription_id ON payment_history(subscription_id);
```

---

## 4.6 Row Level Security (RLS) 설정

```sql
-- RLS 활성화
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_favorite_regions ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_favorite_listings ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_history ENABLE ROW LEVEL SECURITY;

-- 사용자 본인 데이터만 접근 가능
CREATE POLICY "Users can view own profile"
    ON user_profiles FOR SELECT
    USING (auth.uid() = id);

CREATE POLICY "Users can update own profile"
    ON user_profiles FOR UPDATE
    USING (auth.uid() = id);

CREATE POLICY "Users can manage own favorites"
    ON user_favorite_listings FOR ALL
    USING (auth.uid() = user_id);

CREATE POLICY "Users can manage own regions"
    ON user_favorite_regions FOR ALL
    USING (auth.uid() = user_id);

CREATE POLICY "Users can view own subscriptions"
    ON subscriptions FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can view own payments"
    ON payment_history FOR SELECT
    USING (auth.uid() = user_id);
```
