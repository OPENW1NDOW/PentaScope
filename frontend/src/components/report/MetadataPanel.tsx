'use client'

import type { ReportMetadata, CriticScores } from '@/types'
import { SCENARIO_LABELS } from '@/types'
import type { Scenario } from '@/types'
import { ChevronRight, AlertTriangle, Shield } from 'lucide-react'

interface MetadataPanelProps {
  metadata: ReportMetadata
}

const CRITIC_DIMENSIONS: { key: keyof CriticScores; label: string; color: string }[] = [
  { key: 'evidence', label: 'Evidence', color: 'var(--chart-1)' },
  { key: 'specificity', label: 'Specificity', color: 'var(--chart-2)' },
  { key: 'coherence', label: 'Coherence', color: 'var(--chart-3)' },
  { key: 'actionability', label: 'Actionability', color: 'var(--chart-4)' },
]

export function MetadataPanel({ metadata }: MetadataPanelProps) {
  return (
    <details className="rounded-[var(--radius-lg)] border border-[var(--border-default)] bg-[var(--bg-surface)]">
      <summary className="flex items-center gap-2 px-4 py-3 cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden">
        <ChevronRight
          size={14}
          strokeWidth={1.5}
          className="text-[var(--text-tertiary)] transition-transform details-open:rotate-90"
        />
        <span className="text-[13px] font-semibold text-[var(--text-primary)]">
          报告元数据
        </span>
      </summary>

      <div className="px-4 pb-4 flex flex-col gap-4 border-t border-[var(--border-divider)] pt-3">
        {/* Core fields */}
        <div className="grid grid-cols-2 gap-x-6 gap-y-2">
          <MetaField label="报告 ID" value={metadata.report_id} mono />
          <MetaField label="Trace ID" value={metadata.trace_id} mono />
          <MetaField
            label="场景"
            value={SCENARIO_LABELS[metadata.scenario as Scenario] ?? metadata.scenario}
          />
          {metadata.schema_version && (
            <MetaField label="Schema 版本" value={metadata.schema_version} />
          )}
          <MetaField
            label="发布日期"
            value={formatDate(metadata.publication_date)}
          />
          {metadata.version && (
            <MetaField label="版本" value={metadata.version} />
          )}
          {metadata.organization && (
            <MetaField label="组织" value={metadata.organization} />
          )}
          <MetaField
            label="数据源数"
            value={String(metadata.data_sources?.length ?? 0)}
          />
        </div>

        {/* Score source indicator */}
        {metadata.score_source && (
          <div className="flex items-center gap-2 text-[12px] text-[var(--text-tertiary)]">
            <Shield size={12} strokeWidth={1.5} />
            <span>
              评分来源:{' '}
              <span className="text-[var(--text-secondary)] font-medium">
                {metadata.score_source === 'critic' ? 'AI 质检' : '降级估算'}
              </span>
            </span>
          </div>
        )}

        {/* Critic Scores bar chart */}
        {metadata.critic_scores && (
          <CriticScoresChart scores={metadata.critic_scores} />
        )}

        {/* Warnings */}
        {metadata.warnings && metadata.warnings.length > 0 && (
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center gap-1.5">
              <AlertTriangle size={12} strokeWidth={1.5} className="text-[var(--warning)]" />
              <span className="text-[11px] uppercase tracking-wider text-[var(--text-tertiary)] font-medium">
                警告
              </span>
            </div>
            <ul className="flex flex-col gap-1">
              {metadata.warnings.map((w, i) => (
                <li
                  key={i}
                  className="text-[12px] text-[var(--warning)] leading-relaxed pl-[18px] before:content-['!'] before:absolute before:ml-[-12px] before:text-[var(--warning)] before:font-bold"
                >
                  {w}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Disclaimer */}
        {metadata.disclaimer && (
          <p className="text-[12px] text-[var(--text-tertiary)] italic leading-relaxed border-t border-[var(--border-divider)] pt-3">
            {metadata.disclaimer}
          </p>
        )}
      </div>
    </details>
  )
}

function MetaField({
  label,
  value,
  mono,
}: {
  label: string
  value: string
  mono?: boolean
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[11px] uppercase tracking-wider text-[var(--text-tertiary)] font-medium">
        {label}
      </span>
      <span
        className={`text-[13px] text-[var(--text-secondary)] truncate ${mono ? 'font-[family-name:var(--font-mono)] text-[12px]' : ''}`}
      >
        {value}
      </span>
    </div>
  )
}

function CriticScoresChart({ scores }: { scores: CriticScores }) {
  return (
    <div className="flex flex-col gap-2">
      <span className="text-[11px] uppercase tracking-wider text-[var(--text-tertiary)] font-medium">
        Critic 4 维评分
      </span>
      <div className="flex flex-col gap-2">
        {CRITIC_DIMENSIONS.map(({ key, label, color }) => {
          const raw = scores[key]
          const value = typeof raw === 'number' ? raw : 0
          const pct = (value / 4) * 100

          return (
            <div key={key} className="flex items-center gap-3">
              <span className="text-[12px] text-[var(--text-secondary)] w-24 shrink-0">
                {label}
              </span>
              <div className="flex-1 h-2 rounded-full bg-[var(--border-divider)] overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{ width: `${pct}%`, backgroundColor: color }}
                />
              </div>
              <span className="text-[12px] font-[family-name:var(--font-mono)] tabular-nums text-[var(--text-tertiary)] w-6 text-right">
                {value}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    })
  } catch {
    return iso
  }
}
