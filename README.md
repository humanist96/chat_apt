# 아파트 최저가 매물 추천 시스템

네이버 부동산 호가 정보와 공공데이터 실거래가를 수집하여, 시세 대비 저평가된 최저가 매물을 자동으로 추천하는 시스템

## 핵심 기능

- **호가/실거래가 비교**: 네이버 부동산 매물 호가와 실거래가 비교 분석
- **유사 매물 비교**: 동일 평형대 인근 아파트와의 시세 흐름 비교
- **저평가 매물 추천**: 데이터 기반 최저가 매물 자동 추천
- **가격 알림**: 관심 지역/매물 가격 변동 알림

## 기술 스택

| 분류 | 기술 |
|------|------|
| Frontend | Next.js, Tailwind CSS, Recharts |
| Backend | FastAPI, Celery |
| Database | Supabase (PostgreSQL), Upstash Redis |
| Infra | Vercel, Railway, GitHub Actions |
| Crawler | Playwright, httpx |

## 문서 구조

```
docs/
├── 01-overview.md          # 프로젝트 개요
├── 02-architecture.md      # 시스템 아키텍처
├── 03-data-collection.md   # 데이터 수집 (크롤링/API)
├── 04-database.md          # 데이터베이스 설계
├── 05-analysis.md          # 분석 엔진 (유사매물/추천)
├── 06-tech-stack.md        # 기술 스택 및 인프라
├── 07-auth.md              # 인증/인가 시스템
├── 08-payment.md           # 비즈니스 모델 및 결제
├── 09-development-phases.md # 개발 단계
└── 10-legal-risk.md        # 법적 고려사항 및 리스크
```

## 빠른 시작

```bash
# 프론트엔드
cd frontend && npm install && npm run dev

# 백엔드
cd backend && pip install -r requirements.txt && uvicorn main:app --reload
```

## 서비스 요금

| 플랜 | 가격 | 주요 기능 |
|------|------|-----------|
| Free | ₩0 | 실거래가 조회, 매물 10건/일 |
| Basic | ₩9,900/월 | 유사 매물 분석, 알림 |
| Premium | ₩19,900/월 | 무제한 + API |

## 참고 자료

- [공공데이터포털 - 실거래가 API](https://www.data.go.kr/)
- [네이버 부동산](https://new.land.naver.com/)
- [알리알리](https://aliali.co.kr/home) - UI/UX 벤치마킹

## 라이선스

이 프로젝트는 개인 학습/연구 목적으로 제작되었습니다.
상업적 이용 시 법률 자문을 권장합니다.
