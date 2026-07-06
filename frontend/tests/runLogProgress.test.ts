import { describe, it, expect } from 'vitest'
import { parseRunLogProgress } from '@/lib/runLogProgress'

describe('parseRunLogProgress', () => {
  it('returns empty when log has no graph lines', () => {
    expect(parseRunLogProgress('')).toEqual({ currentNode: null, completedNodes: [] })
  })

  it('infers current and completed nodes from run.log', () => {
    const log = [
      'INFO src.graph.builder: [graph] → collector',
      'INFO src.graph.builder: [graph] → analyzer',
      'INFO src.graph.builder: [graph] → writer',
      'INFO src.graph.builder: [graph] → inspector',
    ].join('\n')

    expect(parseRunLogProgress(log)).toEqual({
      currentNode: 'inspector',
      completedNodes: [
        { node: 'collector' },
        { node: 'analyzer' },
        { node: 'writer' },
      ],
    })
  })
})
