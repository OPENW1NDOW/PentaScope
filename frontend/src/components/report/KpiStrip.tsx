'use client'

import type { ReportMetadata } from '@/types'
import { SCENARIO_LABELS, CONFIDENCE_CONFIG } from '@/types'
import type { Scenario, ConfidenceLevel } from '@/types'

interface KpiStripProps {
  metadata: ReportMetadata
}

function confidenceColor(level: ConfidenceLevel): string {
  switch (level) {
    case 'high':
      return 'tag-green'
    case 'medium':
      return 'tag-yellow'
    case 'low':
      return 'tag-red'
  }
}

function qualityColor(score: number | null | undefined): string {
  if (score == null) return 'text-[var(--text-tertiary)]'
  if (score >= 0.8) return 'text-[var(--success)]'
  if (score >= 0.6) return 'text-[var(--warning)]'
  return 'text-[var(--danger)]'
}

export function KpiStrip({ metadata }: KpiStripProps) {
  const quality = metadata.quality_score
  const scenarioLabel = SCENARIO_LABELS[metadata.scenario as Scenario] ?? metadata.scenario
  const confidenceCfg = CONFIDENCE_CONFIG[metadata.confidence_level]
  const competitorCount = metadata.data_sources?.length ?? 0

  return (
    <div
      className="grid grid-cols-5 gap-px rounded-[var(--radius-lg)] overflow-hidden border border-[var(--border-default)] bg-[var(--border-divider)]"
    >
      {/* Quality Score */}
      <div className="bg-[var(--bg-surface)] px-4 py-3 flex flex-col gap-0.5">
        <span className="text-[11px] uppercase tracking-wider text-[var(--text-tertiary)] font-medium">
          质检评分
        </span>
        <span
          className={`text-[20px] font-semibold font-[family-name:var(--font-mono)] tabular-nums ${qualityColor(quality)}`}
        >
          {quality != null ? quality.toFixed(2) : '--'}
        </span>
      </div>

      {/* Scenario */}
      <div className="bg-[var(--bg-surface)] px-4 py-3 flex flex-col gap-0.5">
        <span className="text-[11px] uppercase tracking-wider text-[var(--text-tertiary)] font-medium">
          分析场景
        </span>
        <span className="text-[14px] font-medium text-[var(--text-primary)]">
          {scenarioLabel}
        </span>
      </div>

      {/* Competitor Count */}
      <div className="bg-[var(--bg-surface)] px-4 py-3 flex flex-col gap-0.5">
        <span className="text-[11px] uppercase tracking-wider text-[var(--text-tertiary)] font-medium">
          数据源
        </span>
        <span className="text-[14px] font-medium text-[var(--text-primary)]">
          {competitorCount}
        </span>
      </div>

      {/* Data Sources */}
      <div className="bg-[var(--bg-surface)] px-4 py-3 flex flex-col gap-0.5">
        <span className="text-[11px] uppercase tracking-wider text-[var(--text-tertiary)] font-medium">
          参考资料
        </span>
        <span className="text-[14px] font-medium text-[var(--text-primary)]">
          {metadata.data_sources?.length ?? 0} 条
        </span>
      </div>

      {/* Confidence */}
      <div className="bg-[var(--bg-surface)] px-4 py-3 flex flex-col gap-0.5">
        <span className="text-[11px] uppercase tracking-wider text-[var(--text-tertiary)] font-medium">
          可信度
        </span>
        <span className={`inline-flex items-center`}>
          <span className={`${confidenceColor(metadata.confidence_level)} text-[13px] font-medium px-2 py-0.5 rounded-[var(--radius-sm)]`}>
            {confidenceCfg?.label ?? metadata.confidence_level}
          </span>
        </span>
      </div>
    </div>
  )
}
