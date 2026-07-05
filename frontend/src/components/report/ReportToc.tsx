'use client'

import { useEffect, useState, type ReactNode } from 'react'

export interface TocItem {
  id: string
  label: string
}

interface ReportTocProps {
  items: TocItem[]
}

/** 报告页左侧 sticky 目录（≥1280px 显示） */
export function ReportToc({ items }: ReportTocProps) {
  const [activeId, setActiveId] = useState<string>(items[0]?.id ?? '')

  useEffect(() => {
    if (items.length === 0) return

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
        if (visible.length > 0) {
          setActiveId(visible[0].target.id)
        }
      },
      { rootMargin: '-20% 0px -60% 0px', threshold: 0 },
    )

    for (const item of items) {
      const el = document.getElementById(item.id)
      if (el) observer.observe(el)
    }
    return () => observer.disconnect()
  }, [items])

  if (items.length === 0) return null

  return (
    <nav
      aria-label="报告目录"
      className="hidden xl:block w-[180px] shrink-0 sticky top-8 self-start max-h-[calc(100vh-4rem)] overflow-y-auto"
    >
      <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-tertiary)] mb-3 px-2">
        目录
      </p>
      <ul className="flex flex-col gap-0.5">
        {items.map((item) => (
          <li key={item.id}>
            <a
              href={`#${item.id}`}
              onClick={(e) => {
                e.preventDefault()
                document.getElementById(item.id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
                setActiveId(item.id)
              }}
              className={`block px-2 py-1 text-[12px] rounded-[var(--radius-sm)] transition-colors truncate ${
                activeId === item.id
                  ? 'bg-[var(--bg-selected)] text-[var(--text-primary)] font-medium'
                  : 'text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]'
              }`}
            >
              {item.label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  )
}

/** 根据报告内容动态组装目录项 */
export function buildReportToc(report: {
  background?: string
  analysis_sections?: unknown[]
  conclusions?: string
  appendix?: unknown
}): TocItem[] {
  const items: TocItem[] = [
    { id: 'report-header', label: '报告标题' },
    { id: 'kpi', label: '关键指标' },
    { id: 'at-a-glance', label: '核心要点' },
    { id: 'executive-summary', label: '执行摘要' },
  ]
  if (report.background) items.push({ id: 'background', label: '背景' })
  items.push(
    { id: 'scope', label: '范围与方法论' },
    { id: 'key-findings', label: '关键发现' },
  )
  if (report.analysis_sections && report.analysis_sections.length > 0) {
    items.push({ id: 'analysis', label: '详细分析' })
  }
  items.push(
    { id: 'scenario', label: '场景专有分析' },
    { id: 'swot', label: 'SWOT' },
  )
  if (report.conclusions) items.push({ id: 'conclusions', label: '结论' })
  items.push(
    { id: 'recommendations', label: '行动建议' },
  )
  if (report.appendix) items.push({ id: 'appendix', label: '附录' })
  items.push(
    { id: 'metadata', label: '元数据' },
    { id: 'trace', label: '执行追溯' },
  )
  return items
}

function SectionWrap({ id, children }: { id: string; children: ReactNode }) {
  return (
    <div id={id} className="scroll-mt-8">
      {children}
    </div>
  )
}

export { SectionWrap }
