# 7. 인증/인가 시스템

> 유료 서비스 제공을 위한 로그인 기반 사용자 관리 시스템

## 7.1 인증 방식

### Supabase Auth 활용

```typescript
// lib/supabase.ts
import { createClient } from '@supabase/supabase-js';

export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

// 지원 OAuth Provider
const providers = ['google', 'kakao', 'naver'];

// 로그인 함수
export async function signInWithOAuth(provider: 'google' | 'kakao' | 'naver') {
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider,
    options: {
      redirectTo: `${window.location.origin}/auth/callback`,
    },
  });
  return { data, error };
}

// 로그아웃
export async function signOut() {
  const { error } = await supabase.auth.signOut();
  return { error };
}

// 현재 사용자 조회
export async function getCurrentUser() {
  const { data: { user } } = await supabase.auth.getUser();
  return user;
}
```

### 지원 로그인 방식

| 방식 | 용도 | 비고 |
|------|------|------|
| Google OAuth | 주요 로그인 | 글로벌 사용자 |
| Kakao OAuth | 국내 사용자 | 카카오톡 연동 |
| Naver OAuth | 국내 사용자 | 네이버 연동 |
| Email/Password | 대체 수단 | 소셜 로그인 불가 시 |

---

## 7.2 OAuth 설정

### Supabase 설정

```
Supabase Dashboard > Authentication > Providers

1. Google
   - Client ID: [Google Cloud Console에서 발급]
   - Client Secret: [Google Cloud Console에서 발급]

2. Kakao
   - REST API Key: [Kakao Developers에서 발급]
   - Client Secret: [선택사항]

3. Naver
   - Client ID: [Naver Developers에서 발급]
   - Client Secret: [Naver Developers에서 발급]
```

### Redirect URL 설정

```
https://[project-ref].supabase.co/auth/v1/callback
```

---

## 7.3 회원 등급 및 기능 제한

| 기능 | Free | Basic (₩9,900/월) | Premium (₩19,900/월) |
|------|------|-------------------|---------------------|
| 실거래가 조회 | ✅ 무제한 | ✅ 무제한 | ✅ 무제한 |
| 매물 호가 조회 | ✅ 10건/일 | ✅ 100건/일 | ✅ 무제한 |
| 유사 매물 비교 분석 | ❌ | ✅ 10건/일 | ✅ 무제한 |
| 저평가 리포트 | ❌ | ✅ 5건/일 | ✅ 무제한 |
| 가격 알림 | ❌ | ✅ 3개 지역 | ✅ 10개 지역 |
| 관심 매물 저장 | ✅ 5개 | ✅ 50개 | ✅ 무제한 |
| API 접근 | ❌ | ❌ | ✅ |
| 광고 | 있음 | 없음 | 없음 |

---

## 7.4 Rate Limiting 구현

```python
from upstash_redis import Redis
from datetime import datetime

redis = Redis.from_env()

class RateLimiter:
    """사용자 등급별 API 호출 제한"""

    LIMITS = {
        'free': {'listings': 10, 'analysis': 0, 'report': 0},
        'basic': {'listings': 100, 'analysis': 10, 'report': 5},
        'premium': {'listings': -1, 'analysis': -1, 'report': -1},  # -1 = 무제한
    }

    async def check_limit(
        self,
        user_id: str,
        tier: str,
        endpoint: str
    ) -> tuple[bool, int]:
        """
        API 호출 가능 여부 확인

        Returns:
            (허용 여부, 남은 횟수)
        """
        limit = self.LIMITS.get(tier, {}).get(endpoint, 0)

        if limit == -1:  # 무제한
            return True, -1

        key = f"rate:{user_id}:{endpoint}:{datetime.now().strftime('%Y-%m-%d')}"
        current = await redis.get(key) or 0
        current = int(current)

        if current >= limit:
            return False, 0

        await redis.incr(key)
        await redis.expire(key, 86400)  # 24시간 후 만료

        return True, limit - current - 1


# FastAPI 미들웨어
from fastapi import Request, HTTPException

async def rate_limit_middleware(request: Request, call_next):
    user = request.state.user
    if not user:
        return await call_next(request)

    limiter = RateLimiter()
    endpoint = request.url.path.split('/')[-1]

    allowed, remaining = await limiter.check_limit(
        user.id,
        user.membership_tier,
        endpoint
    )

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="일일 사용량을 초과했습니다. 업그레이드를 고려해주세요."
        )

    response = await call_next(request)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    return response
```

