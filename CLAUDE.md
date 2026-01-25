# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Chat APT is a Korean real estate analytics SaaS that identifies undervalued properties by comparing Naver Real Estate listing prices against government public transaction data. The system uses web scraping, data analysis algorithms, and a subscription-based business model.

## Commands

### Backend (FastAPI)
```bash
cd backend
pip install -r requirements.txt          # Install dependencies
uvicorn app.main:app --reload             # Dev server at localhost:8000
pytest                                    # Run all tests
pytest tests/test_analysis.py             # Run single test file
pytest tests/test_analysis.py::test_fire_sale  # Run single test
pytest --cov=app                          # Run with coverage
ruff check app/                           # Lint
```

### Frontend (Next.js)
```bash
cd frontend
npm install                               # Install dependencies
npm run dev                               # Dev server at localhost:3000
npm run build                             # Production build
npm run lint                              # ESLint
npx tsc --noEmit                          # Type check
```

### Data Collection
```bash
cd backend
python -m app.scripts.collect_naver_listings    # Crawl Naver Real Estate
python -m app.scripts.collect_public_data       # Collect government transaction data
playwright install chromium                      # Install browser for crawler
```

## Architecture

### Data Flow
1. **Collection Layer**: Naver crawler (`crawler/naver.py`) + Public Data API → scrapes listing prices and transaction history
2. **Storage**: Supabase PostgreSQL with tables: apartments, listings, transactions, analysis_results, users, subscriptions
3. **Analysis Engine**: Fire sale detection (`analysis/fire_sale.py`), similar apartment matching (`analysis/similarity.py`), recommendation scoring
4. **API Layer**: FastAPI with 10+ route groups, JWT auth via Supabase, rate limiting via Redis
5. **Frontend**: Next.js 14 App Router, centralized API client (`lib/api.ts`)

### Key Directories
```
backend/app/
├── api/          # Route handlers (listings, analysis, auth, payments, etc.)
├── models/       # SQLAlchemy ORM models
├── crawler/      # Naver scraper + anti-abuse (stealth_browser.py, anti_abuse.py)
├── analysis/     # Fire sale, similarity, recommendation algorithms
├── services/     # Cache, notifications, payments, public data API
└── auth/         # JWT middleware, rate limiting

frontend/src/
├── app/          # Next.js pages (App Router)
├── components/   # UI components (layout, search, analysis, auth)
├── lib/          # API client, Supabase client
└── types/        # TypeScript interfaces
```

### Anti-Abuse Crawler
The Naver crawler uses stealth techniques in `crawler/stealth_browser.py`:
- Playwright with WebDriver detection bypass
- User-Agent rotation, proxy support
- Human-like delays (2-10s Gaussian distribution)
- Exponential backoff on blocks

### Database
- **Production**: Supabase PostgreSQL (async via asyncpg)
- **Testing**: SQLite (via aiosqlite)
- Async SQLAlchemy with `database.py` session management

### Authentication & Rate Limiting
- Supabase Auth (Google, Kakao, Naver OAuth + email/password)
- JWT validation in `auth/middleware.py`
- Rate limits by subscription tier (Free: 10/day, Basic: 100/day, Premium: unlimited)
- Redis backend via Upstash REST API

## Environment Variables

Backend requires (see `backend/.env.example`):
- `DATABASE_URL`: PostgreSQL connection string
- `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`: Supabase credentials
- `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`: Redis for rate limiting
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`: Alert notifications
- `TOSS_CLIENT_KEY`, `TOSS_SECRET_KEY`: Payment processing
- `PUBLIC_DATA_API_KEY`: Korean government API

## CI/CD

GitHub Actions workflows:
- `ci.yml`: Backend tests (pytest, ruff), frontend build (tsc, next build), Trivy security scan
- `crawl.yml`: Scheduled daily crawl at 6 AM KST, runs collectors, sends Telegram notifications
