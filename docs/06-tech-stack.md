# 6. 기술 스택 및 인프라

## 6.1 Backend

| 구분 | 기술 | 선정 이유 |
|------|------|-----------|
| Language | Python 3.11+ | 데이터 처리 및 크롤링에 최적 |
| Framework | FastAPI | 비동기 처리, 자동 문서화 |
| ORM | SQLAlchemy | 유연한 쿼리 빌더 |
| Task Queue | Celery + Redis | 주기적 크롤링 작업 |
| Crawler | httpx + BeautifulSoup | 비동기 HTTP 클라이언트 |
| Browser Automation | Playwright | 헤드리스 브라우저, WebDriver 탐지 우회 |
| Data Analysis | NumPy, SciPy | 상관관계 분석, 통계 계산 |
| Proxy Management | 자체 구현 | Proxy 풀 관리, 로테이션 |

## 6.2 Database

| 구분 | 기술 | 선정 이유 |
|------|------|-----------|
| Main DB | PostgreSQL (Supabase) | 안정성, 복잡한 쿼리 지원, RLS |
| Cache | Redis (Upstash) | 빠른 조회, 세션 관리, Rate Limiting |

## 6.3 Frontend

| 구분 | 기술 | 선정 이유 |
|------|------|-----------|
| Framework | Next.js 14 (App Router) | SSR/SSG, Edge Functions |
| State | Zustand / TanStack Query | 간결한 상태 관리 |
| UI | Tailwind CSS + shadcn/ui | 빠른 스타일링, 일관된 디자인 |
| Chart | Recharts | 가격 추이 시각화 |
| Map | react-kakao-maps | 지도 기반 매물 표시 |

---

## 6.4 서버리스 인프라 (무료 티어 활용)

> 초기 비용을 최소화하고 확장성을 확보하기 위해 무료 서버리스 환경 최대 활용

| 구분 | 서비스 | 무료 티어 | 용도 |
|------|--------|-----------|------|
| Frontend | Vercel | 100GB 대역폭/월 | Next.js 호스팅, Edge Functions |
| Backend | Railway | $5 크레딧/월 | FastAPI 서버 |
| Database | Supabase | 500MB DB, 1GB Storage | PostgreSQL + Auth |
| Cache | Upstash Redis | 10,000 요청/일 | 세션, 캐싱 |
| Cron Jobs | GitHub Actions | 2,000분/월 | 크롤링 스케줄러 |
| File Storage | Cloudflare R2 | 10GB 저장, 무료 egress | 정적 파일 |
| CDN | Cloudflare | 무제한 | 전역 캐싱 |
| Monitoring | Grafana Cloud | 10K metrics | 모니터링 |

---

## 6.5 비용 예상 (월간)

| 단계 | 예상 사용량 | 비용 |
|------|-------------|------|
| MVP (100명 미만) | 무료 티어 내 | **$0** |
| 성장기 (1,000명) | Supabase Pro + Railway | **~$25** |
| 확장기 (10,000명) | 전체 유료 전환 | **~$100** |

### 상세 비용 분석

#### MVP 단계 ($0/월)
```
Vercel Free      : $0 (100GB 대역폭)
Supabase Free    : $0 (500MB DB)
Railway Free     : $5 크레딧 내
Upstash Free     : $0 (10K 요청/일)
GitHub Actions   : $0 (2,000분/월)
Cloudflare       : $0 (무제한)
──────────────────────────────
Total            : $0
```

#### 성장기 (~$25/월)
```
Vercel Pro       : $0 (개인 무료)
Supabase Pro     : $25 (8GB DB)
Railway          : $0 (크레딧 내)
Upstash Pay-go   : ~$3
──────────────────────────────
Total            : ~$28
```

---

## 6.6 개발 환경 설정

### Backend 설정

```bash
# Python 가상환경
python -m venv venv
source venv/bin/activate

# 의존성 설치
pip install fastapi uvicorn sqlalchemy asyncpg
pip install httpx beautifulsoup4 playwright
pip install celery redis
pip install numpy scipy

# Playwright 브라우저 설치
playwright install chromium
```

### Frontend 설정

```bash
# Next.js 프로젝트 생성
npx create-next-app@latest frontend --typescript --tailwind --app

# 추가 의존성
cd frontend
npm install @supabase/supabase-js
npm install zustand @tanstack/react-query
npm install recharts
npm install react-kakao-maps-sdk
```

### 환경 변수 설정

```env
# .env.local (Frontend)
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key
NEXT_PUBLIC_API_URL=your_backend_url

# .env (Backend)
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_KEY=your_service_key
PUBLIC_DATA_API_KEY=your_api_key
TOSS_SECRET_KEY=your_toss_key
```

---

## 6.7 CI/CD 파이프라인

### GitHub Actions 워크플로우

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Deploy to Railway
        uses: bervProject/railway-deploy@main
        with:
          railway_token: ${{ secrets.RAILWAY_TOKEN }}
          service: backend

  deploy-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Deploy to Vercel
        uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
          vercel-args: '--prod'
```

### 크롤링 스케줄러

```yaml
# .github/workflows/crawler.yml
name: Crawler

on:
  schedule:
    - cron: '0 */6 * * *'  # 6시간마다 실행
  workflow_dispatch:

jobs:
  crawl:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger Crawler
        run: |
          curl -X POST ${{ secrets.BACKEND_URL }}/api/crawler/trigger \
            -H "Authorization: Bearer ${{ secrets.CRAWLER_TOKEN }}"
```
