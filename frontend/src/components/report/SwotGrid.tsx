'use client'

import type { Swot, SwotEntry } from '@/types'
import { ShieldCheck, ShieldAlert, TrendingUp, AlertTriangle } from 'lucide-react'

interface SwotGridProps {
  swot?: Swot
}

interface QuadrantConfig {
  key: keyof Swot
  label: string
  icon: React.ElementType
  bgClass: string
  titleClass: string
}

const QUADRANTS: QuadrantConfig[] = [
  {
    key: 'strengths',
    label: '优势',
    icon: ShieldCheck,
    bgClass: 'bg-[var(--tag-green)]',
    titleClass: 'text-[var(--tag-green-text)]',
  },
  {
    key: 'weaknesses',
    label: '劣势',
    icon: ShieldAlert,
    bgClass: 'bg-[var(--tag-red)]',
    titleClass: 'text-[var(--tag-red-text)]',
  },
  {
    key: 'opportunities',
    label: '机会',
    icon: TrendingUp,
    bgClass: 'bg-[var(--tag-blue)]',
    titleClass: 'text-[var(--tag-blue-text)]',
  },
  {
    key: 'threats',
    label: '威胁',
    icon: AlertTriangle,
    bgClass: 'bg-[var(--tag-orange)]',
    titleClass: 'text-[var(--tag-orange-text)]',
  },
]

function SwotQuadrant({ config, entries }: { config: QuadrantConfig; entries: SwotEntry[] }) {
  const Icon = config.icon

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--border-default)] bg-[var(--bg-surface)] overflow-hidden">
      <div className={`flex items-center gap-2 px-4 py-2.5 ${config.bgClass}`}>
        <Icon size={14} strokeWidth={1.5} className={config.titleClass} />
        <span className={`text-[13px] font-semibold ${config.titleClass}`}>
          {config.label}
        </span>
      </div>

      <div className="p-4">
        {entries.length === 0 ? (
          <p className="text-[13px] text-[var(--text-tertiary)] italic">暂无数据</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {entries.map((entry, i) => (
              <li key={i} className="flex flex-col gap-0.5">
                <span className="text-[13px] font-medium text-[var(--text-primary)] leading-snug">
                  {entry.point}
                </span>
                {entry.evidence && (
                  <span className="text-[12px] text-[var(--text-secondary)] leading-relaxed">
                    {entry.evidence}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

export function SwotGrid({ swot }: SwotGridProps) {
  if (!swot) return null

  return (
    <div className="flex flex-col gap-4">
      <h3 className="text-[15px] font-semibold text-[var(--text-primary)]">
        SWOT 分析
      </h3>

      <div className="grid grid-cols-2 gap-3">
        {QUADRANTS.map((config) => (
          <SwotQuadrant
            key={config.key}
            config={config}
            entries={swot[config.key] ?? []}
          />
        ))}
      </div>
    </div>
  )
}
