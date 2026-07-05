'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Plus, List, Search } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useTraces } from '@/hooks/useTraces'
import { SCENARIO_LABELS } from '@/types'
import type { Scenario } from '@/types'

const NAV_ITEMS = [
  { href: '/', label: '新建分析', icon: Plus },
  { href: '/history', label: '历史记录', icon: List },
] as const

export function Sidebar() {
  const pathname = usePathname()
  const { traces } = useTraces(1, 10)

  return (
    <aside className="fixed left-0 top-0 bottom-0 w-[240px] bg-[var(--bg-page)] border-r border-[var(--border-default)] hidden lg:flex flex-col">
      {/* Logo */}
      <div className="h-14 flex items-center px-5 border-b border-[var(--border-divider)]">
        <span className="text-[15px] font-semibold tracking-tight text-[var(--text-primary)]">
          PentaScope
        </span>
      </div>

      {/* Navigation */}
      <nav className="px-2 py-3">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const isActive = href === '/' ? pathname === '/' : pathname.startsWith(href)
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'flex items-center gap-2.5 px-3 py-1.5 rounded-[var(--radius-md)] text-[14px] transition-colors',
                isActive
                  ? 'bg-[var(--bg-selected)] text-[var(--text-primary)] font-medium'
                  : 'text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]'
              )}
            >
              <Icon size={16} strokeWidth={1.5} />
              {label}
            </Link>
          )
        })}
      </nav>

      {/* Divider */}
      <div className="mx-3 border-t border-[var(--border-divider)]" />

      {/* Recent analyses */}
      <div className="flex-1 overflow-y-auto px-2 py-3">
        <div className="px-3 mb-2 text-[11px] font-medium uppercase tracking-wider text-[var(--text-tertiary)]">
          最近分析
        </div>
        {traces.length === 0 ? (
          <div className="px-3 py-4 text-[13px] text-[var(--text-tertiary)]">
            暂无分析记录
          </div>
        ) : (
          <div className="flex flex-col gap-0.5">
            {traces.map(trace => (
              <Link
                key={trace.trace_id}
                href={`/analyze/${trace.trace_id}`}
                className={cn(
                  'flex items-center gap-2 px-3 py-1.5 rounded-[var(--radius-md)] text-[13px] transition-colors truncate',
                  pathname === `/analyze/${trace.trace_id}`
                    ? 'bg-[var(--bg-selected)] text-[var(--text-primary)]'
                    : 'text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]'
                )}
                title={trace.competitors.join(', ') || trace.trace_id}
              >
                <Search size={14} strokeWidth={1.5} className="shrink-0 opacity-50" />
                <span className="truncate">
                  {trace.competitors.length > 0
                    ? trace.competitors.slice(0, 2).join(', ')
                    : trace.scenario
                      ? SCENARIO_LABELS[trace.scenario as Scenario] || trace.scenario
                      : trace.trace_id.slice(0, 8)}
                </span>
              </Link>
            ))}
          </div>
        )}
      </div>
    </aside>
  )
}
