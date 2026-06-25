'use client'

import { CheckCircle2 } from 'lucide-react'

interface AtAGlanceProps {
  items?: string[]
}

export function AtAGlance({ items }: AtAGlanceProps) {
  if (!items || items.length === 0) return null

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--border-default)] bg-[var(--bg-surface)] p-5">
      <h3 className="text-[13px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)] mb-3">
        核心要点
      </h3>
      <ul className="flex flex-col gap-2">
        {items.map((item, i) => (
          <li key={i} className="flex items-start gap-2.5 text-[14px] text-[var(--text-primary)] leading-relaxed">
            <CheckCircle2
              size={16}
              className="shrink-0 mt-[3px] text-[var(--success)]"
              strokeWidth={1.5}
            />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
