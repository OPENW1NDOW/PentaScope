'use client'

import { Check, Loader2 } from 'lucide-react'
import { NODE_LABELS, PIPELINE_NODES, PIPELINE_NODES_S2 } from '@/lib/constants'
import type { CompletedNode } from '@/hooks/useSSE'

interface PipelineStepperProps {
  scenario?: string
  currentNode: string | null
  completedNodes: CompletedNode[]
}

type StepState = 'completed' | 'current' | 'pending'

/**
 * Agent 流水线全景步骤条：已完成 ✓+耗时 / 当前脉动 / 未开始置灰。
 * 反馈闭环打回重跑时，节点重新进入 current 态并显示重跑次数。
 */
export function PipelineStepper({ scenario, currentNode, completedNodes }: PipelineStepperProps) {
  const nodes: readonly string[] = scenario === 'S2' ? PIPELINE_NODES_S2 : PIPELINE_NODES

  const stepFor = (node: string): { state: StepState; durationMs?: number; runs: number } => {
    const runs = completedNodes.filter((c) => c.node === node)
    if (currentNode === node) return { state: 'current', runs: runs.length }
    if (runs.length > 0) {
      return { state: 'completed', durationMs: runs[runs.length - 1].durationMs, runs: runs.length }
    }
    return { state: 'pending', runs: 0 }
  }

  return (
    <ol className="flex flex-wrap items-center gap-y-3">
      {nodes.map((node, i) => {
        const { state, durationMs, runs } = stepFor(node)
        return (
          <li key={node} className="flex items-center">
            {i > 0 && (
              <div
                className={`w-6 sm:w-10 h-px mx-1.5 ${
                  state === 'pending' ? 'bg-[var(--border-default)]' : 'bg-[var(--border-active)]'
                }`}
              />
            )}
            <div className="flex items-center gap-2">
              <span
                className={`flex items-center justify-center w-6 h-6 rounded-full shrink-0 ${
                  state === 'completed'
                    ? 'bg-[var(--success)] text-white'
                    : state === 'current'
                      ? 'border-2 border-[var(--info)] text-[var(--info)]'
                      : 'border border-[var(--border-default)] text-[var(--text-tertiary)]'
                }`}
              >
                {state === 'completed' ? (
                  <Check size={13} strokeWidth={2.5} />
                ) : state === 'current' ? (
                  <Loader2 size={13} className="animate-spin" />
                ) : (
                  <span className="text-[11px]">{i + 1}</span>
                )}
              </span>
              <div className="flex flex-col">
                <span
                  className={`text-[13px] leading-tight ${
                    state === 'pending'
                      ? 'text-[var(--text-tertiary)]'
                      : 'text-[var(--text-primary)] font-medium'
                  }`}
                >
                  {NODE_LABELS[node] ?? node}
                  {runs > 1 && (
                    <span className="ml-1 text-[11px] text-[var(--warning)]">×{runs}</span>
                  )}
                </span>
                <span className="text-[11px] leading-tight text-[var(--text-tertiary)] min-h-[14px]">
                  {state === 'completed' && durationMs != null
                    ? `${(durationMs / 1000).toFixed(1)}s`
                    : state === 'current'
                      ? '执行中'
                      : ''}
                </span>
              </div>
            </div>
          </li>
        )
      })}
    </ol>
  )
}
