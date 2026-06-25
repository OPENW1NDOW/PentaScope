'use client'

import type { S4MonitoringPayload } from '@/types'
import { Construction } from 'lucide-react'

interface S4PayloadProps {
  payload: S4MonitoringPayload
}

export function S4Payload({ payload }: S4PayloadProps) {
  // S4 schema 是 placeholder，显示已有字段
  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] p-8 flex flex-col items-center gap-3 text-center">
        <Construction size={24} strokeWidth={1.5} className="text-[var(--text-tertiary)]" />
        <p className="text-[14px] text-[var(--text-secondary)]">
          S4 竞争监控场景渲染组件开发中
        </p>
        <p className="text-[12px] text-[var(--text-tertiary)]">
          数据已加载（{Object.keys(payload).length} 个字段）
        </p>
      </div>
    </div>
  )
}
