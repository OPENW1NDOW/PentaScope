'use client'

import { use, useEffect, useState, useCallback } from 'react'
import { api } from '@/lib/api'
import type { BaseReport } from '@/types'
import { useSSE } from '@/hooks/useSSE'
import {
  ReportHeader,
  KpiStrip,
  AtAGlance,
  ExecutiveSummary,
  KeyFindings,
  SwotGrid,
  Recommendations,
  ScopeMethodology,
  Appendix,
  MetadataPanel,
  ScenarioPayload,
} from '@/components/report'
import { Loader2, AlertTriangle, RefreshCw } from 'lucide-react'

interface TraceData {
  trace_id: string
  meta?: {
    status?: string
    started_at?: string
    ended_at?: string
    input?: {
      scenario?: string
      competitors?: { name: string }[]
    }
  } | null
  stages?: {
    report?: BaseReport | null
  }
  log?: string
}

export default function AnalyzePage({
  params,
}: {
  params: Promise<{ traceId: string }>
}) {
  const { traceId } = use(params)
  const [trace, setTrace] = useState<TraceData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchTrace = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const res = await api.getTrace(traceId)
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || `HTTP ${res.status}`)
      }
      const data = await res.json()
      setTrace(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load trace')
    } finally {
      setLoading(false)
    }
  }, [traceId])

  useEffect(() => {
    fetchTrace()
  }, [fetchTrace])

  // SSE for live progress when status is running
  const sse = useSSE(
    trace?.meta?.status === 'running' ? traceId : null
  )

  // Refetch when SSE signals completion
  useEffect(() => {
    if (sse.status === 'disconnected' && trace?.meta?.status === 'running') {
      fetchTrace()
    }
  }, [sse.status, trace?.meta?.status, fetchTrace])

  const status = trace?.meta?.status ?? 'unknown'
  const report = trace?.stages?.report

  // ── Loading ──────────────────────────────────────────────
  if (loading) {
    return <LoadingState />
  }

  // ── Error ────────────────────────────────────────────────
  if (error) {
    return <ErrorState message={error} onRetry={fetchTrace} />
  }

  // ── Running (SSE streaming) ──────────────────────────────
  if (status === 'running') {
    return <RunningState traceId={traceId} sse={sse} />
  }

  // ── Failed ───────────────────────────────────────────────
  if (status === 'failed') {
    return (
      <ErrorState
        message={trace?.meta && 'error' in trace.meta ? String((trace.meta as Record<string, unknown>).error) : '分析失败'}
        traceId={traceId}
      />
    )
  }

  // ── Completed ────────────────────────────────────────────
  if (!report) {
    return (
      <ErrorState
        message="报告数据缺失"
        traceId={traceId}
      />
    )
  }

  return <ReportView report={report} />
}

// ============================================================
// Sub-components
// ============================================================

function LoadingState() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
      <Loader2 size={32} className="animate-spin text-[var(--text-tertiary)]" />
      <p className="text-[14px] text-[var(--text-secondary)]">
        加载分析数据...
      </p>
    </div>
  )
}

function ErrorState({
  message,
  traceId,
  onRetry,
}: {
  message: string
  traceId?: string
  onRetry?: () => void
}) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
      <AlertTriangle size={32} className="text-[var(--danger)]" />
      <p className="text-[14px] text-[var(--text-primary)] font-medium">
        加载失败
      </p>
      <p className="text-[13px] text-[var(--text-secondary)] max-w-[400px] text-center">
        {message}
      </p>
      <div className="flex gap-2 mt-2">
        {onRetry && (
          <button
            onClick={onRetry}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[13px] font-medium rounded-[var(--radius-md)] border border-[var(--border-default)] bg-[var(--bg-surface)] text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition-colors"
          >
            <RefreshCw size={13} />
            重试
          </button>
        )}
        {traceId && (
          <a
            href="/"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[13px] font-medium rounded-[var(--radius-md)] border border-[var(--border-default)] bg-[var(--bg-surface)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition-colors"
          >
            返回首页
          </a>
        )}
      </div>
    </div>
  )
}

