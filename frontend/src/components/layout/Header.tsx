'use client'

import Link from 'next/link'
import { useState } from 'react'
import { Menu, X, User, LogIn } from 'lucide-react'

export function Header() {
  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const [isLoggedIn, setIsLoggedIn] = useState(false)

  return (
    <header className="bg-white shadow-sm border-b">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link href="/" className="flex items-center space-x-2">
            <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">CA</span>
            </div>
            <span className="text-xl font-bold text-gray-900">Chat APT</span>
          </Link>

          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center space-x-8">
            <Link href="/" className="text-gray-600 hover:text-primary-600 transition">
              홈
            </Link>
            <Link href="/search" className="text-gray-600 hover:text-primary-600 transition">
              매물 검색
            </Link>
            <Link href="/analysis" className="text-gray-600 hover:text-primary-600 transition">
              시세 분석
            </Link>
            <Link href="/pricing" className="text-gray-600 hover:text-primary-600 transition">
              요금제
            </Link>
          </nav>

          {/* Auth Buttons */}
          <div className="hidden md:flex items-center space-x-4">
            {isLoggedIn ? (
              <Link
                href="/mypage"
                className="flex items-center space-x-2 text-gray-600 hover:text-primary-600"
              >
                <User className="w-5 h-5" />
                <span>마이페이지</span>
              </Link>
            ) : (
              <>
                <Link
                  href="/login"
                  className="text-gray-600 hover:text-primary-600 transition"
                >
                  로그인
                </Link>
                <Link
                  href="/signup"
                  className="bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 transition"
                >
                  무료 시작하기
                </Link>
              </>
            )}
          </div>

          {/* Mobile Menu Button */}
          <button
            className="md:hidden p-2"
            onClick={() => setIsMenuOpen(!isMenuOpen)}
          >
            {isMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>

        {/* Mobile Menu */}
        {isMenuOpen && (
          <div className="md:hidden py-4 border-t">
            <nav className="flex flex-col space-y-4">
              <Link href="/" className="text-gray-600 hover:text-primary-600">
                홈
              </Link>
              <Link href="/search" className="text-gray-600 hover:text-primary-600">
                매물 검색
              </Link>
              <Link href="/analysis" className="text-gray-600 hover:text-primary-600">
                시세 분석
              </Link>
              <Link href="/pricing" className="text-gray-600 hover:text-primary-600">
                요금제
              </Link>
              <hr />
              <Link href="/login" className="text-gray-600 hover:text-primary-600">
                로그인
              </Link>
              <Link
                href="/signup"
                className="bg-primary-600 text-white px-4 py-2 rounded-lg text-center"
              >
                무료 시작하기
              </Link>
            </nav>
          </div>
        )}
      </div>
    </header>
  )
}
