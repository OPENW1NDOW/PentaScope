'use client'

import {
  ScatterChart as ReScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
  Label,
  ResponsiveContainer,
  ZAxis,
} from 'recharts'

interface ScatterDataPoint {
  name: string
  x: number
  y: number
  isSelf?: boolean
}

interface ScatterChartProps {
  data: ScatterDataPoint[]
  xLabel?: string
  yLabel?: string
  xMax?: number
  yMax?: number
  quadrantLines?: boolean
  height?: number
}

function CustomLabel(props: Record<string, unknown>) {
  const { x, y, name } = props as { x: number; y: number; name: string }
  return (
    <text
      x={x}
      y={y - 12}
      textAnchor="middle"
      fontSize={11}
      fill="var(--text-secondary)"
    >
      {name}
    </text>
  )
}

export function ScatterChart({
  data,
  xLabel,
  yLabel,
  xMax = 5,
  yMax = 5,
  quadrantLines = false,
  height = 420,
}: ScatterChartProps) {
  const competitors = data.filter((d) => !d.isSelf)
  const self = data.filter((d) => d.isSelf)

  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg-surface)] p-4">
      <ResponsiveContainer width="100%" height={height}>
        <ReScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-divider)" />
          <XAxis
            type="number"
            dataKey="x"
            domain={[0, xMax]}
            tick={{ fontSize: 11, fill: 'var(--text-tertiary)' }}
          >
            {xLabel && <Label value={xLabel} position="bottom" offset={0} style={{ fontSize: 12, fill: 'var(--text-secondary)' }} />}
          </XAxis>
          <YAxis
            type="number"
            dataKey="y"
            domain={[0, yMax]}
            tick={{ fontSize: 11, fill: 'var(--text-tertiary)' }}
          >
            {yLabel && <Label value={yLabel} angle={-90} position="insideLeft" style={{ fontSize: 12, fill: 'var(--text-secondary)' }} />}
          </YAxis>
          <ZAxis range={[80, 80]} />
          <Tooltip
            contentStyle={{
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-md)',
              fontSize: 13,
              color: 'var(--text-primary)',
            }}
          />
          {quadrantLines && (
            <>
              <ReferenceLine x={xMax / 2} stroke="var(--text-tertiary)" strokeDasharray="6 4" />
              <ReferenceLine y={yMax / 2} stroke="var(--text-tertiary)" strokeDasharray="6 4" />
            </>
          )}
          {competitors.length > 0 && (
            <Scatter
              name="竞品"
              data={competitors}
              fill="#2EAADC"
              label={<CustomLabel />}
            />
          )}
          {self.length > 0 && (
            <Scatter
              name="我方"
              data={self}
              fill="#D44C47"
              shape="star"
              label={<CustomLabel />}
            />
          )}
          <Legend wrapperStyle={{ fontSize: 12, color: 'var(--text-secondary)' }} />
        </ReScatterChart>
      </ResponsiveContainer>
    </div>
  )
}
