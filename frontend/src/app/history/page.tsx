'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useTraces } from '@/hooks/useTraces'
import { SCENARIO_LABELS } from '@/types'
import type { Scenario } from '@/types'
import { Loader2, CheckCircle2, XCircle, ExternalLink } from 'lucide-react'

const PAGE_SIZE = 20

const SCENARIO_OPTIONS = ['', 'S1', 'S2', 'S3', 'S4', 'S5'] as const
const STATUS_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 'completed', label: '完成' },
  { value: 'failed', label: '失败' },
  { value: 'running', label: '运行中' },
] as const

export default function HistoryPage() {
  const [page, setPage] = useState(1)
  const [scenarioFilter, setScenarioFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  const filters = {
    scenario: scenarioFilter || undefined,
    status: statusFilter || undefined,
  }
  const { traces, total, isLoading, error } = useTraces(page, PAGE_SIZE, filters)

  const totalPages = Math.ceil(total / PAGE_SIZE)

  const handleScenarioChange = (value: string) => {
    setScenarioFilter(value)
    setPage(1)
  }
  const handleStatusChange = (value: string) => {
    setStatusFilter(value)
    setPage(1)
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-[28px] font-bold text-[var(--text-primary)]">历史记录</h1>
        <p className="mt-1 text-[14px] text-[var(--text-secondary)]">
          共 {total} 条分析记录
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-[13px] text-[var(--text-secondary)]">
          场景
          <select
            value={scenarioFilter}
            onChange={(e) => handleScenarioChange(e.target.value)}
            className="px-2 py-1.5 rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] text-[var(--text-primary)] text-[13px]"
          >
            <option value="">全部场景</option>
            {SCENARIO_OPTIONS.filter(Boolean).map((s) => (
              <option key={s} value={s}>
                {s} · {SCENARIO_LABELS[s as Scenario]}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-[13px] text-[var(--text-secondary)]">
          状态
          <select
            value={statusFilter}
            onChange={(e) => handleStatusChange(e.target.value)}
            className="px-2 py-1.5 rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] text-[var(--text-primary)] text-[13px]"
          >
            {STATUS_OPTIONS.map(({ value, label }) => (
              <option key={value || 'all'} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 size={24} className="animate-spin text-[var(--text-tertiary)]" />
        </div>
      ) : error ? (
        <div className="rounded-[var(--radius-md)] border border-[var(--danger)] bg-[var(--tag-red)] p-4 text-center">
          <p className="text-[13px] text-[var(--tag-red-text)]">
            {error instanceof Error ? error.message : '加载失败'}
          </p>
        </div>
      ) : traces.length === 0 ? (
        <div className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] p-12 text-center">
          <p className="text-[14px] text-[var(--text-tertiary)]">暂无分析记录</p>
          <Link
            href="/"
            className="inline-block mt-3 text-[13px] text-[var(--info)] hover:underline"
          >
            创建第一个分析 →
          </Link>
        </div>
      ) : (
        <div className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] overflow-x-auto">
          <table className="w-full min-w-[980px] table-fixed text-[13px]">
            <colgroup>
              <col className="w-[190px]" />
              <col className="w-[150px]" />
              <col className="w-[110px]" />
              <col />
              <col className="w-[180px]" />
              <col className="w-[92px]" />
            </colgroup>
            <thead>
              <tr className="bg-[var(--bg-page)]">
                <th className="text-left font-medium text-[var(--text-secondary)] px-4 py-2.5 border-b border-[var(--border)] text-[12px] uppercase tracking-wider">Trace ID</th>
                <th className="text-left font-medium text-[var(--text-secondary)] px-4 py-2.5 border-b border-[var(--border)] text-[12px] uppercase tracking-wider">场景</th>
                <th className="text-left font-medium text-[var(--text-secondary)] px-4 py-2.5 border-b border-[var(--border)] text-[12px] uppercase tracking-wider">状态</th>
                <th className="text-left font-medium text-[var(--text-secondary)] px-4 py-2.5 border-b border-[var(--border)] text-[12px] uppercase tracking-wider">竞品</th>
                <th className="text-left font-medium text-[var(--text-secondary)] px-4 py-2.5 border-b border-[var(--border)] text-[12px] uppercase tracking-wider">时间</th>
                <th className="px-4 py-2.5 border-b border-[var(--border)]" />
              </tr>
            </thead>
            <tbody>
              {traces.map((trace) => (
                <tr key={trace.trace_id} className="hover:bg-[var(--bg-hover)] transition-colors">
                  <td className="px-4 py-3 border-b border-[var(--border-divider)] font-[family-name:var(--font-mono)] text-[12px] text-[var(--text-secondary)] whitespace-nowrap">
                    {trace.trace_id}
                  </td>
                  <td className="px-4 py-3 border-b border-[var(--border-divider)]">
                    {trace.scenario ? (
                      <span className="tag-blue inline-flex whitespace-nowrap text-[12px] font-medium px-2 py-0.5 rounded-[var(--radius-sm)]">
                        {trace.scenario} · {SCENARIO_LABELS[trace.scenario as Scenario] ?? ''}
                      </span>
                    ) : '—'}
                  </td>
                  <td className="px-4 py-3 border-b border-[var(--border-divider)]">
                    <StatusBadge status={trace.status} />
                  </td>
                  <td className="px-4 py-3 border-b border-[var(--border-divider)] text-[var(--text-secondary)] truncate" title={trace.competitors?.join(', ') || undefined}>
                    {trace.competitors?.length > 0 ? trace.competitors.join(', ') : '—'}
                  </td>
                  <td className="px-4 py-3 border-b border-[var(--border-divider)] text-[12px] text-[var(--text-tertiary)] whitespace-nowrap">
                    {trace.started_at ? new Date(trace.started_at).toLocaleString('zh-CN', { hour12: false }) : '—'}
                  </td>
                  <td className="px-4 py-3 border-b border-[var(--border-divider)] text-right">
                    <Link
                      href={`/analyze/${trace.trace_id}`}
                      className="inline-flex items-center gap-1 text-[12px] text-[var(--info)] hover:underline"
                    >
                      查看 <ExternalLink size={11} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1.5 text-[13px] rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] disabled:opacity-40 transition-colors"
          >
            上一页
          </button>
          <span className="text-[13px] text-[var(--text-tertiary)]">
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="px-3 py-1.5 text-[13px] rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] disabled:opacity-40 transition-colors"
          >
            下一页
          </button>
        </div>
      )}
    </div>
  )
}

function StatusBadge({ status }: { status?: string | null }) {
  if (status === 'completed') {
    return (
      <span className="inline-flex items-center gap-1 text-[12px] font-medium text-[var(--tag-green-text)]">
        <CheckCircle2 size={13} /> 完成
      </span>
    )
  }
  if (status === 'failed') {
    return (
      <span className="inline-flex items-center gap-1 text-[12px] font-medium text-[var(--tag-red-text)]">
        <XCircle size={13} /> 失败
      </span>
    )
  }
  if (status === 'running') {
    return (
      <span
        title="该记录的 meta.json 仍标记为 running；通常是历史任务执行时前端断连或进程中断，未写入 completed/failed 终态。"
        className="inline-flex items-center gap-1 whitespace-nowrap text-[12px] font-medium text-[var(--tag-blue-text)]"
      >
        <Loader2 size={13} className="animate-spin" /> 运行中
      </span>
    )
  }
  return <span className="text-[12px] text-[var(--text-tertiary)]">{status ?? '—'}</span>
}
