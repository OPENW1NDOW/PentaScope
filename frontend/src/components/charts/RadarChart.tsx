'use client'

import {
  RadarChart as ReRadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'

const COLORS = ['#2EAADC', '#4DAB9A', '#E9973F', '#D44C47', '#9A6DD7', '#E255A1', '#6B8E23', '#CD853F']

interface RadarChartProps {
  data: Array<Record<string, number | string>>
  keys: string[]
  labels?: Record<string, string>
  height?: number
  max?: number
}

export function RadarChart({ data, keys, labels, height = 380, max = 5 }: RadarChartProps) {
  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] p-4">
      <ResponsiveContainer width="100%" height={height}>
        <ReRadarChart data={data} cx="50%" cy="50%" outerRadius="75%">
          <PolarGrid stroke="var(--divider)" />
          <PolarAngleAxis
            dataKey="dimension"
            tick={{ fontSize: 12, fill: 'var(--text-secondary)' }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, max]}
            tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }}
          />
          {keys.map((key, i) => (
            <Radar
              key={key}
              name={labels?.[key] ?? key}
              dataKey={key}
              stroke={COLORS[i % COLORS.length]}
              fill={COLORS[i % COLORS.length]}
              fillOpacity={0.15}
              strokeWidth={2}
            />
          ))}
          <Tooltip
            contentStyle={{
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-md)',
              fontSize: 13,
              color: 'var(--text-primary)',
            }}
          />
          <Legend
            wrapperStyle={{ fontSize: 12, color: 'var(--text-secondary)' }}
          />
        </ReRadarChart>
      </ResponsiveContainer>
    </div>
  )
}
