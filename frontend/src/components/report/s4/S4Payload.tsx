'use client'

import type {
  S4MonitoringPayload,
  ChangeSeverity,
  FIATuple,
  FeatureChange,
  PricingChange,
  MessagingChange,
  NewsEvent,
  OrgChange,
  MonitoringThreat,
  Battlecard,
  BattlecardSectionName,
  BattlecardCompleteness,
  MonitoringTrends,
} from '@/types'
import { t } from '@/lib/translations'
import { trendArrow } from '@/lib/formatters'
import { ChevronRight } from 'lucide-react'
import type { ReactNode } from 'react'

interface S4PayloadProps {
  payload: S4MonitoringPayload
}

// ============================================================
// S4 局部枚举中文映射（不修改 translations.ts）
// ============================================================

const FEATURE_CHANGE_TYPE: Record<string, string> = {
  new_feature: '新功能 (new_feature)',
  removed_feature: '功能下架 (removed_feature)',
  feature_updated: '功能更新 (feature_updated)',
}

const PRICING_CHANGE_TYPE: Record<string, string> = {
  tier_added: '新增层级 (tier_added)',
  tier_removed: '移除层级 (tier_removed)',
  price_increased: '涨价 (price_increased)',
  price_decreased: '降价 (price_decreased)',
  packaging_restructured: '套餐重组 (packaging_restructured)',
  discount_changed: '折扣变更 (discount_changed)',
}

const MESSAGING_CHANGE_TYPE: Record<string, string> = {
  headline_changed: '标语变更 (headline_changed)',
  positioning_shift: '定位转变 (positioning_shift)',
  brand_update: '品牌更新 (brand_update)',
  campaign_launch: '活动上线 (campaign_launch)',
}

const NEWS_CATEGORY: Record<string, string> = {
  funding: '融资 (funding)',
  partnership: '合作 (partnership)',
  leadership: '高管变动 (leadership)',
  legal: '法律/合规 (legal)',
  product_launch: '产品发布 (product_launch)',
  acquisition: '收购 (acquisition)',
  ipo: 'IPO (ipo)',
  layoff: '裁员 (layoff)',
  other: '其他 (other)',
}

const ORG_ACTION: Record<string, string> = {
  hired: '入职 (hired)',
  departed: '离职 (departed)',
  promoted: '晋升 (promoted)',
  demoted: '降级 (demoted)',
  joined_board: '加入董事会 (joined_board)',
  title_changed: '头衔变更 (title_changed)',
  founder_exit: '创始人离开 (founder_exit)',
}

const OPPORTUNITY_TYPE: Record<string, string> = {
  abandoned_segment: '放弃的细分市场 (abandoned_segment)',
  product_gap: '产品差距 (product_gap)',
  messaging_white_space: '信息空白 (messaging_white_space)',
  operational_weakness: '运营弱点 (operational_weakness)',
}

const OWNER_TEAM: Record<string, string> = {
  product: '产品 (product)',
  marketing: '市场 (marketing)',
  sales: '销售 (sales)',
  exec: '管理层 (exec)',
  engineering: '工程 (engineering)',
  support: '客服 (support)',
}

const QUADRANT_CONFIG: Record<
  MonitoringThreat['quadrant'],
  { label: string; tagClass: string }
> = {
  act_now: { label: '立即行动', tagClass: 'tag-red' },
  contingency: { label: '预案准备', tagClass: 'tag-orange' },
  monitor: { label: '持续观察', tagClass: 'tag-yellow' },
  deprioritize: { label: '降低优先级', tagClass: 'tag-gray' },
}

const BATTLECARD_SECTION_LABELS: Record<BattlecardSectionName, string> = {
  quick_summary: '快速摘要',
  primary_threat: '主要威胁',
  messaging_positioning: '信息与定位',
  pricing_packaging: '定价与打包',
  product_strategy: '产品策略',
  customer_sentiment: '客户口碑',
  win_loss_themes: '赢单/丢单主题',
  monitoring_priorities: '监控重点',
}