function RunningState({
  traceId,
  sse,
}: {
  traceId: string
  sse: ReturnType<typeof useSSE>
}) {
  const nodeLabels: Record<string, string> = {
    set_entry: '场景路由',
    recommender: '竞品推荐',
    collector: '信息采集',
    analyzer: '竞品分析',
    writer: '报告撰写',
    inspector: '质检审核',
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-[28px] font-semibold text-[var(--text-primary)]">
          分析进行中
        </h1>
        <p className="mt-1 text-[13px] text-[var(--text-tertiary)] font-[var(--font-mono)]">
          {traceId}
        </p>
      </div>

      {/* Progress */}
      <div className="rounded-[var(--radius-lg)] border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 flex flex-col gap-4">
        <div className="flex items-center gap-2">
          <Loader2 size={16} className="animate-spin text-[var(--info)]" />
          <span className="text-[14px] font-medium text-[var(--text-primary)]">
            {sse.currentNode
              ? `${nodeLabels[sse.currentNode] ?? sse.currentNode} 执行中...`
              : sse.status === 'connecting'
                ? '正在连接...'
                : '等待节点调度...'}
          </span>
        </div>

        {/* Completed nodes */}
        {sse.completedNodes.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {sse.completedNodes.map((node, i) => (
              <span
                key={`${node}-${i}`}
                className="tag-green text-[12px] font-medium px-2 py-0.5 rounded-[var(--radius-sm)]"
              >
                {nodeLabels[node] ?? node}
              </span>
            ))}
          </div>
        )}

        {sse.error && (
          <p className="text-[13px] text-[var(--danger)]">
            {sse.error}
          </p>
        )}
      </div>

      {/* Live log */}
      {sse.logs.length > 0 && (
        <details className="rounded-[var(--radius-lg)] border border-[var(--border-default)] bg-[var(--bg-surface)]">
          <summary className="px-4 py-3 text-[13px] font-semibold text-[var(--text-primary)] cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden">
            实时日志 ({sse.logs.length})
          </summary>
          <div className="px-4 pb-4 border-t border-[var(--border-divider)]">
            <pre className="text-[12px] font-[var(--font-mono)] text-[var(--text-secondary)] max-h-[300px] overflow-y-auto whitespace-pre-wrap pt-3">
              {sse.logs.map((log, i) => (
                <div key={i}>
                  <span className="text-[var(--text-tertiary)]">[{log.event}]</span>{' '}
                  {JSON.stringify(log.data)}
                </div>
              ))}
            </pre>
          </div>
        </details>
      )}
    </div>
  )
}

function ReportView({ report }: { report: BaseReport }) {
  const scenario = report.metadata.scenario

  return (
    <div className="flex flex-col gap-8">
      {/* Header */}
      <ReportHeader
        title={report.title}
        subtitle={report.subtitle}
        metadata={report.metadata}
      />

      {/* KPI Strip */}
      <KpiStrip metadata={report.metadata} />

      {/* At a Glance */}
      <AtAGlance items={report.at_a_glance} />

      {/* Executive Summary */}
      <ExecutiveSummary summary={report.executive_summary} />

      {/* Key Findings */}
      <KeyFindings findings={report.key_findings} />

      {/* SWOT */}
      <SwotGrid swot={report.swot} />

      {/* Analysis sections */}
      {report.analysis_sections.length > 0 && (
        <AnalysisSections sections={report.analysis_sections} />
      )}

      {/* Conclusions */}
      <MarkdownSection title="结论" content={report.conclusions} />

      {/* Background */}
      <MarkdownSection title="背景" content={report.background} />

      {/* Recommendations */}
      <Recommendations recommendations={report.recommendations} />

      {/* Scope & Methodology */}
      <ScopeMethodology
        scope={report.scope}
        methodology={report.methodology}
      />

      {/* Scenario-specific payload */}
      <ScenarioPayload
        payload={report.scenario_payload}
        scenario={scenario}
      />

      {/* Appendix */}
      {report.appendix && <Appendix appendix={report.appendix} />}

      {/* Metadata Panel */}
      <MetadataPanel metadata={report.metadata} />
    </div>
  )
}

function AnalysisSections({
  sections,
}: {
  sections: { heading: string; narrative: string; section_id: string }[]
}) {
  return (
    <div className="flex flex-col gap-6">
      <h3 className="text-[15px] font-semibold text-[var(--text-primary)]">
        详细分析
      </h3>
      <div className="flex flex-col gap-6">
        {sections.map((section, i) => (
          <div key={section.section_id || i} className="flex flex-col gap-2">
            <h4 className="text-[14px] font-semibold text-[var(--text-primary)] border-b border-[var(--border-divider)] pb-2">
              {section.heading}
            </h4>
            <div className="text-[14px] leading-relaxed text-[var(--text-secondary)] whitespace-pre-wrap">
              {section.narrative}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function MarkdownSection({
  title,
  content,
}: {
  title: string
  content: string
}) {
  if (!content) return null

  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-[15px] font-semibold text-[var(--text-primary)]">
        {title}
      </h3>
      <div className="text-[14px] leading-relaxed text-[var(--text-secondary)] whitespace-pre-wrap">
        {content}
      </div>
    </div>
  )
}
