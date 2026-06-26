'use client'

import type { S5PositioningPayload } from '@/types'
import { ScatterChart, LineChart } from '@/components/charts'
import { SortableTable } from '@/components/ui/SortableTable'
import { t } from '@/lib/translations'

interface S5PayloadProps {
  payload: S5PositioningPayload
}

export function S5Payload({ payload }: S5PayloadProps) {
  const { vendor_profiles, perceptual_map, strategy_canvas, errc_grid, positioning_statement, category_strategy, blue_ocean_move } = payload

  // 感知地图数据
  const scatterData = perceptual_map.plotted_brands.map((b) => ({
    name: b.competitor_name ?? '—',
    x: b.x_score,
    y: b.y_score,
    isSelf: b.is_self,
  }))

  // 策略画布数据
  const factorNames = strategy_canvas.competitive_factors.map((f) => f.name ?? '—')
  const canvasData = factorNames.map((name) => {
    const row: Record<string, number | string> = { factor: name }
    strategy_canvas.value_curves.forEach((vc) => {
      row[vc.competitor_name ?? '—'] = vc.factor_levels[name] ?? 0
    })
    return row
  })
  const canvasLines = strategy_canvas.value_curves.map((vc) => ({
    key: vc.competitor_name ?? '—',
    isSelf: vc.is_self,
  }))

  // MQ 散点数据
  const mqData = vendor_profiles.map((v) => ({
    name: v.competitor_name ?? '—',
    x: v.ability_to_execute_score,
    y: v.completeness_of_vision_score,
  }))

  // ERRC 表格
  const errcToData = (items: typeof errc_grid.eliminate) =>
    (items ?? []).map((item) => ({
      factor: item.factor ?? '—',
      rationale: item.rationale ?? '—',
      proposed_level: item.proposed_level != null ? String(item.proposed_level) : '—',
      buyer_value: item.buyer_value ?? '—',
    }))
  const errcCols = [
    { key: 'factor', label: '因素' },
    { key: 'rationale', label: '理由' },
    { key: 'proposed_level', label: '建议水平' },
    { key: 'buyer_value', label: '买方价值' },
  ]

  return (
    <div className="flex flex-col gap-8">
      {/* 魔力象限 */}
      <section>
        <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">魔力象限</h3>
        <ScatterChart
          data={mqData}
          xLabel="执行力"
          yLabel="愿景完整度"
          xMax={5}
          yMax={5}
          quadrantLines
        />
      </section>

      {/* 感知地图 */}
      <section>
        <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">感知地图</h3>
        <ScatterChart
          data={scatterData}
          xLabel={`${perceptual_map.x_axis.attribute} (${perceptual_map.x_axis.low_label} → ${perceptual_map.x_axis.high_label})`}
          yLabel={`${perceptual_map.y_axis.attribute} (${perceptual_map.y_axis.low_label} → ${perceptual_map.y_axis.high_label})`}
          xMax={perceptual_map.x_axis.scale_max ?? 5}
          yMax={perceptual_map.y_axis.scale_max ?? 5}
        />
      </section>

      {/* 策略画布 */}
      <section>
        <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">策略画布</h3>
        <LineChart data={canvasData} xKey="factor" lines={canvasLines} />
      </section>

      {/* ERRC 网格 */}
      <section>
        <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">ERRC 网格</h3>
        <div className="grid grid-cols-2 gap-3">
          {[
            { label: '消除', data: errcToData(errc_grid.eliminate), colorClass: 'tag-red' },
            { label: '减少', data: errcToData(errc_grid.reduce), colorClass: 'tag-orange' },
            { label: '提升', data: errcToData(errc_grid.raise_level), colorClass: 'tag-green' },
            { label: '创造', data: errcToData(errc_grid.create), colorClass: 'tag-blue' },
          ].map((section) => (
            <div key={section.label} className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] p-4">
              <h4 className={`text-[13px] font-semibold mb-2 inline-block px-2 py-0.5 rounded-[var(--radius-sm)] ${section.colorClass}`}>
                {section.label}
              </h4>
              {section.data.length > 0 ? (
                <ul className="space-y-1">
                  {section.data.map((item, i) => (
                    <li key={i} className="text-[13px] text-[var(--text-primary)]">• {item.factor}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-[12px] text-[var(--text-tertiary)]">暂无</p>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* 定位声明 */}
      {positioning_statement && (
        <section>
          <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">定位声明</h3>
          <div className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] p-4 space-y-2">
            {positioning_statement.target_customer && <p className="text-[14px] text-[var(--text-primary)]"><strong>目标客户：</strong>{positioning_statement.target_customer}</p>}
            {positioning_statement.need_or_opportunity && <p className="text-[14px] text-[var(--text-primary)]"><strong>需求/机会：</strong>{positioning_statement.need_or_opportunity}</p>}
            {positioning_statement.product_name && <p className="text-[14px] text-[var(--text-primary)]"><strong>产品名称：</strong>{positioning_statement.product_name}</p>}
            {positioning_statement.key_benefit && <p className="text-[14px] text-[var(--text-primary)]"><strong>核心价值：</strong>{positioning_statement.key_benefit}</p>}
            {positioning_statement.primary_alternative && <p className="text-[14px] text-[var(--text-primary)]"><strong>主要替代方案：</strong>{positioning_statement.primary_alternative}</p>}
            {positioning_statement.primary_differentiation && <p className="text-[14px] text-[var(--text-primary)]"><strong>核心差异化：</strong>{positioning_statement.primary_differentiation}</p>}
          </div>
        </section>
      )}

      {/* 蓝海策略 */}
      {blue_ocean_move && (
        <section>
          <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">蓝海策略</h3>
          <div className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] p-4 space-y-2">
            <p className="text-[16px] font-semibold text-[var(--text-primary)]">“{blue_ocean_move.compelling_tagline}”</p>
            {blue_ocean_move.new_value_curve_summary && <p className="text-[14px] text-[var(--text-secondary)]">{blue_ocean_move.new_value_curve_summary}</p>}
            {blue_ocean_move.target_noncustomers?.length > 0 && (
              <div>
                <p className="text-[13px] font-medium text-[var(--text-secondary)] mb-1">目标非客户：</p>
                <ul className="space-y-1">
                  {blue_ocean_move.target_noncustomers.map((nc, i) => (
                    <li key={i} className="text-[13px] text-[var(--text-primary)]">• {nc}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </section>
      )}

      {/* 品类策略 */}
      {category_strategy && (
        <section>
          <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">品类策略</h3>
          <div className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] p-4 space-y-2">
            <p className="text-[14px] text-[var(--text-primary)]"><strong>选择品类：</strong>{category_strategy.chosen_category}</p>
            {category_strategy.why_this_category && <p className="text-[14px] text-[var(--text-secondary)]">{category_strategy.why_this_category}</p>}
            {category_strategy.risk_of_category_choice && <p className="text-[13px] text-[var(--warning)]">风险：{category_strategy.risk_of_category_choice}</p>}
          </div>
        </section>
      )}
    </div>
  )
}