const COMPLETENESS_LABELS: Record<BattlecardCompleteness, string> = {
  full: '完整 (full)',
  partial: '部分 (partial)',
  empty: '空 (empty)',
}

const COMPLETENESS_TAG: Record<BattlecardCompleteness, string> = {
  full: 'tag-green',
  partial: 'tag-yellow',
  empty: 'tag-gray',
}

const TREND_ITEMS: { key: keyof MonitoringTrends; label: string }[] = [
  { key: 'sentiment_trend', label: '用户口碑' },
  { key: 'pricing_trend', label: '定价' },
  { key: 'release_velocity_trend', label: '发布节奏' },
  { key: 'threat_level_trend', label: '威胁水平' },
]

function s4t(val: string | null | undefined, map: Record<string, string>): string {
  if (!val) return '—'
  return map[val] ?? t(val)
}

function severityTagClass(severity: ChangeSeverity): string {
  switch (severity) {
    case 'high':
      return 'tag-red'
    case 'medium':
      return 'tag-orange'
    case 'low':
      return 'tag-gray'
    default:
      return 'tag-gray'
  }
}

function priorityTagClass(tier: string): string {
  switch (tier) {
    case 'critical':
      return 'tag-red'
    case 'important':
      return 'tag-orange'
    case 'consider':
      return 'tag-blue'
    default:
      return 'tag-gray'
  }
}

