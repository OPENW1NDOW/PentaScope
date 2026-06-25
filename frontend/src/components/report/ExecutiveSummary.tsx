'use client'

import type { ExecutiveSummary as ExecutiveSummaryType } from '@/types'
import { Lightbulb } from 'lucide-react'

interface ExecutiveSummaryProps {
  summary?: ExecutiveSummaryType
}

function Paragraph({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)]">
        {label}
      </span>
      <div className="text-[14px] leading-relaxed text-[var(--text-primary)]">
        {children}
      </div>
    </div>
  )
}

export function ExecutiveSummary({ summary }: ExecutiveSummaryProps) {
  if (!summary) return null

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 flex flex-col gap-5">
      <h3 className="text-[15px] font-semibold text-[var(--text-primary)]">
        执行摘要
      </h3>

      {/* Context */}
      <Paragraph label="背景">{summary.context}</Paragraph>

      {/* Core Thesis — callout style */}
      {summary.core_thesis && (
        <div className="flex gap-3 rounded-[var(--radius-md)] bg-[var(--tag-blue)] p-4">
          <Lightbulb
            size={18}
            className="shrink-0 mt-0.5 text-[var(--tag-blue-text)]"
            strokeWidth={1.5}
          />
          <div className="flex flex-col gap-1">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--tag-blue-text)] opacity-70">
              核心论点
            </span>
            <span className="text-[14px] leading-relaxed text-[var(--tag-blue-text)]">
              {summary.core_thesis}
            </span>
          </div>
        </div>
      )}

      {/* Key Findings Brief */}
      {summary.key_findings_brief?.length > 0 && (
        <Paragraph label="关键发现">
          <ul className="flex flex-col gap-1 mt-1">
            {summary.key_findings_brief.map((item, i) => (
              <li key={i} className="flex items-start gap-2 text-[14px] leading-relaxed">
                <span className="text-[var(--text-tertiary)] shrink-0">-</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </Paragraph>
      )}

      {/* Implications */}
      <Paragraph label="影响">{summary.implications}</Paragraph>

      {/* Path Forward */}
      {summary.path_forward?.length > 0 && (
        <Paragraph label="下一步">
          <ul className="flex flex-col gap-1 mt-1">
            {summary.path_forward.map((item, i) => (
              <li key={i} className="flex items-start gap-2 text-[14px] leading-relaxed">
                <span className="text-[var(--text-tertiary)] shrink-0">{i + 1}.</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </Paragraph>
      )}
    </div>
  )
}
