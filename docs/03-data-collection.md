# 3. 데이터 수집

## 3.1 네이버 부동산 호가 정보

### 수집 대상

| 항목 | 설명 |
|------|------|
| 매물 ID | 네이버 부동산 고유 식별자 |
| 아파트명 | 단지명 |
| 주소 | 시/구/동 + 상세주소 |
| 면적 | 전용면적 (m²) |
| 층수 | 해당 매물의 층 |
| 호가 | 매도 희망가격 |
| 매물 종류 | 매매/전세/월세 |
| 등록일 | 매물 등록 날짜 |
| 중개사 정보 | 중개사무소명, 연락처 |

### 수집 방법 (비공식 API)

```python
# 네이버 부동산 API 엔드포인트 (비공식)

# 1. 단지 목록 조회
GET https://new.land.naver.com/api/regions/complexes
    ?cortarNo={법정동코드}
    &realEstateType=APT
    &tradeType=A1  # A1: 매매, B1: 전세

# 2. 단지 상세 정보
GET https://new.land.naver.com/api/complexes/{complexNo}

# 3. 매물 목록
GET https://new.land.naver.com/api/articles/complex/{complexNo}
    ?tradeType=A1
    &realEstateType=APT
```

### 크롤링 시 고려사항

> **주의**: 네이버 부동산은 공식 API를 제공하지 않으므로 웹 크롤링이 필수이며,
> Abuse 탐지 시스템 회피를 위한 다양한 기술적 대응이 필요함

- **Rate Limiting**: 요청 간 적절한 딜레이 (2-5초)
- **User-Agent 설정**: 브라우저 User-Agent 사용
- **세션 관리**: 쿠키 및 헤더 관리
- **IP 차단 대비**: Proxy 로테이션 고려

---

## 3.2 크롤링 안정화 전략 (Anti-Abuse 회피)

네이버 부동산은 비정상적인 접근 패턴을 감지하여 차단하므로, 안정적인 데이터 수집을 위해 다음 전략을 적용해야 함.

### 3.2.1 요청 패턴 인간화

```python
import random
import time

class HumanizedRequester:
    """인간의 브라우징 패턴을 모방한 요청 클래스"""

    def __init__(self):
        self.session_start = time.time()
        self.request_count = 0

    def get_random_delay(self) -> float:
        """
        요청 간 랜덤 딜레이 생성
        - 기본: 3-7초 랜덤
        - 10회 요청마다: 15-30초 휴식
        - 50회 요청마다: 60-120초 장기 휴식
        """
        self.request_count += 1

        if self.request_count % 50 == 0:
            return random.uniform(60, 120)  # 장기 휴식
        elif self.request_count % 10 == 0:
            return random.uniform(15, 30)   # 중간 휴식
        else:
            # 정규분포 기반 자연스러운 딜레이
            delay = random.gauss(5, 1.5)
            return max(2, min(10, delay))

    def add_human_behavior(self):
        """마우스 움직임, 스크롤 등 인간 행동 시뮬레이션"""
        behaviors = [
            lambda: time.sleep(random.uniform(0.5, 1.5)),  # 페이지 읽는 시간
            lambda: random.choice([True, False]),          # 가끔 뒤로가기
        ]
        random.choice(behaviors)()
```

### 3.2.2 User-Agent 로테이션

```python
USER_AGENTS = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Chrome Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Firefox Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Safari Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    # Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]

class UserAgentRotator:
    def __init__(self):
        self.current_ua = random.choice(USER_AGENTS)
        self.usage_count = 0

    def get_user_agent(self) -> str:
        """20-50회 사용 후 User-Agent 변경"""
        self.usage_count += 1
        if self.usage_count > random.randint(20, 50):
            self.current_ua = random.choice(USER_AGENTS)
            self.usage_count = 0
        return self.current_ua
```

### 3.2.3 Proxy 풀 관리

