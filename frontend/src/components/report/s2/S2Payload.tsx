'use client'

import type { S2MarketEntryPayload } from '@/types'
import { FiveForcesRadar } from '@/components/charts'
import { SortableTable } from '@/components/ui/SortableTable'
import { t } from '@/lib/translations'
import { formatMarketValue, formatPct } from '@/lib/formatters'

interface S2PayloadProps {
  payload: S2MarketEntryPayload
}

export function S2Payload({ payload }: S2PayloadProps) {
  const { market_sizing, five_forces, players, key_trends, entry_strategy } = payload

  // 市场玩家表
  const playerCols = [
    { key: 'name', label: '名称' },
    { key: 'market_role', label: '角色' },
    { key: 'market_share', label: '市场份额' },
    { key: 'growth', label: '同比增长' },
    { key: 'differentiator', label: '差异化' },
  ]
  const playerData = players.map((p) => ({
    name: p.name ?? '—',
    market_role: t(p.market_role),
    market_share: formatPct(p.market_share_pct),
    growth: formatPct(p.yoy_growth_pct),
    differentiator: p.key_differentiator ?? '—',
  }))

  // 趋势表
  const trendCols = [
    { key: 'trend_name', label: '趋势' },
    { key: 'direction', label: '方向' },
    { key: 'time_horizon', label: '时间范围' },
    { key: 'impact', label: '对进入的影响' },
  ]
  const trendData = key_trends.map((tr) => ({
    trend_name: tr.trend_name ?? '—',
    direction: t(tr.direction),
    time_horizon: t(tr.time_horizon),
    impact: t(tr.impact_on_entry),
  }))

  return (
    <div className="flex flex-col gap-8">
      {/* TAM/SAM/SOM */}
      <section>
        <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">市场规模</h3>
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: 'TAM', value: market_sizing.tam },
            { label: 'SAM', value: market_sizing.sam },
            { label: 'SOM', value: market_sizing.som },
          ].map((item) => (
            <div key={item.label} className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] p-4 text-center">
              <div className="text-[11px] uppercase tracking-wider text-[var(--text-tertiary)] font-medium mb-1">{item.label}</div>
              <div className="text-[20px] font-semibold text-[var(--text-primary)] font-[family-name:var(--font-mono)]">
                {formatMarketValue(item.value)}
              </div>
              {item.value?.geography && (
                <div className="text-[11px] text-[var(--text-tertiary)] mt-1">{item.value.geography}</div>
              )}
            </div>
          ))}
        </div>
        {market_sizing.cagr_pct != null && (
          <p className="text-[12px] text-[var(--text-tertiary)] mt-2">CAGR: {formatPct(market_sizing.cagr_pct)}</p>
        )}
      </section>

      {/* 五力分析 */}
      <section>
        <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">Porter 五力分析</h3>
        <FiveForcesRadar forces={five_forces} />
      </section>

      {/* 市场玩家 */}
      <section>
        <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">市场玩家</h3>
        <SortableTable data={playerData} columns={playerCols} />
      </section>

      {/* 关键趋势 */}
      <section>
        <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">关键趋势</h3>
        <SortableTable data={trendData} columns={trendCols} />
      </section>

      {/* 进入策略 */}
      {entry_strategy && (
        <section>
          <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">进入策略</h3>
          <div className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] p-4 space-y-3">
            <p className="text-[14px] text-[var(--text-primary)]"><strong>推荐模式：</strong>{t(entry_strategy.recommended_mode)}</p>
            {entry_strategy.initial_positioning && (
              <p className="text-[14px] text-[var(--text-primary)]"><strong>初始定位：</strong>{entry_strategy.initial_positioning}</p>
            )}
            {entry_strategy.key_success_factors?.length > 0 && (
              <div>
                <p className="text-[13px] font-medium text-[var(--text-secondary)] mb-1">关键成功因素：</p>
                <ul className="space-y-1">
                  {entry_strategy.key_success_factors.map((f, i) => (
                    <li key={i} className="text-[13px] text-[var(--text-primary)]">• {f}</li>
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
