import Link from 'next/link'

export function Footer() {
  return (
    <footer className="bg-gray-900 text-gray-300 py-12">
      <div className="container mx-auto px-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {/* Brand */}
          <div className="col-span-1 md:col-span-2">
            <div className="flex items-center space-x-2 mb-4">
              <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
                <span className="text-white font-bold text-sm">CA</span>
              </div>
              <span className="text-xl font-bold text-white">Chat APT</span>
            </div>
            <p className="text-sm text-gray-400 max-w-md">
              네이버 부동산 호가와 실거래가를 분석하여 저평가 매물을 찾아드립니다.
              데이터 기반의 스마트한 부동산 투자를 경험하세요.
            </p>
          </div>

          {/* Links */}
          <div>
            <h3 className="text-white font-semibold mb-4">서비스</h3>
            <ul className="space-y-2 text-sm">
              <li>
                <Link href="/search" className="hover:text-white transition">
                  매물 검색
                </Link>
              </li>
              <li>
                <Link href="/analysis" className="hover:text-white transition">
                  시세 분석
                </Link>
              </li>
              <li>
                <Link href="/pricing" className="hover:text-white transition">
                  요금제
                </Link>
              </li>
            </ul>
          </div>

          {/* Legal */}
          <div>
            <h3 className="text-white font-semibold mb-4">정보</h3>
            <ul className="space-y-2 text-sm">
              <li>
                <Link href="/terms" className="hover:text-white transition">
                  이용약관
                </Link>
              </li>
              <li>
                <Link href="/privacy" className="hover:text-white transition">
                  개인정보처리방침
                </Link>
              </li>
              <li>
                <Link href="/contact" className="hover:text-white transition">
                  문의하기
                </Link>
              </li>
            </ul>
          </div>
        </div>

        <div className="border-t border-gray-800 mt-8 pt-8 text-sm text-center text-gray-500">
          <p>&copy; {new Date().getFullYear()} Chat APT. All rights reserved.</p>
          <p className="mt-2">
            본 서비스에서 제공하는 정보는 참고용이며, 투자 결정은 본인의 판단에 따라 이루어져야 합니다.
          </p>
        </div>
      </div>
    </footer>
  )
}