```python
from dataclasses import dataclass
from typing import Optional
import asyncio

@dataclass
class ProxyInfo:
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    fail_count: int = 0
    last_used: float = 0
    is_blocked: bool = False

class ProxyPoolManager:
    """Proxy 풀 관리 및 로테이션"""

    def __init__(self, proxies: list[ProxyInfo]):
        self.proxies = proxies
        self.current_index = 0
        self.blocked_cooldown = 300  # 5분 쿨다운

    def get_next_proxy(self) -> Optional[ProxyInfo]:
        """
        다음 사용 가능한 Proxy 반환
        - 차단된 Proxy 제외
        - 라운드 로빈 방식
        """
        available = [p for p in self.proxies if not p.is_blocked]
        if not available:
            # 모든 Proxy 차단 시 쿨다운 후 복구
            self._recover_proxies()
            available = self.proxies

        proxy = available[self.current_index % len(available)]
        self.current_index += 1
        proxy.last_used = time.time()
        return proxy

    def mark_failed(self, proxy: ProxyInfo):
        """Proxy 실패 처리"""
        proxy.fail_count += 1
        if proxy.fail_count >= 3:
            proxy.is_blocked = True

    def _recover_proxies(self):
        """쿨다운 지난 Proxy 복구"""
        current_time = time.time()
        for proxy in self.proxies:
            if proxy.is_blocked and (current_time - proxy.last_used) > self.blocked_cooldown:
                proxy.is_blocked = False
                proxy.fail_count = 0
```

### 3.2.4 헤드리스 브라우저 (Playwright)

```python
from playwright.async_api import async_playwright

class StealthBrowser:
    """탐지 회피 기능이 적용된 브라우저"""

    async def create_context(self):
        playwright = await async_playwright().start()

        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )

        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=self.get_random_ua(),
            locale='ko-KR',
            timezone_id='Asia/Seoul',
        )

        # WebDriver 탐지 우회
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Chrome 속성 추가
            window.chrome = { runtime: {} };

            // Permissions 우회
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)

        return context
```

### 3.2.5 차단 감지 및 자동 복구

```python
class BlockDetector:
    """차단 상태 감지 및 자동 복구"""

    BLOCK_INDICATORS = [
        "비정상적인 접근",
        "자동화된 접근",
        "captcha",
        "차단",
        "blocked",
    ]

    def __init__(self):
        self.consecutive_failures = 0
        self.max_failures = 5

    def is_blocked(self, response) -> bool:
        """응답에서 차단 여부 확인"""
        # HTTP 상태 코드 확인
        if response.status_code in [403, 429, 503]:
            return True

        # 응답 본문에서 차단 키워드 확인
        content = response.text.lower()
        return any(indicator in content for indicator in self.BLOCK_INDICATORS)

    async def handle_block(self, proxy_manager: ProxyPoolManager):
        """차단 시 복구 절차"""
        self.consecutive_failures += 1

        if self.consecutive_failures >= self.max_failures:
            # 장기 대기 후 재시도
            wait_time = min(300, 60 * self.consecutive_failures)
            await asyncio.sleep(wait_time)
            self.consecutive_failures = 0

        # Proxy 교체
        return proxy_manager.get_next_proxy()
```

### 3.2.6 세션 및 쿠키 관리

```python
class SessionManager:
    """세션 상태 관리"""

    def __init__(self):
        self.cookies = {}
        self.session_created = time.time()
        self.max_session_age = 1800  # 30분

    def get_headers(self, user_agent: str) -> dict:
        """실제 브라우저와 유사한 헤더 구성"""
        return {
            'User-Agent': user_agent,
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://new.land.naver.com/',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        }

    def should_refresh_session(self) -> bool:
        """세션 갱신 필요 여부"""
        return (time.time() - self.session_created) > self.max_session_age
```

### 3.2.7 크롤링 전략 요약

