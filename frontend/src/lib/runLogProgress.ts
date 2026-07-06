import type { CompletedNode } from '@/hooks/useSSE'

/** 从 run.log 的 `[graph] → node` 行推断流水线进度（SSE 晚加入时的兜底） */
export function parseRunLogProgress(log: string): {
  currentNode: string | null
  completedNodes: CompletedNode[]
} {
  const starts = [...log.matchAll(/\[graph\] → (\w+)/g)].map((m) => m[1])
  if (starts.length === 0) {
    return { currentNode: null, completedNodes: [] }
  }

  const currentNode = starts[starts.length - 1]
  const completedNodes: CompletedNode[] = starts.slice(0, -1).map((node) => ({ node }))

  return { currentNode, completedNodes }
}
