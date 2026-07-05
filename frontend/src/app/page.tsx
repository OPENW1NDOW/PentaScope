'use client'

import { useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import { SCENARIO_LABELS } from '@/types'
import type { Scenario, AnalysisRequest, PickScenarioResponse, CompetitorBasic } from '@/types'
import { Loader2, Sparkles, ChevronRight } from 'lucide-react'

const SCENARIOS: { key: Scenario; desc: string }[] = [
  { key: 'S1', desc: '对比竞品功能矩阵，发现差异化机会' },
  { key: 'S2', desc: '评估市场规模、竞争格局和进入策略' },
  { key: 'S3', desc: '分析竞品定价，制定最优定价策略' },
  { key: 'S4', desc: '持续追踪竞品变化，及时发现威胁和机会' },
  { key: 'S5', desc: '绘制感知地图，找到独特定位' },
]

export default function HomePage() {
  const router = useRouter()
  const [scenario, setScenario] = useState<Scenario | null>(null)
  const [analysisContext, setAnalysisContext] = useState('')
  const [ourProductName, setOurProductName] = useState('')
  const [ourProductBrief, setOurProductBrief] = useState('')
  const [competitorNames, setCompetitorNames] = useState('')
  const [industry, setIndustry] = useState('')
  const [priorTraceId, setPriorTraceId] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isPicking, setIsPicking] = useState(false)
  const [pickResult, setPickResult] = useState<PickScenarioResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handlePickScenario = useCallback(async () => {
    if (!analysisContext.trim()) return
    setIsPicking(true)
    setPickResult(null)
    try {
      const data = await api.pickScenario(analysisContext)
      setPickResult(data)
      setScenario(data.scenario as Scenario)
    } catch (e) {
      setError(e instanceof Error ? e.message : '推荐失败')
    } finally {
      setIsPicking(false)
    }
  }, [analysisContext])

  const handleSubmit = useCallback(async () => {
    if (!scenario || !analysisContext.trim()) return
    setIsSubmitting(true)
    setError(null)

    const competitors: CompetitorBasic[] = competitorNames
      .split('\n')
      .map((s) => s.trim())
      .filter(Boolean)
      .map((name) => ({ name }))

    const body: AnalysisRequest = {
      scenario,
      analysis_context: analysisContext,
      competitors: competitors.length > 0 ? competitors : undefined,
      our_product_name: ourProductName || undefined,
      our_product_brief: ourProductBrief || undefined,
      industry: scenario === 'S2' ? industry || undefined : undefined,
      prior_trace_id: scenario === 'S4' ? priorTraceId || undefined : undefined,
    }

    try {
      const data = await api.analyze(body)
      router.push(`/analyze/${data.trace_id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : '提交失败')
    } finally {
      setIsSubmitting(false)
    }
  }, [scenario, analysisContext, competitorNames, ourProductName, ourProductBrief, industry, priorTraceId, router])

  const hasCompetitors = competitorNames
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean).length > 0
  const needsCompetitors = scenario && scenario !== 'S2'
  const needsIndustry = scenario === 'S2'
  const needsPriorTrace = scenario === 'S4'
  const canSubmit = Boolean(
    scenario &&
    analysisContext.trim() &&
    (scenario === 'S2' ? industry.trim() : ourProductName.trim() && hasCompetitors)
  )

  return (
    <div className="flex flex-col gap-8 max-w-[640px] mx-auto">
      {/* Hero */}
      <div>
        <h1 className="text-[28px] font-bold text-[var(--text-primary)] leading-tight">
          AI 竞品分析
        </h1>
        <p className="mt-2 text-[15px] text-[var(--text-secondary)] leading-relaxed">
          选择分析场景，描述你的需求，AI 将自动采集、分析并生成结构化竞品报告。
        </p>
      </div>

      {/* Analysis Context */}
      <div className="flex flex-col gap-2">
        <label className="text-[13px] font-medium text-[var(--text-primary)]">
          分析意图 <span className="text-[var(--danger)]">*</span>
        </label>
        <textarea
          value={analysisContext}
          onChange={(e) => setAnalysisContext(e.target.value)}
          placeholder="描述你想要分析的内容，例如：我想了解飞书文档与 Notion、Confluence 的功能差异..."
          className="min-h-[100px] px-3 py-2 text-[14px] rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:border-[var(--border-active)] resize-y"
        />
        <button
          onClick={handlePickScenario}
          disabled={!analysisContext.trim() || isPicking}
          className="self-start inline-flex items-center gap-1.5 px-3 py-1.5 text-[13px] font-medium rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition-colors disabled:opacity-50"
        >
          {isPicking ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
          AI 帮我选场景
        </button>
        {pickResult && (
          <div className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--info-bg, var(--tag-blue))] p-3">
            <p className="text-[13px] text-[var(--tag-blue-text)]">
              推荐场景：<strong>{SCENARIO_LABELS[pickResult.scenario as Scenario] ?? pickResult.scenario}</strong>
              （置信度：{pickResult.confidence}）
            </p>
            <p className="text-[12px] text-[var(--tag-blue-text)] mt-1 opacity-80">{pickResult.rationale}</p>
          </div>
        )}
      </div>

      {/* Scenario Selection */}
      <div className="flex flex-col gap-2">
        <label className="text-[13px] font-medium text-[var(--text-primary)]">
          分析场景 <span className="text-[var(--danger)]">*</span>
        </label>
        <div className="grid grid-cols-1 gap-2">
          {SCENARIOS.map((s) => (
            <button
              key={s.key}
              onClick={() => setScenario(s.key)}
              className={`flex items-center justify-between px-4 py-3 rounded-[var(--radius-md)] border text-left transition-colors ${
                scenario === s.key
                  ? 'border-[var(--border-active)] bg-[var(--bg-selected)]'
                  : 'border-[var(--border)] bg-[var(--bg-surface)] hover:bg-[var(--bg-hover)]'
              }`}
            >
              <div>
                <span className="text-[14px] font-medium text-[var(--text-primary)]">
                  {s.key} · {SCENARIO_LABELS[s.key]}
                </span>
                <p className="text-[12px] text-[var(--text-tertiary)] mt-0.5">{s.desc}</p>
              </div>
              {scenario === s.key && <ChevronRight size={16} className="text-[var(--border-active)]" />}
            </button>
          ))}
        </div>
      </div>

      {/* Conditional Fields */}
      {scenario && (
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <label className="text-[13px] font-medium text-[var(--text-primary)]">
              竞品名称 <span className="text-[var(--text-tertiary)]">({scenario === 'S2' ? '可选，' : ''}每行一个)</span>
              {needsCompetitors && <span className="text-[var(--danger)]"> *</span>}
            </label>
            <textarea
              value={competitorNames}
              onChange={(e) => setCompetitorNames(e.target.value)}
              placeholder={'Notion\nConfluence\n飞书文档'}
              className="min-h-[80px] px-3 py-2 text-[14px] rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:border-[var(--border-active)] resize-y"
            />
          </div>

          {scenario !== 'S2' && (
            <>
              <div className="flex flex-col gap-2">
                <label className="text-[13px] font-medium text-[var(--text-primary)]">
                  我方产品名称 <span className="text-[var(--danger)]">*</span>
                </label>
                <input
                  type="text"
                  value={ourProductName}
                  onChange={(e) => setOurProductName(e.target.value)}
                  placeholder="例如：飞书文档"
                  className="px-3 py-2 text-[14px] rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:border-[var(--border-active)]"
                />
              </div>

              <div className="flex flex-col gap-2">
                <label className="text-[13px] font-medium text-[var(--text-primary)]">
                  产品简介 <span className="text-[var(--text-tertiary)]">(可选)</span>
                </label>
                <textarea
                  value={ourProductBrief}
                  onChange={(e) => setOurProductBrief(e.target.value)}
                  placeholder="简要描述你的产品..."
                  className="min-h-[60px] px-3 py-2 text-[14px] rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:border-[var(--border-active)] resize-y"
                />
              </div>
            </>
          )}

          {needsIndustry && (
            <div className="flex flex-col gap-2">
              <label className="text-[13px] font-medium text-[var(--text-primary)]">
                行业/赛道 <span className="text-[var(--danger)]">*</span>
              </label>
              <input
                type="text"
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                placeholder="例如：协作办公"
                className="px-3 py-2 text-[14px] rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:border-[var(--border-active)]"
              />
            </div>
          )}

          {needsPriorTrace && (
            <div className="flex flex-col gap-2">
              <label className="text-[13px] font-medium text-[var(--text-primary)]">
                上次分析 Trace ID <span className="text-[var(--text-tertiary)]">(可选，用于增量监控)</span>
              </label>
              <input
                type="text"
                value={priorTraceId}
                onChange={(e) => setPriorTraceId(e.target.value)}
                placeholder="例如：20260625-143052-a1b2c3"
                className="px-3 py-2 text-[13px] font-[family-name:var(--font-mono)] rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:border-[var(--border-active)]"
              />
            </div>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-[var(--radius-md)] border border-[var(--danger)] bg-[var(--tag-red)] p-3">
          <p className="text-[13px] text-[var(--tag-red-text)]">{error}</p>
        </div>
      )}

      {/* Submit */}
      <button
        onClick={handleSubmit}
        disabled={!canSubmit || isSubmitting}
        className="self-start inline-flex items-center gap-2 px-5 py-2.5 text-[14px] font-semibold rounded-[var(--radius-md)] bg-[var(--text-primary)] text-[var(--bg-surface)] hover:opacity-90 transition-opacity disabled:opacity-40"
      >
        {isSubmitting ? <Loader2 size={16} className="animate-spin" /> : null}
        {isSubmitting ? '提交中...' : '开始分析'}
      </button>
    </div>
  )
}