| 전략 | 구현 방식 | 효과 |
|------|-----------|------|
| 요청 간격 랜덤화 | 정규분포 기반 3-7초 + 주기적 휴식 | 봇 패턴 탐지 회피 |
| User-Agent 로테이션 | 20-50회 요청마다 변경 | 단일 클라이언트 탐지 회피 |
| Proxy 풀 | 다중 IP 로테이션, 실패 시 자동 교체 | IP 기반 차단 회피 |
| 헤드리스 브라우저 | Playwright + WebDriver 탐지 우회 | JavaScript 기반 탐지 회피 |
| 세션 관리 | 실제 브라우저 헤더, 30분마다 세션 갱신 | 세션 기반 탐지 회피 |
| 차단 감지 | 응답 분석 + 자동 복구 | 차단 시 빠른 대응 |

---

## 3.3 공공데이터 실거래가 API

### API 정보

| 항목 | 내용 |
|------|------|
| 서비스명 | 국토교통부 아파트매매 실거래 상세 자료 |
| 제공기관 | 국토교통부 |
| 인증방식 | API Key (공공데이터포털 발급) |
| 호출제한 | 1,000회/일 (기본) |

### API 엔드포인트

```
GET http://openapi.molit.go.kr/OpenAPI_ToolInstall498/service/rest/RTMSOBJSvc/getRTMSDataSvcAptTradeDev

Parameters:
- serviceKey: 인증키
- LAWD_CD: 법정동코드 (5자리)
- DEAL_YMD: 계약년월 (YYYYMM)
- pageNo: 페이지 번호
- numOfRows: 한 페이지 결과 수
```

### 응답 데이터

```xml
<item>
    <거래금액>85,000</거래금액>
    <건축년도>2010</건축년도>
    <년>2024</년>
    <월>1</월>
    <일>15</일>
    <법정동>역삼동</법정동>
    <아파트>래미안역삼</아파트>
    <전용면적>84.99</전용면적>
    <층>12</층>
    <지번>123-45</지번>
</item>
```

### 추가 활용 API

| API명 | 용도 |
|-------|------|
| 아파트 전월세 실거래가 | 전세가 데이터 수집 |
| 공동주택 기본정보 | 아파트 기본 정보 (세대수, 동수 등) |
| 개별공시지가 | 토지 가치 참고 |

### API 클라이언트 구현

```python
import httpx
from typing import Optional
import xml.etree.ElementTree as ET

class PublicDataAPIClient:
    """공공데이터 API 클라이언트"""

    BASE_URL = "http://openapi.molit.go.kr/OpenAPI_ToolInstall498/service/rest/RTMSOBJSvc"

    def __init__(self, service_key: str):
        self.service_key = service_key
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get_apartment_trades(
        self,
        lawd_cd: str,
        deal_ymd: str,
        page_no: int = 1,
        num_of_rows: int = 100
    ) -> list[dict]:
        """
        아파트 실거래가 조회

        Args:
            lawd_cd: 법정동코드 (5자리)
            deal_ymd: 계약년월 (YYYYMM)
        """
        params = {
            'serviceKey': self.service_key,
            'LAWD_CD': lawd_cd,
            'DEAL_YMD': deal_ymd,
            'pageNo': page_no,
            'numOfRows': num_of_rows,
        }

        response = await self.client.get(
            f"{self.BASE_URL}/getRTMSDataSvcAptTradeDev",
            params=params
        )

        return self._parse_response(response.text)

    def _parse_response(self, xml_text: str) -> list[dict]:
        """XML 응답 파싱"""
        root = ET.fromstring(xml_text)
        items = root.findall('.//item')

        results = []
        for item in items:
            results.append({
                'deal_amount': int(item.findtext('거래금액', '0').replace(',', '')),
                'built_year': int(item.findtext('건축년도', '0')),
                'year': int(item.findtext('년', '0')),
                'month': int(item.findtext('월', '0')),
                'day': int(item.findtext('일', '0')),
                'dong': item.findtext('법정동', ''),
                'apartment_name': item.findtext('아파트', ''),
                'area': float(item.findtext('전용면적', '0')),
                'floor': int(item.findtext('층', '0')),
                'jibun': item.findtext('지번', ''),
            })

        return results
```
