'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Plus, List } from 'lucide-react'
import { cn } from '@/lib/utils'

const NAV = [
  { href: '/', label: '新建', icon: Plus },
  { href: '/history', label: '历史', icon: List },
] as const

/** 小屏顶栏导航（侧栏 lg 以下隐藏时的兜底） */
export function MobileNav() {
  const pathname = usePathname()

  return (
    <header className="lg:hidden sticky top-0 z-40 flex items-center justify-between px-4 h-12 border-b border-[var(--border-default)] bg-[var(--bg-page)]">
      <span className="text-[14px] font-semibold text-[var(--text-primary)]">PentaScope</span>
      <nav className="flex items-center gap-1">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = href === '/' ? pathname === '/' : pathname.startsWith(href)
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'inline-flex items-center gap-1 px-2.5 py-1 rounded-[var(--radius-md)] text-[13px] transition-colors',
                active
                  ? 'bg-[var(--bg-selected)] text-[var(--text-primary)] font-medium'
                  : 'text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]',
              )}
            >
              <Icon size={14} strokeWidth={1.5} />
              {label}
            </Link>
          )
        })}
      </nav>
    </header>
  )
}
