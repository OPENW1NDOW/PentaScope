import type { Metadata } from 'next'
import { Sidebar } from '@/components/layout/Sidebar'
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
        <main className="ml-[240px] min-h-screen">
          <div className="mx-auto max-w-[1120px] px-8 py-10">
            {children}
          </div>
        </main>
      </body>
    </html>
  )
}
