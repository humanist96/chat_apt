import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

// Paths that require authentication
const PROTECTED_PATHS = [
  '/dashboard',
  '/mypage',
  '/analysis',
  '/favorites',
  '/subscription',
]

// Paths that should redirect to dashboard if already authenticated
const AUTH_PATHS = ['/login', '/signup']

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Check for Supabase auth cookie (sb-access-token or sb-*-auth-token)
  const hasAuthCookie = request.cookies.getAll().some(
    (cookie) =>
      cookie.name.includes('sb-') &&
      (cookie.name.includes('access-token') || cookie.name.includes('auth-token'))
  )

  // Check if the path requires authentication
  const isProtectedPath = PROTECTED_PATHS.some((path) =>
    pathname.startsWith(path)
  )

  // Check if the path is an auth page (login/signup)
  const isAuthPath = AUTH_PATHS.some((path) => pathname.startsWith(path))

  // Redirect unauthenticated users from protected paths to login
  if (isProtectedPath && !hasAuthCookie) {
    const loginUrl = new URL('/login', request.url)
    loginUrl.searchParams.set('redirect', pathname)
    return NextResponse.redirect(loginUrl)
  }

  // Redirect authenticated users from auth pages to dashboard
  if (isAuthPath && hasAuthCookie) {
    return NextResponse.redirect(new URL('/dashboard', request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public files (public folder)
     * - API routes
     */
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$|api).*)',
  ],
}
