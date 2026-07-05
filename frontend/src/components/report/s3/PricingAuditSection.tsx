'use client'

import type { PricingPageAudit, PricingPageAuditScore } from '@/types'

const RULE_LABELS: Record<PricingPageAuditScore['rule_name'], string> = {
  tier_naming_buyer_centric: '层级命名以买家为中心',
  anchor_pricing_middle_tier: '中档锚定定价',
  annual_billing_default: '年付为默认',
  feature_gating_clear: '功能分层清晰',
  cta_copy_aligned: 'CTA 文案一致',
  social_proof_at_decision: '决策点社会证明',
  transparent_feature_comparison: '功能对比透明',
  psychological_pricing: '心理定价',
}

const RULE_ORDER = Object.keys(RULE_LABELS) as PricingPageAuditScore['rule_name'][]

function sortScores(scores: PricingPageAuditScore[]): PricingPageAuditScore[] {
  const byRule = new Map(scores.map((score) => [score.rule_name, score]))
  return RULE_ORDER.filter((rule) => byRule.has(rule)).map(
    (rule) => byRule.get(rule)!,
  )
}

function PassBadge({ passed }: { passed: boolean }) {
  return (
    <span
      className={`inline-flex items-center text-[12px] font-medium px-2 py-0.5 rounded-[var(--radius-sm)] ${passed ? 'tag-green' : 'tag-red'}`}
    >
      {passed ? '✓' : '✗'}
    </span>
  )
}

function AuditBlock({ audit }: { audit: PricingPageAudit }) {
  const scores = sortScores(audit.audit_scores ?? [])
  const passedCount = scores.filter((score) => score.passed).length
  const totalCount = scores.length

  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] p-4 mb-3 last:mb-0">
      <div className="flex items-start justify-between gap-3 mb-2 flex-wrap">
        <h4 className="text-[14px] font-semibold text-[var(--text-primary)]">
          {audit.competitor_name ?? '竞品'}
        </h4>
        {totalCount > 0 && (
          <span className="text-[12px] text-[var(--text-secondary)] font-[family-name:var(--font-mono)]">
            通过率 {passedCount}/{totalCount}
          </span>
        )}
      </div>

      {audit.pricing_page_url && (
        <p className="mb-3">
          <a
            href={audit.pricing_page_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[12px] text-[var(--info)] hover:underline decoration-[var(--text-tertiary)] break-all"
          >
            {audit.pricing_page_url}
          </a>
        </p>
      )}

      {scores.length === 0 ? (
        <p className="text-[12px] text-[var(--text-tertiary)]">暂无审计数据</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr>
                <th className="text-left font-medium text-[var(--text-secondary)] px-3 py-2 border-b border-[var(--border)] bg-[var(--bg-page)] text-[12px] uppercase tracking-wider">
                  法则
                </th>
                <th className="text-left font-medium text-[var(--text-secondary)] px-3 py-2 border-b border-[var(--border)] bg-[var(--bg-page)] text-[12px] uppercase tracking-wider w-20">
                  通过
                </th>
                <th className="text-left font-medium text-[var(--text-secondary)] px-3 py-2 border-b border-[var(--border)] bg-[var(--bg-page)] text-[12px] uppercase tracking-wider">
                  备注
                </th>
              </tr>
            </thead>
            <tbody>
              {scores.map((score) => (
                <tr key={score.rule_name} className="border-b border-[var(--border-divider)] last:border-0">
                  <td className="px-3 py-2 text-[var(--text-primary)]">
                    {RULE_LABELS[score.rule_name]}
                  </td>
                  <td className="px-3 py-2">
                    <PassBadge passed={score.passed} />
                  </td>
                  <td className="px-3 py-2 text-[var(--text-secondary)]">
                    {score.note ?? '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export function PricingAuditSection({ audits }: { audits?: PricingPageAudit[] | null }) {
  if (!audits || audits.length === 0) return null

  return (
    <section>
      <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">定价页审计</h3>
      {audits.map((audit, i) => (
        <AuditBlock key={audit.artifact_id ?? i} audit={audit} />
      ))}
    </section>
  )
}
