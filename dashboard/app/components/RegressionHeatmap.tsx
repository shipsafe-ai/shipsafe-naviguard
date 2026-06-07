'use client'

interface Regression {
  trace_id: string
  timestamp: string
  confidence_score: number
  category: string
}

interface Props {
  regressions: Regression[]
}

function getHour(ts: string): number {
  return new Date(ts).getUTCHours()
}

export function RegressionHeatmap({ regressions }: Props) {
  const hours = Array.from({ length: 24 }, (_, i) => i)
  const categories = ['ROUTE', 'BLOCK', 'HOLD']

  const heatmap: Record<string, Record<number, { count: number; minConf: number }>> = {}
  for (const cat of categories) {
    heatmap[cat] = {}
    for (const h of hours) {
      heatmap[cat][h] = { count: 0, minConf: 1.0 }
    }
  }
  for (const r of regressions) {
    const h = getHour(r.timestamp)
    const cat = r.category in heatmap ? r.category : 'ROUTE'
    heatmap[cat][h].count += 1
    heatmap[cat][h].minConf = Math.min(heatmap[cat][h].minConf, r.confidence_score)
  }

  const cellColor = (count: number, minConf: number): string => {
    if (count === 0) return '#18181B'
    if (minConf < 0.45) return '#EC4899'
    if (minConf < 0.60) return '#BE185D'
    return '#9D174D'
  }

  return (
    <div className="bg-[#111113] border border-[#27272A] p-5" style={{ borderRadius: '4px' }}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-mono text-zinc-300 uppercase tracking-wider">
          Regression Heatmap
        </h2>
        <span className="text-xs font-mono text-[#52525B]">
          {regressions.length} spans below threshold
        </span>
      </div>

      <div className="overflow-x-auto">
        <div className="flex gap-1 mb-1">
          <div className="w-12" />
          {hours.filter(h => h % 3 === 0).map(h => (
            <div
              key={h}
              className="text-xs font-mono text-[#52525B]"
              style={{ width: `${100 / 8}%` }}
            >
              {String(h).padStart(2, '0')}:00
            </div>
          ))}
        </div>

        {categories.map(cat => (
          <div key={cat} className="flex items-center gap-1 mb-1">
            <div className="text-xs font-mono text-[#52525B] w-12 text-right pr-2">
              {cat}
            </div>
            <div className="flex gap-0.5 flex-1">
              {hours.map(h => {
                const cell = heatmap[cat][h]
                return (
                  <div
                    key={h}
                    className="flex-1 h-6 transition-colors"
                    style={{
                      backgroundColor: cellColor(cell.count, cell.minConf),
                      borderRadius: '2px',
                    }}
                    title={`${cat} ${String(h).padStart(2, '0')}:00 — ${cell.count} regressions, min conf: ${cell.count > 0 ? cell.minConf.toFixed(2) : 'N/A'}`}
                  />
                )
              })}
            </div>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-4 mt-4">
        <span className="text-xs font-mono text-[#52525B]">Severity:</span>
        {[
          { color: '#EC4899', label: '<0.45' },
          { color: '#BE185D', label: '<0.60' },
          { color: '#9D174D', label: '<0.70' },
          { color: '#18181B', label: 'OK' },
        ].map(({ color, label }) => (
          <div key={label} className="flex items-center gap-1">
            <div className="w-3 h-3" style={{ backgroundColor: color, borderRadius: '2px' }} />
            <span className="text-xs font-mono text-[#52525B]">{label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
