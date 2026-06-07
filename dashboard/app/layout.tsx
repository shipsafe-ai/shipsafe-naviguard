import type { Metadata } from 'next'
import { GeistSans } from 'geist/font/sans'
import './globals.css'

export const metadata: Metadata = {
  title: 'NaviGuard — AI Quality Monitor',
  description: 'Self-improving AI quality monitoring powered by Arize Phoenix',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={GeistSans.className}>
      <body className="min-h-screen bg-[#0A0A0B] text-zinc-50">
        <nav className="border-b border-[#27272A] bg-[#111113] px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-[#EC4899] font-mono text-sm font-medium tracking-widest uppercase">
              NaviGuard
            </span>
            <span className="text-[#52525B] text-xs font-mono">
              AI Quality Monitor
            </span>
          </div>
          <div className="flex items-center gap-4 text-xs font-mono text-[#52525B]">
            <span>Phoenix: naviguard</span>
            <span className="w-2 h-2 rounded-full bg-[#EC4899] animate-pulse" />
            <span>live</span>
          </div>
        </nav>
        <main className="mx-auto max-w-7xl px-6 py-8">
          {children}
        </main>
      </body>
    </html>
  )
}
