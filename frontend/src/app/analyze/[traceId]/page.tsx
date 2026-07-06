'use client'

import Link from 'next/link'
import { use, useEffect, useState, useCallback } from 'react'
import { api } from '@/lib/api'
import { NODE_LABELS } from '@/lib/constants'
import { parseRunLogProgress } from '@/lib/runLogProgress'
import type { BaseReport, TraceResponse } from '@/types'
import { useSSE } from '@/hooks/useSSE'
import { PipelineStepper } from '@/components/analysis/PipelineStepper'
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
  MarkdownContent,
  AnalysisSections,
  TracePanel,
  ReportToc,
  buildReportToc,
  SectionWrap,
} from '@/components/report'
import { Loader2, AlertTriangle, RefreshCw } from 'lucide-react'

export default function AnalyzePage({
  params,
}: {
  params: Promise<{ traceId: string }>
}) {
  const { traceId } = use(params)
  const [trace, setTrace] = useState<TraceResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchTrace = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await api.getTrace(traceId)
      setTrace(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load trace')
    } finally {
      setLoading(false)
    }
  }, [traceId])

  useEffect(() => {
    void Promise.resolve().then(fetchTrace)
  }, [fetchTrace])

  // SSE for live progress when status is running
  const sse = useSSE(
    trace?.meta?.status === 'running' ? traceId : null
  )

  // Refetch when SSE signals completion
  useEffect(() => {
    if (sse.status === 'disconnected' && trace?.meta?.status === 'running') {
      void Promise.resolve().then(fetchTrace)
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
    return (
      <RunningState
        traceId={traceId}
        sse={sse}
        scenario={trace?.meta?.input?.scenario}
        runLog={trace?.log ?? ''}
        onRefresh={fetchTrace}
      />
    )
  }

  // ── Failed ───────────────────────────────────────────────
  if (status === 'failed') {
    return (
      <ErrorState
        message={trace?.meta?.error ?? '分析失败'}
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

  return <ReportView report={report} trace={trace} traceId={traceId} />
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
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[13px] font-medium rounded-[var(--radius-md)] border border-[var(--border-default)] bg-[var(--bg-surface)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition-colors"
          >
            返回首页
          </Link>
        )}
      </div>
    </div>
  )
}

function RunningState({
  traceId,
  sse,
  scenario,
  runLog,
  onRefresh,
}: {
  traceId: string
  sse: ReturnType<typeof useSSE>
  scenario?: string
  runLog?: string
  onRefresh?: () => void
}) {
  useEffect(() => {
    if (!onRefresh) return
    const id = setInterval(() => onRefresh(), 5000)
    return () => clearInterval(id)
  }, [onRefresh])

  const logProgress = parseRunLogProgress(runLog ?? '')
  const currentNode = sse.currentNode ?? logProgress.currentNode
  const completedNodes =
    sse.completedNodes.length > 0 ? sse.completedNodes : logProgress.completedNodes
  const progressSource = sse.currentNode ? 'sse' : logProgress.currentNode ? 'log' : null

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-[28px] font-semibold text-[var(--text-primary)]">
          分析进行中
        </h1>
        <p className="mt-1 text-[13px] text-[var(--text-tertiary)] font-[family-name:var(--font-mono)]">
          {traceId}
        </p>
      </div>

      {/* Progress */}
      <div className="rounded-[var(--radius-lg)] border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 flex flex-col gap-4">
        <div className="flex items-center gap-2">
          <Loader2 size={16} className="animate-spin text-[var(--info)]" />
          <span className="text-[14px] font-medium text-[var(--text-primary)]">
            {currentNode
              ? `${NODE_LABELS[currentNode] ?? currentNode} 执行中...`
              : sse.status === 'connecting'
                ? '正在连接...'
                : progressSource === null
                  ? '等待节点调度...'
                  : '正在同步进度...'}
          </span>
        </div>

        {/* Pipeline stepper */}
        <PipelineStepper
          scenario={scenario}
          currentNode={currentNode}
          completedNodes={completedNodes}
        />

        {sse.error && (
          <div className="flex items-center gap-3">
            <p className="text-[13px] text-[var(--danger)]">
              {sse.error}
            </p>
            {onRefresh && (
              <button
                onClick={onRefresh}
                className="inline-flex items-center gap-1.5 px-3 py-1 text-[12px] font-medium rounded-[var(--radius-md)] border border-[var(--border-default)] bg-[var(--bg-surface)] text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition-colors"
              >
                <RefreshCw size={12} />
                刷新状态
              </button>
            )}
          </div>
        )}
      </div>

      {/* Live log */}
      {sse.logs.length > 0 && (
        <details className="rounded-[var(--radius-lg)] border border-[var(--border-default)] bg-[var(--bg-surface)]">
          <summary className="px-4 py-3 text-[13px] font-semibold text-[var(--text-primary)] cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden">
            实时日志 ({sse.logs.length})
          </summary>
          <div className="px-4 pb-4 border-t border-[var(--border-divider)]">
            <div className="text-[12px] font-[family-name:var(--font-mono)] text-[var(--text-secondary)] max-h-[300px] overflow-y-auto pt-3 flex flex-col gap-1">
              {sse.logs.map((log, i) => (
                <div key={i} className="flex items-baseline gap-2">
                  <span className="text-[var(--text-tertiary)] shrink-0">[{log.event}]</span>
                  <span>{formatSSELog(log)}</span>
                </div>
              ))}
            </div>
          </div>
        </details>
      )}
    </div>
  )
}

