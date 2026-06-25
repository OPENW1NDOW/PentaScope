'use client'

import type { S1FeatureIterationPayload } from '@/types'
import { RadarChart } from '@/components/charts'
import { SortableTable } from '@/components/ui/SortableTable'
import { t } from '@/lib/translations'

interface S1PayloadProps {
  payload: S1FeatureIterationPayload
}

export function S1Payload({ payload }: S1PayloadProps) {
  // 雷达图数据
  const radarData = [
    { dimension: '功能广度', ...Object.fromEntries(payload.radar_scores.map((s) => [s.competitor_name, s.feature_breadth])) },
    { dimension: '易用性', ...Object.fromEntries(payload.radar_scores.map((s) => [s.competitor_name, s.usability])) },
    { dimension: '性价比', ...Object.fromEntries(payload.radar_scores.map((s) => [s.competitor_name, s.cost_effectiveness])) },
    { dimension: '稳定性', ...Object.fromEntries(payload.radar_scores.map((s) => [s.competitor_name, s.stability])) },
    { dimension: '设计质量', ...Object.fromEntries(payload.radar_scores.map((s) => [s.competitor_name, s.design_quality])) },
  ]
  const radarKeys = payload.radar_scores.map((s) => s.competitor_name)

  // 供应商概况表
  const vendorCols = [
    { key: 'competitor_name', label: '竞品' },
    { key: 'wave_position', label: '波次定位' },
    { key: 'one_line_pitch', label: '一句话定位' },
    { key: 'strengths_count', label: '优势数' },
    { key: 'cautions_count', label: '风险数' },
  ]
  const vendorData = payload.vendor_profiles.map((v) => ({
    competitor_name: v.competitor_name,
    wave_position: t(v.wave_position),
    one_line_pitch: v.one_line_pitch,
    strengths_count: v.strengths?.length ?? 0,
    cautions_count: v.cautions?.length ?? 0,
  }))

  // 功能差距表
  const gapCols = [
    { key: 'feature_name', label: '功能' },
    { key: 'competitors_have_it', label: '竞品拥有' },
    { key: 'estimated_effort', label: '开发难度' },
    { key: 'estimated_impact', label: '预期影响' },
    { key: 'recommendation', label: '建议' },
  ]
  const gapData = payload.feature_gaps.map((g) => ({
    feature_name: g.feature_name,
    competitors_have_it: g.competitors_have_it.join(', '),
    estimated_effort: t(g.estimated_effort),
    estimated_impact: t(g.estimated_impact),
    recommendation: t(g.recommendation),
  }))

  return (
    <div className="flex flex-col gap-8">
      {/* 雷达图 */}
      <section>
        <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">五维雷达对比</h3>
        <RadarChart data={radarData} keys={radarKeys} />
      </section>

      {/* 供应商概况 */}
      <section>
        <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">供应商概况</h3>
        <SortableTable data={vendorData} columns={vendorCols} />
      </section>

      {/* JTBD */}
      {payload.job_statement && (
        <section>
          <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">用户任务 (JTBD)</h3>
          <div className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] p-4 space-y-2">
            <p className="text-[14px] text-[var(--text-primary)]"><strong>场景：</strong>{payload.job_statement.situation}</p>
            <p className="text-[14px] text-[var(--text-primary)]"><strong>动机：</strong>{payload.job_statement.motivation}</p>
            <p className="text-[14px] text-[var(--text-primary)]"><strong>期望结果：</strong>{payload.job_statement.outcome}</p>
            {payload.job_statement.layer && (
              <p className="text-[12px] text-[var(--text-tertiary)]">层次：{t(payload.job_statement.layer)}</p>
            )}
          </div>
        </section>
      )}

      {/* 功能差距 */}
      <section>
        <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">功能差距分析</h3>
        <SortableTable data={gapData} columns={gapCols} />
      </section>

      {/* 路线图建议 */}
      {payload.roadmap_recommendations && (
        <section>
          <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">路线图建议</h3>
          <div className="grid grid-cols-3 gap-3">
            {(payload.roadmap_recommendations.must_build ?? []).length > 0 && (
              <div className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] p-4">
                <h4 className="text-[13px] font-semibold text-[var(--tag-green-text)] mb-2">必须构建</h4>
                <ul className="space-y-1">
                  {(payload.roadmap_recommendations.must_build ?? []).map((item, i) => (
                    <li key={i} className="text-[13px] text-[var(--text-primary)]">• {item}</li>
                  ))}
                </ul>
              </div>
            )}
            {(payload.roadmap_recommendations.should_skip ?? []).length > 0 && (
              <div className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] p-4">
                <h4 className="text-[13px] font-semibold text-[var(--tag-red-text)] mb-2">建议跳过</h4>
                <ul className="space-y-1">
                  {(payload.roadmap_recommendations.should_skip ?? []).map((item, i) => (
                    <li key={i} className="text-[13px] text-[var(--text-primary)]">• {item}</li>
                  ))}
                </ul>
              </div>
            )}
            {(payload.roadmap_recommendations.should_differentiate ?? []).length > 0 && (
              <div className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] p-4">
                <h4 className="text-[13px] font-semibold text-[var(--tag-blue-text)] mb-2">差异化</h4>
                <ul className="space-y-1">
                  {(payload.roadmap_recommendations.should_differentiate ?? []).map((item, i) => (
                    <li key={i} className="text-[13px] text-[var(--text-primary)]">• {item}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </section>
      )}
    </div>
  )
}
