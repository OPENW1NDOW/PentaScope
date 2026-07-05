'use client'

import type { PESTEL, PESTELFactor } from '@/types'

const DIMENSIONS = [
  { key: 'political', label: '政治' },
  { key: 'economic', label: '经济' },
  { key: 'social', label: '社会' },
  { key: 'technological', label: '技术' },
  { key: 'environmental', label: '环境' },
  { key: 'legal', label: '法律' },
] as const

type PestelDimensionKey = (typeof DIMENSIONS)[number]['key']

const IMPACT_CONFIG: Record<
  PESTELFactor['impact'],
  { label: string; tag: string }
> = {
  opportunity: { label: '机会', tag: 'tag-green' },
  threat: { label: '威胁', tag: 'tag-red' },
  neutral: { label: '中性', tag: 'tag-gray' },
}

const SEVERITY_CONFIG: Record<
  PESTELFactor['severity'],
  { label: string; tag: string }
> = {
  high: { label: '高', tag: 'tag-red' },
  medium: { label: '中', tag: 'tag-orange' },
  low: { label: '低', tag: 'tag-gray' },
}

function isPestelEmpty(pestel: PESTEL): boolean {
  return DIMENSIONS.every(({ key }) => {
    const factors = pestel[key]
    return !factors || factors.length === 0
  })
}

function Tag({ label, tag }: { label: string; tag: string }) {
  return (
    <span className={`text-[11px] font-medium px-1.5 py-0.5 rounded-[var(--radius-sm)] ${tag}`}>
      {label}
    </span>
  )
}

function FactorItem({ factor, index }: { factor: PESTELFactor; index: number }) {
  const impact = IMPACT_CONFIG[factor.impact]
  const severity = SEVERITY_CONFIG[factor.severity]

  return (
    <li className="flex flex-col gap-1.5">
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="text-[13px] font-medium text-[var(--text-primary)]">
          {factor.name ?? `因素 ${index + 1}`}
        </span>
        <Tag label={impact.label} tag={impact.tag} />
        <Tag label={severity.label} tag={severity.tag} />
      </div>
      {factor.description && (
        <p className="text-[12px] text-[var(--text-secondary)] leading-relaxed">
          {factor.description}
        </p>
      )}
    </li>
  )
}

export function PESTELSection({ pestel }: { pestel?: PESTEL | null }) {
  if (!pestel || isPestelEmpty(pestel)) return null

  return (
    <section>
      <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">PESTEL 分析</h3>
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
        {DIMENSIONS.map(({ key, label }) => {
          const factors = pestel[key as PestelDimensionKey] ?? []

          return (
            <div
              key={key}
              className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] p-4"
            >
              <h4 className="text-[13px] font-semibold text-[var(--text-primary)] mb-3">{label}</h4>
              {factors.length === 0 ? (
                <p className="text-[12px] text-[var(--text-tertiary)]">暂无</p>
              ) : (
                <ul className="flex flex-col gap-3">
                  {factors.map((factor, i) => (
                    <FactorItem key={i} factor={factor} index={i} />
                  ))}
                </ul>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}
