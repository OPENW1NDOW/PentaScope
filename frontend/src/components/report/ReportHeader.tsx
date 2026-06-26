'use client'

import type { ReportMetadata } from '@/types'
import { SCENARIO_LABELS } from '@/types'
import type { Scenario } from '@/types'
import { Download } from 'lucide-react'

interface ReportHeaderProps {
  title?: string
  subtitle?: string | null
  metadata?: ReportMetadata
  exportUrls?: {
    md: string
    html: string
  }
}

export function ReportHeader({ title, subtitle, metadata, exportUrls }: ReportHeaderProps) {
  const scenarioLabel = metadata?.scenario
    ? SCENARIO_LABELS[metadata.scenario as Scenario] ?? metadata.scenario
    : null

  return (
    <div className="flex items-start justify-between gap-4">
      <div className="flex flex-col gap-2">
        {title && (
          <h1 className="text-[24px] font-bold text-[var(--text-primary)] leading-tight">
            {title}
          </h1>
        )}
        {subtitle && (
          <p className="text-[15px] text-[var(--text-secondary)] leading-relaxed">
            {subtitle}
          </p>
        )}
        <div className="flex items-center gap-3 text-[12px] text-[var(--text-tertiary)]">
          {scenarioLabel && <span>{scenarioLabel}</span>}
          {metadata?.trace_id && (
            <span className="font-[var(--font-mono)] text-[11px]">
              trace: {metadata.trace_id}
            </span>
          )}
        </div>
      </div>

      {/* Export buttons */}
      {exportUrls && (
        <div className="flex items-center gap-2 shrink-0">
          <a
            href={exportUrls.md}
            download
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[13px] font-medium text-[var(--text-secondary)] border border-[var(--border-default)] rounded-[var(--radius-md)] hover:bg-[var(--bg-hover)] transition-colors"
          >
            <Download size={14} strokeWidth={1.5} />
            MD
          </a>
          <a
            href={exportUrls.html}
            download
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[13px] font-medium text-[var(--text-secondary)] border border-[var(--border-default)] rounded-[var(--radius-md)] hover:bg-[var(--bg-hover)] transition-colors"
          >
            <Download size={14} strokeWidth={1.5} />
            HTML
          </a>
        </div>
      )}
    </div>
  )
}
