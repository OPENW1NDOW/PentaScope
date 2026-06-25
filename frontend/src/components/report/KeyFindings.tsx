'use client'

import type { Finding } from '@/types'
import { SourceRefs } from './SourceRefs'

interface KeyFindingsProps {
  findings?: Finding[]
}

export function KeyFindings({ findings }: KeyFindingsProps) {
  if (!findings || findings.length === 0) return null

  return (
    <div className="flex flex-col gap-4">
      <h3 className="text-[15px] font-semibold text-[var(--text-primary)]">
        关键发现
      </h3>

      <div className="flex flex-col gap-3">
        {findings.map((finding, i) => (
          <div
            key={i}
            className="group rounded-[var(--radius-lg)] border border-[var(--border-default)] bg-[var(--bg-surface)] overflow-hidden transition-colors hover:border-[var(--border-active)]"
            style={{ borderLeftWidth: '3px', borderLeftColor: 'var(--border-default)' }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLElement).style.borderLeftColor = 'var(--border-active)'
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLElement).style.borderLeftColor = 'var(--border-default)'
            }}
          >
            <div className="p-4 flex flex-col gap-2.5">
              <h4 className="text-[14px] font-semibold text-[var(--text-primary)] leading-snug">
                {finding.statement}
              </h4>

              {finding.evidence && (
                <p className="text-[13px] leading-relaxed text-[var(--text-secondary)]">
                  {finding.evidence}
                </p>
              )}

              {finding.implication && (
                <p className="text-[13px] leading-relaxed text-[var(--text-secondary)] italic">
                  {finding.implication}
                </p>
              )}

              {finding.source_refs && finding.source_refs.length > 0 && (
                <div className="pt-1 border-t border-[var(--border-divider)]">
                  <SourceRefs refs={finding.source_refs} />
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