---

## 7.5 JWT 검증 미들웨어

```python
from fastapi import Request, HTTPException
from supabase import create_client
import jwt

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

async def auth_middleware(request: Request, call_next):
    """JWT 토큰 검증"""
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        request.state.user = None
        return await call_next(request)

    token = auth_header.split(" ")[1]

    try:
        # Supabase JWT 검증
        user = supabase.auth.get_user(token)
        request.state.user = user.user
    except Exception:
        request.state.user = None

    return await call_next(request)


# 인증 필수 데코레이터
from functools import wraps

def require_auth(func):
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        if not request.state.user:
            raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
        return await func(request, *args, **kwargs)
    return wrapper


def require_tier(min_tier: str):
    """최소 회원 등급 요구"""
    tiers = {'free': 0, 'basic': 1, 'premium': 2}

    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            user = request.state.user
            if not user:
                raise HTTPException(status_code=401, detail="로그인이 필요합니다.")

            user_tier = user.user_metadata.get('membership_tier', 'free')
            if tiers.get(user_tier, 0) < tiers.get(min_tier, 0):
                raise HTTPException(
                    status_code=403,
                    detail=f"{min_tier} 이상 등급에서 사용 가능합니다."
                )

            return await func(request, *args, **kwargs)
        return wrapper
    return decorator
```

---

## 7.6 프론트엔드 인증 컴포넌트

### 로그인 페이지

```typescript
// app/(auth)/login/page.tsx
'use client';

import { signInWithOAuth } from '@/lib/supabase';

export default function LoginPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen">
      <h1 className="text-2xl font-bold mb-8">로그인</h1>

      <div className="flex flex-col gap-4 w-80">
        <button
          onClick={() => signInWithOAuth('google')}
          className="flex items-center justify-center gap-2 p-3 border rounded-lg hover:bg-gray-50"
        >
          <GoogleIcon />
          Google로 계속하기
        </button>

        <button
          onClick={() => signInWithOAuth('kakao')}
          className="flex items-center justify-center gap-2 p-3 bg-yellow-400 rounded-lg hover:bg-yellow-500"
        >
          <KakaoIcon />
          카카오로 계속하기
        </button>

        <button
          onClick={() => signInWithOAuth('naver')}
          className="flex items-center justify-center gap-2 p-3 bg-green-500 text-white rounded-lg hover:bg-green-600"
        >
          <NaverIcon />
          네이버로 계속하기
        </button>
      </div>
    </div>
  );
}
```

### Auth Callback 처리

```typescript
// app/(auth)/callback/route.ts
import { createRouteHandlerClient } from '@supabase/auth-helpers-nextjs';
import { cookies } from 'next/headers';
import { NextResponse } from 'next/server';

export async function GET(request: Request) {
  const requestUrl = new URL(request.url);
  const code = requestUrl.searchParams.get('code');

  if (code) {
    const supabase = createRouteHandlerClient({ cookies });
    await supabase.auth.exchangeCodeForSession(code);
  }

  return NextResponse.redirect(new URL('/dashboard', request.url));
}
```

### 인증 상태 Provider

```typescript
// providers/AuthProvider.tsx
'use client';

import { createContext, useContext, useEffect, useState } from 'react';
import { supabase } from '@/lib/supabase';
import type { User } from '@supabase/supabase-js';

const AuthContext = createContext<{
  user: User | null;
  loading: boolean;
}>({
  user: null,
  loading: true,
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // 초기 세션 확인
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null);
      setLoading(false);
    });

    // 인증 상태 변경 리스너
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_, session) => {
        setUser(session?.user ?? null);
      }
    );

    return () => subscription.unsubscribe();
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
```
