'use client'

import { useEffect, useState } from 'react'
import { RegressionHeatmap } from './components/RegressionHeatmap'
import { ConfidenceTimeline } from './components/ConfidenceTimeline'
import { DatasetBrowser } from './components/DatasetBrowser'
import { ExperimentLog } from './components/ExperimentLog'
import { SelfImprovementLoop } from './components/SelfImprovementLoop'

const API = process.env.NAVIGUARD_API_URL || 'http://localhost:8080'

interface Metrics {
  confidence_timeline: Array<{ timestamp: string; confidence_score: number; category: string }>
  by_category: Record<string, { mean: number; count: number }>
  regression_windows: Array<{ timestamp: string; confidence_score: number; category: string }>
}

interface Regression {
  trace_id: string
  span_id: string
  timestamp: string
  confidence_score: number
  category: string
}

interface Dataset {
  dataset_id: string
  dataset_name: string
  example_count: number
  created_at: string
}

interface Experiment {
  prompt_version_id: string
  prompt_identifier: string
  prompt_tag: string
  dataset_id: string
  change_summary: string
  created_at: string
}

export default function Dashboard() {
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [regressions, setRegressions] = useState<Regression[]>([])
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [experiments, setExperiments] = useState<Experiment[]>([])
  const [running, setRunning] = useState(false)
  const [lastRun, setLastRun] = useState<any>(null)

  useEffect(() => {
    Promise.all([
      fetch(`${API}/metrics`).then(r => r.json()).catch(() => null),
      fetch(`${API}/regressions`).then(r => r.json()).catch(() => []),
      fetch(`${API}/datasets`).then(r => r.json()).catch(() => []),
      fetch(`${API}/experiments`).then(r => r.json()).catch(() => []),
    ]).then(([m, r, d, e]) => {
      if (m) setMetrics(m)
      setRegressions(r || [])
      setDatasets(d || [])
      setExperiments(e || [])
    })
  }, [lastRun])

  const runPipeline = async (scenario?: string) => {
    setRunning(true)
    try {
      const res = await fetch(`${API}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ window_minutes: 60, scenario }),
      })
      const data = await res.json()
      setLastRun(data)
    } finally {
      setRunning(false)
    }
  }

  const regressionCount = regressions.length
  const loopClosed = experiments.length > 0 && datasets.length > 0

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-zinc-50">Quality Monitor</h1>
          <p className="text-sm text-[#52525B] font-mono mt-1">
            Arize Phoenix ↔ Gemini self-improvement loop
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => runPipeline('hormuz')}
            disabled={running}
            className="px-4 py-2 text-sm font-mono border border-[#EC4899] text-[#EC4899] hover:bg-[#EC4899]/10 disabled:opacity-50 transition-colors"
            style={{ borderRadius: '4px' }}
          >
            {running ? 'Running...' : 'Run Hormuz Demo'}
          </button>
          <button
            onClick={() => runPipeline()}
            disabled={running}
            className="px-4 py-2 text-sm font-mono bg-[#EC4899] text-white hover:bg-[#BE185D] disabled:opacity-50 transition-colors"
            style={{ borderRadius: '4px' }}
          >
            {running ? 'Running...' : 'Run Pipeline'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Regressions', value: regressionCount, accent: regressionCount > 0 },
          { label: 'Datasets', value: datasets.length, accent: false },
          { label: 'Experiments', value: experiments.length, accent: false },
          { label: 'Loop Closed', value: loopClosed ? 'YES' : 'NO', accent: loopClosed },
        ].map(({ label, value, accent }) => (
          <div
            key={label}
            className="bg-[#111113] border border-[#27272A] p-4"
            style={{ borderRadius: '4px' }}
          >
            <p className="text-xs font-mono text-[#52525B] uppercase tracking-wider">{label}</p>
            <p className={`text-3xl font-mono mt-2 ${accent ? 'text-[#EC4899]' : 'text-zinc-50'}`}>
              {value}
            </p>
          </div>
        ))}
      </div>

      {lastRun && (
        <div className="bg-[#111113] border border-[#27272A] p-4" style={{ borderRadius: '4px' }}>
          <p className="text-xs font-mono text-[#52525B] uppercase tracking-wider mb-2">Last Run</p>
          <div className="flex gap-6 text-sm font-mono">
            <span>ID: <span className="text-zinc-300">{lastRun.run_id}</span></span>
            <span>Status: <span className={lastRun.status === 'completed' ? 'text-green-400' : 'text-[#EC4899]'}>{lastRun.status}</span></span>
            <span>Regression: <span className={lastRun.regression_status === 'REGRESSION' ? 'text-[#EC4899]' : 'text-green-400'}>{lastRun.regression_status}</span></span>
            <span>Critic: <span className={lastRun.critic_verdict === 'CORRECT' ? 'text-green-400' : 'text-yellow-400'}>{lastRun.critic_verdict || '—'}</span></span>
          </div>
          {lastRun.root_cause && (
            <p className="text-xs text-[#52525B] mt-2 font-mono">
              Root cause: {lastRun.root_cause}
            </p>
          )}
        </div>
      )}

      <SelfImprovementLoop
        hasRegressions={regressionCount > 0}
        hasDataset={datasets.length > 0}
        hasExperiment={experiments.length > 0}
        loopClosed={loopClosed}
      />

      <div className="grid grid-cols-2 gap-6">
        <RegressionHeatmap regressions={regressions} />
        <ConfidenceTimeline metrics={metrics} />
      </div>

      <div className="grid grid-cols-2 gap-6">
        <DatasetBrowser datasets={datasets} />
        <ExperimentLog experiments={experiments} />
      </div>
    </div>
  )
}