function Tag({ className, children }: { className: string; children: ReactNode }) {
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded-[var(--radius-sm)] text-[11px] font-medium whitespace-nowrap ${className}`}
    >
      {children}
    </span>
  )
}

function SeverityTag({ severity }: { severity: ChangeSeverity }) {
  return <Tag className={severityTagClass(severity)}>{t(severity)}</Tag>
}

function FiaContent({ fia }: { fia: FIATuple }) {
  return (
    <div className="space-y-1">
      <p className="text-[13px] text-[var(--text-primary)]">{fia.fact || '—'}</p>
      {fia.impact && (
        <p className="text-[11px] text-[var(--text-secondary)]">
          <span className="text-[var(--text-tertiary)]">影响：</span>
          {fia.impact}
        </p>
      )}
      {fia.act && (
        <p className="text-[11px] text-[var(--text-secondary)]">
          <span className="text-[var(--text-tertiary)]">行动：</span>
          {fia.act}
        </p>
      )}
    </div>
  )
}

function BaselineBadge({ isBaseline }: { isBaseline: boolean }) {
  if (!isBaseline) return null
  return (
    <Tag className="tag-blue ml-1.5 align-middle">基线</Tag>
  )
}

interface TableColumn {
  key: string
  label: string
  render?: (row: Record<string, unknown>) => ReactNode
}

function StaticTable({
  columns,
  data,
}: {
  columns: TableColumn[]
  data: Array<Record<string, unknown>>
}) {
  if (data.length === 0) {
    return (
      <div className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] p-8 text-center">
        <p className="text-[13px] text-[var(--text-tertiary)]">暂无数据</p>
      </div>
    )
  }

  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-[13px]">
          <thead>
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className="text-left font-medium text-[var(--text-secondary)] px-3 py-2 border-b border-[var(--border)] bg-[var(--bg-page)] text-[12px] uppercase tracking-wider"
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => (
              <tr key={i} className="hover:bg-[var(--bg-hover)] transition-colors">
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className="px-3 py-2 border-b border-[var(--border-divider)] text-[var(--text-primary)] align-top"
                  >
                    {col.render
                      ? col.render(row)
                      : row[col.key] == null || row[col.key] === ''
                        ? '—'
                        : String(row[col.key])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function formatTrendArrow(direction: string | null | undefined): string {
  if (!direction) return '—'
  const arrow = trendArrow(direction)
  return arrow || '—'
}

function ReviewPeriodCard({ rp }: { rp: S4MonitoringPayload['review_period'] }) {
  const hasPrior = Boolean(rp.prior_trace_id)
  const newlyAdded = rp.newly_added_competitors ?? []
  const dropped = rp.dropped_competitors ?? []

  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] p-4 space-y-3">
      <div className="grid grid-cols-2 gap-x-6 gap-y-2">
        <div>
          <span className="text-[11px] uppercase tracking-wider text-[var(--text-tertiary)] font-medium">
            本次监控日期
          </span>
          <p className="text-[13px] text-[var(--text-primary)] mt-0.5">
            {rp.current_review_date || '—'}
          </p>
        </div>
        {rp.review_period_label && (
          <div>
            <span className="text-[11px] uppercase tracking-wider text-[var(--text-tertiary)] font-medium">
              监控周期
            </span>
            <p className="text-[13px] text-[var(--text-primary)] mt-0.5">{rp.review_period_label}</p>
          </div>
        )}
      </div>

      <div>
        <span className="text-[11px] uppercase tracking-wider text-[var(--text-tertiary)] font-medium">
          监控竞品
        </span>
        <div className="flex flex-wrap gap-1.5 mt-1.5">
          {(rp.monitored_competitors ?? []).length > 0 ? (
            rp.monitored_competitors.map((name) => (
              <Tag key={name} className="tag-blue">{name}</Tag>
            ))
          ) : (
            <span className="text-[13px] text-[var(--text-tertiary)]">—</span>
          )}
        </div>
      </div>

      <div>
        <span className="text-[11px] uppercase tracking-wider text-[var(--text-tertiary)] font-medium">
          对比模式
        </span>
        <div className="mt-1">
          {hasPrior ? (
            <span className="font-[family-name:var(--font-mono)] text-[12px] text-[var(--text-secondary)]">
              {rp.prior_trace_id}
            </span>
          ) : (
            <Tag className="tag-blue">首次监控（基线模式）</Tag>
          )}
        </div>
      </div>

      {(newlyAdded.length > 0 || dropped.length > 0) && (
        <div className="grid grid-cols-2 gap-3 pt-1 border-t border-[var(--border-divider)]">
          {newlyAdded.length > 0 && (
            <div>
              <span className="text-[11px] text-[var(--text-tertiary)]">新增竞品</span>
              <div className="flex flex-wrap gap-1 mt-1">
                {newlyAdded.map((name) => (
                  <Tag key={name} className="tag-green">{name}</Tag>
                ))}
              </div>
            </div>
          )}
          {dropped.length > 0 && (
            <div>
              <span className="text-[11px] text-[var(--text-tertiary)]">移除竞品</span>
              <div className="flex flex-wrap gap-1 mt-1">
                {dropped.map((name) => (
                  <Tag key={name} className="tag-gray">{name}</Tag>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function TrendsSection({ trends }: { trends: MonitoringTrends }) {
  const isBaselineMode = TREND_ITEMS.every(({ key }) => !trends[key])

  return (
    <section>
      <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">趋势方向</h3>
      {isBaselineMode ? (
        <div className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] p-4">
          <p className="text-[13px] text-[var(--text-secondary)]">
            首次监控（基线模式）：尚无历史对比数据，四项趋势方向暂不可用。完成下一轮监控后将显示相对变化。
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {TREND_ITEMS.map(({ key, label }) => (
              <div
                key={key}
                className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] p-4 text-center"
              >
                <p className="text-[12px] text-[var(--text-tertiary)] mb-1">{label}</p>
                <p className="text-[24px] font-semibold text-[var(--text-primary)] leading-none">
                  {formatTrendArrow(trends[key] as string | null | undefined)}
                </p>
              </div>
            ))}
          </div>
          {trends.rationale && (
            <p className="text-[12px] text-[var(--text-tertiary)] mt-2 leading-relaxed">
              {trends.rationale}
            </p>
          )}
        </>
      )}
    </section>
  )
}

function changeRowBase(item: { competitor_name: string; severity: ChangeSeverity; fia: FIATuple; is_baseline: boolean }) {
  return {
    competitor_name: item.competitor_name,
    severity: item.severity,
    fia: item.fia,
    is_baseline: item.is_baseline,
  }
}

function FeatureChangesSection({ items }: { items: FeatureChange[] }) {
  if (!items.length) return null
  const data = items.map((item) => ({
    ...changeRowBase(item),
    change_type: item.change_type,
    feature_name: item.feature_name,
  }))
  const columns: TableColumn[] = [
    { key: 'competitor_name', label: '竞品' },
    {
      key: 'change_type',
      label: '变更类型',
      render: (row) => (
        <span>
          {s4t(String(row.change_type), FEATURE_CHANGE_TYPE)}
          <BaselineBadge isBaseline={Boolean(row.is_baseline)} />
        </span>
      ),
    },
    { key: 'feature_name', label: '功能名' },
    {
      key: 'severity',
      label: '严重度',
      render: (row) => <SeverityTag severity={row.severity as ChangeSeverity} />,
    },
    {
      key: 'fia',
      label: 'FIA',
      render: (row) => <FiaContent fia={row.fia as FIATuple} />,
    },
  ]
  return (
    <section>
      <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">功能变更</h3>
      <StaticTable columns={columns} data={data} />
    </section>
  )
}

function PricingChangesSection({ items }: { items: PricingChange[] }) {
  if (!items.length) return null
  const data = items.map((item) => ({
    ...changeRowBase(item),
    change_type: item.change_type,
    before_after: `${item.before} → ${item.after}`,
  }))
  const columns: TableColumn[] = [
    { key: 'competitor_name', label: '竞品' },
    {
      key: 'change_type',
      label: '变更类型',
      render: (row) => (
        <span>
          {s4t(String(row.change_type), PRICING_CHANGE_TYPE)}
          <BaselineBadge isBaseline={Boolean(row.is_baseline)} />
        </span>
      ),
    },
    { key: 'before_after', label: '变更前后' },
    {
      key: 'severity',
      label: '严重度',
      render: (row) => <SeverityTag severity={row.severity as ChangeSeverity} />,
    },
    {
      key: 'fia',
      label: 'FIA',
      render: (row) => <FiaContent fia={row.fia as FIATuple} />,
    },
  ]
  return (
    <section>
      <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">定价变更</h3>
      <StaticTable columns={columns} data={data} />
    </section>
  )
}

function MessagingChangesSection({ items }: { items: MessagingChange[] }) {
  if (!items.length) return null
  const data = items.map((item) => ({
    ...changeRowBase(item),
    change_type: item.change_type,
    before_after: `${item.before_text} → ${item.after_text}`,
  }))
  const columns: TableColumn[] = [
    { key: 'competitor_name', label: '竞品' },
    {
      key: 'change_type',
      label: '变更类型',
      render: (row) => (
        <span>
          {s4t(String(row.change_type), MESSAGING_CHANGE_TYPE)}
          <BaselineBadge isBaseline={Boolean(row.is_baseline)} />
        </span>
      ),
    },
    { key: 'before_after', label: '变更前后' },
    {
      key: 'severity',
      label: '严重度',
      render: (row) => <SeverityTag severity={row.severity as ChangeSeverity} />,
    },
    {
      key: 'fia',
      label: 'FIA',
      render: (row) => <FiaContent fia={row.fia as FIATuple} />,
    },
  ]
  return (
    <section>
      <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">信息变更</h3>
      <StaticTable columns={columns} data={data} />
    </section>
  )
}

function NewsEventsSection({ items }: { items: NewsEvent[] }) {
  if (!items.length) return null
  const data = items.map((item) => ({
    ...changeRowBase(item),
    category: item.category,
    headline: item.headline,
  }))
  const columns: TableColumn[] = [
    { key: 'competitor_name', label: '竞品' },
    {
      key: 'category',
      label: '类别',
      render: (row) => (
        <span>
          {s4t(String(row.category), NEWS_CATEGORY)}
          <BaselineBadge isBaseline={Boolean(row.is_baseline)} />
        </span>
      ),
    },
    { key: 'headline', label: '标题' },
    {
      key: 'severity',
      label: '严重度',
      render: (row) => <SeverityTag severity={row.severity as ChangeSeverity} />,
    },
    {
      key: 'fia',
      label: 'FIA',
      render: (row) => <FiaContent fia={row.fia as FIATuple} />,
    },
  ]
  return (
    <section>
      <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">新闻事件</h3>
      <StaticTable columns={columns} data={data} />
    </section>
  )
}

function OrgChangesSection({ items }: { items: OrgChange[] }) {
  if (!items.length) return null
  const data = items.map((item) => ({
    ...changeRowBase(item),
    role: item.role,
    person_name: item.person_name ?? '—',
    action: item.action,
  }))
  const columns: TableColumn[] = [
    { key: 'competitor_name', label: '竞品' },
    { key: 'role', label: '角色' },
    { key: 'person_name', label: '人员' },
    {
      key: 'action',
      label: '动作',
      render: (row) => (
        <span>
          {s4t(String(row.action), ORG_ACTION)}
          <BaselineBadge isBaseline={Boolean(row.is_baseline)} />
        </span>
      ),
    },
    {
      key: 'severity',
      label: '严重度',
      render: (row) => <SeverityTag severity={row.severity as ChangeSeverity} />,
    },
    {
      key: 'fia',
      label: 'FIA',
      render: (row) => <FiaContent fia={row.fia as FIATuple} />,
    },
  ]
  return (
    <section>
      <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">组织变动</h3>
      <StaticTable columns={columns} data={data} />
    </section>
  )
}

function ThreatMatrixSection({ threats }: { threats: MonitoringThreat[] }) {
  if (!threats.length) return null

  const byQuadrant: Record<MonitoringThreat['quadrant'], MonitoringThreat[]> = {
    act_now: [],
    contingency: [],
    monitor: [],
    deprioritize: [],
  }
  for (const threat of threats) {
    byQuadrant[threat.quadrant]?.push(threat)
  }

  const quadrants: MonitoringThreat['quadrant'][] = [
    'act_now',
    'contingency',
    'monitor',
    'deprioritize',
  ]

  return (
    <section>
      <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">威胁矩阵</h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {quadrants.map((q) => {
          const cfg = QUADRANT_CONFIG[q]
          const items = byQuadrant[q]
          return (
            <div
              key={q}
              className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] p-4 min-h-[120px]"
            >
              <Tag className={`${cfg.tagClass} mb-3`}>{cfg.label}</Tag>
              {items.length === 0 ? (
                <p className="text-[12px] text-[var(--text-tertiary)]">暂无威胁</p>
              ) : (
                <ul className="space-y-3">
                  {items.map((threat) => (
                    <li key={threat.artifact_id} className="space-y-1">
                      <p className="text-[13px] font-semibold text-[var(--text-primary)]">
                        {threat.title}
                      </p>
                      <p className="text-[12px] text-[var(--text-secondary)] leading-relaxed">
                        {threat.description}
                      </p>
                      {threat.recommended_response && (
                        <p className="text-[11px] text-[var(--text-tertiary)]">
                          <span className="font-medium">建议应对：</span>
                          {threat.recommended_response}
                        </p>
                      )}
                    </li>
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

function OpportunitiesSection({ payload }: { payload: S4MonitoringPayload }) {
  const { opportunities } = payload
  if (!opportunities.length) return null

  const data = opportunities.map((o) => ({
    opportunity_type: s4t(o.opportunity_type, OPPORTUNITY_TYPE),
    description: o.description,
    estimated_effort: o.estimated_effort,
    expected_impact: o.expected_impact,
    first_step: o.first_step,
  }))

  return (
    <section>
      <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">机会识别</h3>
      <StaticTable
        columns={[
          { key: 'opportunity_type', label: '类型' },
          { key: 'description', label: '描述' },
          {
            key: 'estimated_effort',
            label: '投入',
            render: (row) => <SeverityTag severity={row.estimated_effort as ChangeSeverity} />,
          },
          {
            key: 'expected_impact',
            label: '影响',
            render: (row) => <SeverityTag severity={row.expected_impact as ChangeSeverity} />,
          },
          { key: 'first_step', label: '第一步' },
        ]}
        data={data}
      />
    </section>
  )
}

function MonitoringActionsSection({ payload }: { payload: S4MonitoringPayload }) {
  const { monitoring_actions } = payload
  if (!monitoring_actions.length) return null

  const data = monitoring_actions.map((a) => ({
    description: a.description,
    owner_team: s4t(a.owner_team, OWNER_TEAM),
    priority_tier: a.priority_tier,
    due_date_estimate: a.due_date_estimate ?? '—',
  }))

  return (
    <section>
      <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">推荐行动</h3>
      <StaticTable
        columns={[
          { key: 'description', label: '描述' },
          { key: 'owner_team', label: '负责团队' },
          {
            key: 'priority_tier',
            label: '优先级',
            render: (row) => (
              <Tag className={priorityTagClass(String(row.priority_tier))}>
                {t(String(row.priority_tier))}
              </Tag>
            ),
          },
          { key: 'due_date_estimate', label: '预计截止' },
        ]}
        data={data}
      />
    </section>
  )
}

function BattlecardItem({ battlecard }: { battlecard: Battlecard }) {
  const completenessClass = COMPLETENESS_TAG[battlecard.overall_completeness]

  return (
    <details className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)]">
      <summary className="flex items-center gap-2 px-4 py-3 cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden">
        <ChevronRight
          size={14}
          strokeWidth={1.5}
          className="text-[var(--text-tertiary)] transition-transform details-open:rotate-90 shrink-0"
        />
        <span className="text-[13px] font-semibold text-[var(--text-primary)]">
          {battlecard.competitor_name}
        </span>
        <Tag className={completenessClass}>
          {COMPLETENESS_LABELS[battlecard.overall_completeness]}
        </Tag>
        {battlecard.last_updated_at && (
          <span className="text-[11px] text-[var(--text-tertiary)] ml-auto">
            更新于 {battlecard.last_updated_at}
          </span>
        )}
      </summary>

      <div className="px-4 pb-4 flex flex-col gap-4 border-t border-[var(--border-divider)] pt-3">
        {battlecard.sections.map((sec) => (
          <div key={sec.section_name}>
            <div className="flex items-center gap-2 mb-1.5">
              <h4 className="text-[13px] font-semibold text-[var(--text-primary)]">
                {BATTLECARD_SECTION_LABELS[sec.section_name]}
              </h4>
              <Tag className={`${COMPLETENESS_TAG[sec.completeness]} text-[10px]`}>
                {COMPLETENESS_LABELS[sec.completeness]}
              </Tag>
            </div>
            {sec.content ? (
              <p className="text-[13px] text-[var(--text-secondary)] leading-relaxed whitespace-pre-wrap">
                {sec.content}
              </p>
            ) : (
              <p className="text-[12px] text-[var(--text-tertiary)]">暂无数据</p>
            )}
          </div>
        ))}
      </div>
    </details>
  )
}

function BattlecardsSection({ battlecards }: { battlecards: Battlecard[] }) {
  if (!battlecards.length) return null

  return (
    <section>
      <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">活体战卡</h3>
      <div className="flex flex-col gap-2">
        {battlecards.map((bc) => (
          <BattlecardItem key={bc.artifact_id} battlecard={bc} />
        ))}
      </div>
    </section>
  )
}

export function S4Payload({ payload }: S4PayloadProps) {
  const {
    review_period,
    trends,
    feature_changes,
    pricing_changes,
    messaging_changes,
    news_events,
    org_changes,
    threats,
    battlecards,
  } = payload

  return (
    <div className="flex flex-col gap-8">
      <section>
        <h3 className="text-[15px] font-semibold text-[var(--text-primary)] mb-3">监控时间窗</h3>
        <ReviewPeriodCard rp={review_period} />
      </section>

      <TrendsSection trends={trends} />

      <FeatureChangesSection items={feature_changes} />
      <PricingChangesSection items={pricing_changes} />
      <MessagingChangesSection items={messaging_changes} />
      <NewsEventsSection items={news_events} />
      <OrgChangesSection items={org_changes} />

      <ThreatMatrixSection threats={threats} />

      <OpportunitiesSection payload={payload} />

      <MonitoringActionsSection payload={payload} />
      <BattlecardsSection battlecards={battlecards} />
    </div>
  )
}
