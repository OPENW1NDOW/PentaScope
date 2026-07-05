'use client'

import {
  LineChart as ReLineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'

const COLORS = ['#2EAADC', '#4DAB9A', '#E9973F', '#D44C47', '#9A6DD7', '#E255A1', '#6B8E23', '#CD853F']

interface LineConfig {
  key: string
  label?: string
  isSelf?: boolean
}

interface LineChartProps {
  data: Array<Record<string, number | string>>
  xKey: string
  lines: LineConfig[]
  yMax?: number
  height?: number
}

export function LineChart({ data, xKey, lines, yMax = 10, height = 420 }: LineChartProps) {
  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] p-4">
      <ResponsiveContainer width="100%" height={height}>
        <ReLineChart data={data} margin={{ top: 10, right: 20, bottom: 10, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-divider)" />
          <XAxis
            dataKey={xKey}
            tick={{ fontSize: 11, fill: 'var(--text-tertiary)' }}
          />
          <YAxis
            domain={[0, yMax]}
            tick={{ fontSize: 11, fill: 'var(--text-tertiary)' }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-md)',
              fontSize: 13,
              color: 'var(--text-primary)',
            }}
          />
          <Legend wrapperStyle={{ fontSize: 12, color: 'var(--text-secondary)' }} />
          {lines.map((line, i) => (
            <Line
              key={line.key}
              type="monotone"
              dataKey={line.key}
              name={line.label ?? line.key}
              stroke={line.isSelf ? '#D44C47' : COLORS[i % COLORS.length]}
              strokeWidth={line.isSelf ? 3 : 1.5}
              strokeDasharray={line.isSelf ? undefined : '5 5'}
              dot={{ r: 3, fill: line.isSelf ? '#D44C47' : COLORS[i % COLORS.length] }}
              activeDot={{ r: 5 }}
            />
          ))}
        </ReLineChart>
      </ResponsiveContainer>
    </div>
  )
}
