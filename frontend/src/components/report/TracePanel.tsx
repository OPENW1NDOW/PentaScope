'use client'

import { useState } from 'react'
import type { TraceResponse } from '@/types'
import { ChevronRight } from 'lucide-react'

type TabId = 'profiles' | 'analysis' | 'report' | 'feedback' | 'log' | 'snapshots'

const TABS: { id: TabId; label: string }[] = [
  { id: 'profiles', label: '采集产物' },
  { id: 'analysis', label: '分析产物' },
  { id: 'report', label: '报告产物' },
  { id: 'feedback', label: '质检反馈' },
  { id: 'log', label: '运行日志' },
  { id: 'snapshots', label: '重试快照' },
]

export function TracePanel({ trace }: { trace: TraceResponse }) {
  const [activeTab, setActiveTab] = useState<TabId>('profiles')

  const retryCount = trace.meta?.retry_count
  const showRetryCount = typeof retryCount === 'number'

  return (
    <details className="rounded-[var(--radius-lg)] border border-[var(--border-default)] bg-[var(--bg-surface)]">
      <summary className="flex items-center gap-2 px-4 py-3 cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden">
        <ChevronRight
          size={14}
          strokeWidth={1.5}
          className="text-[var(--text-tertiary)] transition-transform details-open:rotate-90"
        />
        <span className="text-[13px] font-semibold text-[var(--text-primary)]">
          执行追溯
        </span>
      </summary>

      <div className="px-4 pb-4 flex flex-col gap-3 border-t border-[var(--border-divider)] pt-3">
        {showRetryCount && (
          <p className="text-[12px] text-[var(--text-secondary)]">
            反馈闭环重试次数:{' '}
            <span className="font-[family-name:var(--font-mono)] text-[var(--text-primary)]">
              {retryCount}
            </span>
          </p>
        )}

        <div className="flex flex-wrap gap-1">
          {TABS.map(({ id, label }) => (
            <button
              key={id}
              type="button"
              onClick={() => setActiveTab(id)}
              className={`rounded-[var(--radius-md)] px-2.5 py-1.5 text-[12px] transition-colors ${
                activeTab === id
                  ? 'bg-[var(--bg-hover)] text-[var(--text-primary)] font-medium'
                  : 'text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="min-h-[80px]">
          {activeTab === 'profiles' && <JsonView data={trace.stages.profiles} />}
          {activeTab === 'analysis' && <JsonView data={trace.stages.analysis} />}
          {activeTab === 'report' && <JsonView data={trace.stages.report} />}
          {activeTab === 'feedback' && <JsonView data={trace.stages.feedback} />}
          {activeTab === 'log' && <LogView log={trace.log} />}
          {activeTab === 'snapshots' && <SnapshotsView snapshots={trace.snapshots} />}
        </div>
      </div>
    </details>
  )
}

function JsonView({ data }: { data: unknown }) {
  if (data == null) {
    return (
      <p className="text-[13px] text-[var(--text-tertiary)]">该阶段无产物</p>
    )
  }

  return (
    <pre className="text-[12px] font-[family-name:var(--font-mono)] max-h-[400px] overflow-auto rounded-[var(--radius-lg)] bg-[var(--bg-hover)] p-3 text-[var(--text-secondary)] whitespace-pre-wrap break-words">
      {JSON.stringify(data, null, 2)}
    </pre>
  )
}

function LogView({ log }: { log: string }) {
  if (!log) {
    return (
      <p className="text-[13px] text-[var(--text-tertiary)]">无日志</p>
    )
  }

  return (
    <pre className="text-[12px] font-[family-name:var(--font-mono)] max-h-[400px] overflow-y-auto rounded-[var(--radius-lg)] bg-[var(--bg-hover)] p-3 text-[var(--text-secondary)] whitespace-pre-wrap break-words">
      {log}
    </pre>
  )
}

function SnapshotsView({ snapshots }: { snapshots: string[] }) {
  if (!snapshots.length) {
    return (
      <p className="text-[13px] text-[var(--text-tertiary)]">
        无重试快照——一次通过
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      <p className="text-[12px] text-[var(--text-tertiary)]">
        反馈闭环重试时的历史版本，可通过 API ?version= 查看
      </p>
      <ul className="flex flex-col gap-1">
        {snapshots.map((name) => (
          <li
            key={name}
            className="text-[12px] font-[family-name:var(--font-mono)] text-[var(--text-secondary)] rounded-[var(--radius-md)] bg-[var(--bg-hover)] px-2.5 py-1.5"
          >
            {name}
          </li>
        ))}
      </ul>
    </div>
  )
}
