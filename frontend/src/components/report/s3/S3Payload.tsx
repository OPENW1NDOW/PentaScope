'use client'

import type { S3PricingStrategyPayload } from '@/types'
import { SortableTable } from '@/components/ui/SortableTable'
import { t } from '@/lib/translations'
import { formatPct } from '@/lib/formatters'

interface S3PayloadProps {
  payload: S3PricingStrategyPayload
}

export function S3Payload({ payload }: S3PayloadProps) {
  const { pricing_baseline, value_drivers, packaging, competitive_pricing_matrix, recommendations_summary, rollout_plan } = payload

  // 价值驱动因素表
  const driverCols = [
    { key: 'driver_name', label: '驱动因素' },
    { key: 'importance', label: '重要性' },
    { key: 'evidence', label: '证据' },
  ]
  const driverData = value_drivers.map((d) => ({
    driver_name: d.driver_name ?? '—',
    importance: t(d.importance),
    evidence: d.evidence ?? '—',
  }))

  // 路线图表
  const rolloutCols = [
    { key: 'step_name', label: '步骤' },
    { key: 'description', label: '描述' },
    { key: 'duration', label: '时长' },
    { key: 'owner_team', label: '负责团队' },
    { key: 'success_metric', label: '成功指标' },
  ]
  const rolloutData = rollout_plan.map((s) => ({
    step_name: s.step_name ?? '—',
    description: s.description ?? '—',
    duration: s.duration,
    owner_team: s.owner_team ?? '—',
    success_metric: s.success_metric ?? '—',
  }))

  return (
    <div className="flex flex-col gap-8">
      {/* 定价基线 */}
      <section>
        <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">定价基线</h3>
        <div className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] p-4 space-y-2">
          <p className="text-[14px] text-[var(--text-primary)]"><strong>当前模型：</strong>{t(pricing_baseline.current_pricing_model)}</p>
          <p className="text-[14px] text-[var(--text-primary)]"><strong>层级数：</strong>{pricing_baseline.current_tier_count}</p>
          {pricing_baseline.current_arpu_note && (
            <p className="text-[14px] text-[var(--text-primary)]"><strong>ARPU：</strong>{pricing_baseline.current_arpu_note}</p>
          )}
          {pricing_baseline.pain_points?.length > 0 && (
            <div>
              <p className="text-[13px] font-medium text-[var(--text-secondary)] mb-1">痛点：</p>
              <ul className="space-y-1">
                {pricing_baseline.pain_points.map((p, i) => (
                  <li key={i} className="text-[13px] text-[var(--danger)]">• {p}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </section>

      {/* 价值驱动因素 */}
      <section>
        <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">价值驱动因素</h3>
        <SortableTable data={driverData} columns={driverCols} />
      </section>

      {/* 推荐套餐 */}
      <section>
        <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">推荐套餐</h3>
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
          {packaging.tiers.map((tier, i) => (
            <div
              key={i}
              className={`rounded-[var(--radius-md)] border bg-[var(--bg-surface)] p-4 ${tier.is_recommended ? 'border-[var(--info)] ring-1 ring-[var(--info)]' : 'border-[var(--border)]'}`}
            >
              {tier.is_recommended && (
                <div className="text-[10px] uppercase tracking-wider text-[var(--info)] font-semibold mb-2">推荐</div>
              )}
              <h4 className="text-[15px] font-semibold text-[var(--text-primary)]">{tier.name ?? tier.position}</h4>
              <div className="text-[20px] font-semibold text-[var(--text-primary)] font-[family-name:var(--font-mono)] mt-1">
                {tier.monthly_price != null ? `¥${tier.monthly_price}` : '—'}
                <span className="text-[12px] text-[var(--text-tertiary)] font-normal">/月</span>
              </div>
              {tier.target_persona && (
                <p className="text-[12px] text-[var(--text-tertiary)] mt-2">{tier.target_persona}</p>
              )}
              {tier.included_features?.length > 0 && (
                <ul className="mt-3 space-y-1">
                  {tier.included_features.map((f, j) => (
                    <li key={j} className="text-[12px] text-[var(--text-secondary)]">✓ {f}</li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* 竞品定价矩阵 */}
      {competitive_pricing_matrix.length > 0 && (
        <section>
          <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">竞品定价矩阵</h3>
          {competitive_pricing_matrix.map((cp, i) => (
            <div key={i} className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] p-4 mb-3">
              <h4 className="text-[14px] font-semibold text-[var(--text-primary)] mb-2">{cp.competitor_name ?? '竞品'}</h4>
              <p className="text-[12px] text-[var(--text-tertiary)] mb-2">模型：{t(cp.pricing_model)} | 免费策略：{cp.free_plan_strategy ? t(cp.free_plan_strategy) : '—'}</p>
              <SortableTable
                data={cp.tiers.map((tier) => ({
                  name: tier.name ?? '—',
                  price: tier.monthly_price != null ? `¥${tier.monthly_price}` : '—',
                  popular: tier.observed_is_most_popular ? '✓' : '',
                  features: tier.observed_features?.join(', ') ?? '—',
                }))}
                columns={[
                  { key: 'name', label: '层级' },
                  { key: 'price', label: '价格' },
                  { key: 'popular', label: '热门' },
                  { key: 'features', label: '功能' },
                ]}
              />
            </div>
          ))}
        </section>
      )}

      {/* 建议摘要 */}
      {recommendations_summary && (
        <section>
          <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">建议摘要</h3>
          <div className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] p-4 space-y-2">
            {recommendations_summary.recommended_packaging_summary && (
              <p className="text-[14px] text-[var(--text-primary)]">{recommendations_summary.recommended_packaging_summary}</p>
            )}
            {recommendations_summary.expected_arr_uplift_pct != null && (
              <p className="text-[14px] text-[var(--success)]">
                预期 ARR 提升：{formatPct(recommendations_summary.expected_arr_uplift_pct)}
              </p>
            )}
          </div>
        </section>
      )}

      {/* 路线图 */}
      <section>
        <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">落地计划</h3>
        <SortableTable data={rolloutData} columns={rolloutCols} />
      </section>
    </div>
  )
}