/** SSE 事件日志 → 人类可读文本 */
function formatSSELog(log: { event: string; data: Record<string, unknown> }): string {
  const node = typeof log.data.node === 'string' ? (NODE_LABELS[log.data.node] ?? log.data.node) : ''
  switch (log.event) {
    case 'node_start':
      return `${node} 开始${typeof log.data.message === 'string' ? ` — ${log.data.message}` : ''}`
    case 'node_complete': {
      const ms = typeof log.data.duration_ms === 'number' ? ` (${(log.data.duration_ms / 1000).toFixed(1)}s)` : ''
      return `${node} 完成${ms}`
    }
    case 'node_error':
      return `${node} 失败 — ${typeof log.data.error === 'string' ? log.data.error : '未知错误'}`
    case 'analysis_complete':
      return '分析完成'
    case 'analysis_failed':
      return `分析失败 — ${typeof log.data.error === 'string' ? log.data.error : '未知错误'}`
    default:
      return JSON.stringify(log.data)
  }
}

function ReportView({
  report,
  trace,
  traceId,
}: {
  report: BaseReport
  trace: TraceResponse
  traceId: string
}) {
  const scenario = report.metadata.scenario
  const exportUrls = {
    md: api.exportUrl(traceId, 'md'),
    html: api.exportUrl(traceId, 'html'),
  }
  const tocItems = buildReportToc(report)

  return (
    <div className="flex gap-8 xl:gap-10">
      <ReportToc items={tocItems} />
      <div className="flex-1 min-w-0 flex flex-col gap-8">
        <SectionWrap id="report-header">
          <ReportHeader
            title={report.title}
            subtitle={report.subtitle}
            metadata={report.metadata}
            exportUrls={exportUrls}
          />
        </SectionWrap>

        <SectionWrap id="kpi">
          <KpiStrip metadata={report.metadata} />
        </SectionWrap>

        <SectionWrap id="at-a-glance">
          <AtAGlance items={report.at_a_glance} />
        </SectionWrap>

        <SectionWrap id="executive-summary">
          <ExecutiveSummary summary={report.executive_summary} />
        </SectionWrap>

        {report.background && (
          <SectionWrap id="background">
            <MarkdownSection title="背景" content={report.background} />
          </SectionWrap>
        )}

        <SectionWrap id="scope">
          <ScopeMethodology scope={report.scope} methodology={report.methodology} />
        </SectionWrap>

        <SectionWrap id="key-findings">
          <KeyFindings findings={report.key_findings} />
        </SectionWrap>

        {report.analysis_sections.length > 0 && (
          <SectionWrap id="analysis">
            <AnalysisSections sections={report.analysis_sections} />
          </SectionWrap>
        )}

        <SectionWrap id="scenario">
          <ScenarioPayload payload={report.scenario_payload} scenario={scenario} />
        </SectionWrap>

        <SectionWrap id="swot">
          <SwotGrid swot={report.swot} />
        </SectionWrap>

        {report.conclusions && (
          <SectionWrap id="conclusions">
            <MarkdownSection title="结论" content={report.conclusions} />
          </SectionWrap>
        )}

        <SectionWrap id="recommendations">
          <Recommendations recommendations={report.recommendations} />
        </SectionWrap>

        {report.appendix && (
          <SectionWrap id="appendix">
            <Appendix appendix={report.appendix} dataSources={report.metadata.data_sources} />
          </SectionWrap>
        )}

        <SectionWrap id="metadata">
          <MetadataPanel metadata={report.metadata} />
        </SectionWrap>

        <SectionWrap id="trace">
          <TracePanel trace={trace} />
        </SectionWrap>
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
    <div className="rounded-[var(--radius-lg)] border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 flex flex-col gap-4">
      <h3 className="text-[15px] font-semibold text-[var(--text-primary)]">
        {title}
      </h3>
      <MarkdownContent content={content} />
    </div>
  )
}
