'use client'

import { useEffect } from 'react'
import Link from 'next/link'
import { AlertTriangle, RefreshCw } from 'lucide-react'

export default function ErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error('[error-boundary]', error)
  }, [error])

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
      <AlertTriangle size={32} className="text-[var(--danger)]" />
      <p className="text-[15px] font-medium text-[var(--text-primary)]">页面渲染出错</p>
      <p className="text-[13px] text-[var(--text-secondary)] max-w-[480px] text-center break-all">
        {error.message || '未知错误'}
      </p>
      <div className="flex gap-2 mt-2">
        <button
          onClick={reset}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[13px] font-medium rounded-[var(--radius-md)] border border-[var(--border-default)] bg-[var(--bg-surface)] text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition-colors"
        >
          <RefreshCw size={13} />
          重试
        </button>
        <Link
          href="/"
          className="inline-flex items-center px-3 py-1.5 text-[13px] font-medium rounded-[var(--radius-md)] border border-[var(--border-default)] bg-[var(--bg-surface)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition-colors"
        >
          返回首页
        </Link>
      </div>
    </div>
  )
}
