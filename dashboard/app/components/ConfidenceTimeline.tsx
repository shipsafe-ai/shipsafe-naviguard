'use client'

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Legend,
} from 'recharts'

interface MetricsData {
  confidence_timeline: Array<{ timestamp: string; confidence_score: number; category: string }>
  by_category: Record<string, { mean: number; count: number }>
  regression_windows: Array<{ timestamp: string; confidence_score: number; category: string }>
}

interface Props {
  metrics: MetricsData | null
}

const CATEGORY_COLORS: Record<string, string> = {
  ROUTE: '#52525B',
  BLOCK: '#EC4899',
  HOLD: '#71717A',
}

export function ConfidenceTimeline({ metrics }: Props) {
  const timeline = metrics?.confidence_timeline || []

  const byCategory: Record<string, Record<string, number>> = {}
  for (const pt of timeline) {
    const ts = pt.timestamp.slice(0, 16)
    if (!byCategory[ts]) byCategory[ts] = {}
    byCategory[ts][pt.category] = pt.confidence_score
  }

  const chartData = Object.entries(byCategory)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([ts, cats]) => ({ ts: ts.slice(11, 16), ...cats }))

  const categories = [...new Set(timeline.map(t => t.category))]

  return (
    <div className="bg-[#111113] border border-[#27272A] p-5" style={{ borderRadius: '4px' }}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-mono text-zinc-300 uppercase tracking-wider">
          Confidence Timeline
        </h2>
        <span className="text-xs font-mono text-[#52525B]">
          threshold: <span className="text-[#EC4899]">0.70</span>
        </span>
      </div>

      {metrics?.by_category && (
        <div className="flex gap-4 mb-4">
          {Object.entries(metrics.by_category).map(([cat, stats]) => (
            <div key={cat} className="text-center">
              <p className="text-xs font-mono text-[#52525B]">{cat}</p>
              <p
                className="text-lg font-mono"
                style={{ color: stats.mean < 0.70 ? '#EC4899' : '#A1A1AA' }}
              >
                {stats.mean.toFixed(2)}
              </p>
              <p className="text-xs font-mono text-[#3F3F46]">{stats.count} spans</p>
            </div>
          ))}
        </div>
      )}

      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: -20 }}>
          <CartesianGrid stroke="#27272A" strokeDasharray="3 3" />
          <XAxis
            dataKey="ts"
            tick={{ fill: '#52525B', fontSize: 10, fontFamily: 'DM Mono' }}
            tickLine={false}
            axisLine={{ stroke: '#27272A' }}
          />
          <YAxis
            domain={[0, 1]}
            tick={{ fill: '#52525B', fontSize: 10, fontFamily: 'DM Mono' }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#18181B',
              border: '1px solid #27272A',
              borderRadius: '4px',
              fontFamily: 'DM Mono',
              fontSize: '11px',
            }}
            labelStyle={{ color: '#52525B' }}
          />
          <ReferenceLine
            y={0.70}
            stroke="#EC4899"
            strokeDasharray="4 4"
            strokeWidth={1}
            label={{ value: '0.70', fill: '#EC4899', fontSize: 10, fontFamily: 'DM Mono' }}
          />
          <Legend
            wrapperStyle={{ fontFamily: 'DM Mono', fontSize: '10px', color: '#52525B' }}
          />
          {categories.map(cat => (
            <Line
              key={cat}
              type="monotone"
              dataKey={cat}
              stroke={CATEGORY_COLORS[cat] || '#71717A'}
              strokeWidth={cat === 'BLOCK' ? 2 : 1}
              dot={false}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
