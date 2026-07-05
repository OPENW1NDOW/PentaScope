import type { Metadata } from 'next'
import { Sidebar } from '@/components/layout/Sidebar'
import { MobileNav } from '@/components/layout/MobileNav'
import './globals.css'

export const metadata: Metadata = {
  title: 'PentaScope',
  description: 'AI-driven competitive analysis system',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="zh-CN" className="h-full antialiased">
      <body className="min-h-full">
        <Sidebar />
        <MobileNav />
        <main className="min-h-screen lg:ml-[240px]">
          <div className="mx-auto max-w-[1120px] px-4 py-6 sm:px-6 lg:px-8 lg:py-10">
            {children}
          </div>
        </main>
      </body>
    </html>
  )
}
