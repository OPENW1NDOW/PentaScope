'use client'

import { RadarChart } from './RadarChart'
import type { FiveForces, Force } from '@/types'
import { intensityToNum } from '@/lib/formatters'

interface FiveForcesRadarProps {
  forces: FiveForces
}

const FORCE_KEYS: Array<{ key: keyof FiveForces; label: string }> = [
  { key: 'new_entrants', label: '新进入者' },
  { key: 'supplier_power', label: '供应商' },
  { key: 'buyer_power', label: '买家' },
  { key: 'substitute_threat', label: '替代品' },
  { key: 'competitive_rivalry', label: '现有竞争' },
]

export function FiveForcesRadar({ forces }: FiveForcesRadarProps) {
  const data = FORCE_KEYS.map(({ key, label }) => {
    const force = forces[key]
    const intensity = typeof force === 'object' && force !== null && 'intensity' in force
      ? (force as Force).intensity
      : undefined
    return {
      dimension: label,
      强度: intensityToNum(intensity),
    }
  })

  return (
    <RadarChart
      data={data}
      keys={['强度']}
      height={350}
      max={5}
    />
  )
}
