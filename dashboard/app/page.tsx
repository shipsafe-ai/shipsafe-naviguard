'use client'

import { useEffect, useState, useCallback } from 'react'
import { RegressionHeatmap } from './components/RegressionHeatmap'
import { ConfidenceTimeline } from './components/ConfidenceTimeline'
import { DatasetBrowser } from './components/DatasetBrowser'
import { ExperimentLog } from './components/ExperimentLog'
import { SelfImprovementLoop } from './components/SelfImprovementLoop'

const API = process.env.NAVIGUARD_API_URL || 'http://localhost:8080'

const _cache = new Map<string, { data: unknown; ts: number }>()
const CACHE_TTL = 30_000
async function cachedFetch(url: string): Promise<unknown> {
  const hit = _cache.get(url)
  if (hit && Date.now() - hit.ts < CACHE_TTL) return hit.data
  const res = await fetch(url)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data = await res.json()
  _cache.set(url, { data, ts: Date.now() })
  return data
}

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

type StepStatus = 'pending' | 'running' | 'done' | 'skipped' | 'error'

interface RunStep {
  step: number
  name: string
  label: string
  status: StepStatus
  message?: string
}

const PIPELINE_STEPS: RunStep[] = [
  { step: 1, name: 'ModelMonitor',       label: 'Fetch Phoenix traces',            status: 'pending' },
  { step: 2, name: 'RegressionDetector', label: 'Detect confidence regressions',   status: 'pending' },
  { step: 3, name: 'Analysis',           label: 'Root cause + dataset + prompt',   status: 'pending' },
  { step: 4, name: 'Critic',             label: 'Adversarial validation',           status: 'pending' },
]

export default function Dashboard() {
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [regressions, setRegressions] = useState<Regression[]>([])
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [experiments, setExperiments] = useState<Experiment[]>([])
  const [running, setRunning] = useState(false)
  const [lastRun, setLastRun] = useState<any>(null)
  const [runSteps, setRunSteps] = useState<RunStep[]>([])

  const refreshData = useCallback(() => {
    // Bust cache on explicit refresh
    _cache.clear()
    Promise.all([
      cachedFetch(`${API}/metrics`).catch(() => null),
      cachedFetch(`${API}/regressions`).catch(() => []),
      cachedFetch(`${API}/datasets`).catch(() => []),
      cachedFetch(`${API}/experiments`).catch(() => []),
    ]).then(([m, r, d, e]) => {
      if (m) setMetrics(m as Metrics)
      setRegressions((r as Regression[]) || [])
      setDatasets((d as Dataset[]) || [])
      setExperiments((e as Experiment[]) || [])
    })
  }, [])

  useEffect(() => {
    refreshData()
  }, [refreshData])

  const runPipeline = async (scenario?: string) => {
    setRunning(true)
    setRunSteps(PIPELINE_STEPS.map(s => ({ ...s, status: 'pending' as StepStatus })))

    try {
      const res = await fetch(`${API}/run/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ window_minutes: 60, scenario }),
      })

      if (!res.ok || !res.body) {
        throw new Error(`HTTP ${res.status}`)
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6))

            if (event.event === 'step') {
              setRunSteps(prev =>
                prev.map(s =>
                  s.step === event.step
                    ? { ...s, status: event.status as StepStatus, message: event.message }
                    : s
                )
              )
            } else if (event.event === 'complete') {
              setLastRun(event)
              setRunning(false)
              setTimeout(refreshData, 1500)
            } else if (event.event === 'error') {
              setRunning(false)
            }
          } catch {
            // malformed SSE line — skip
          }
        }
      }
    } catch {
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
          { label: 'Datasets',    value: datasets.length,    accent: false },
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

      {/* Pipeline thinking panel — visible while running */}
      {runSteps.length > 0 && (
        <div className="bg-[#111113] border border-[#27272A] p-4" style={{ borderRadius: '4px' }}>
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs font-mono text-[#52525B] uppercase tracking-wider">
              {running ? 'Analysis in progress' : 'Last run steps'}
            </p>
            {running && (
              <span className="flex gap-1">
                {[0, 1, 2].map(i => (
                  <span
                    key={i}
                    className="w-1.5 h-1.5 rounded-full bg-[#EC4899] animate-bounce"
                    style={{ animationDelay: `${i * 150}ms` }}
                  />
                ))}
              </span>
            )}
          </div>
          <div className="space-y-2">
            {runSteps.map(step => (
              <div key={step.step} className="flex items-start gap-3 text-sm font-mono">
                <span
                  className={[
                    'mt-0.5 text-base leading-none',
                    step.status === 'done'    ? 'text-green-400' :
                    step.status === 'running' ? 'text-[#EC4899] animate-pulse' :
                    step.status === 'skipped' ? 'text-[#52525B]' :
                    'text-[#3F3F46]',
                  ].join(' ')}
                >
                  {step.status === 'done'    ? '✓' :
                   step.status === 'running' ? '●' :
                   step.status === 'skipped' ? '—' : '○'}
                </span>
                <div className="flex-1 min-w-0">
                  <span className={step.status === 'pending' ? 'text-[#3F3F46]' : 'text-zinc-300'}>
                    {step.name}
                  </span>
                  <span className="text-[#3F3F46] ml-2 text-xs">{step.label}</span>
                  {step.message && (
                    <p className="text-[#52525B] text-xs mt-0.5 truncate">{step.message}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Last run summary */}
      {lastRun && (
        <div className="bg-[#111113] border border-[#27272A] p-4" style={{ borderRadius: '4px' }}>
          <p className="text-xs font-mono text-[#52525B] uppercase tracking-wider mb-2">Last Run</p>
          <div className="flex gap-6 text-sm font-mono flex-wrap">
            <span>ID: <span className="text-zinc-300">{lastRun.run_id}</span></span>
            <span>
              Status:{' '}
              <span className={lastRun.status === 'completed' ? 'text-green-400' : 'text-[#EC4899]'}>
                {lastRun.status}
              </span>
            </span>
            <span>
              Regression:{' '}
              <span className={lastRun.regression_status === 'REGRESSION' ? 'text-[#EC4899]' : 'text-green-400'}>
                {lastRun.regression_status}
              </span>
            </span>
            <span>
              Critic:{' '}
              <span className={lastRun.critic_verdict === 'CORRECT' ? 'text-green-400' : 'text-yellow-400'}>
                {lastRun.critic_verdict || '—'}
              </span>
            </span>
          </div>
          {/* Gemini reasoning across the pipeline */}
          {lastRun.regression_report?.regression_summary && (
            <p className="text-xs text-zinc-400 mt-3 font-mono leading-relaxed">
              <span className="text-[#52525B] uppercase tracking-wider">Regression · </span>
              {lastRun.regression_report.regression_summary}
            </p>
          )}
          {lastRun.root_cause && (
            <p className="text-xs text-zinc-400 mt-2 font-mono leading-relaxed">
              <span className="text-[#52525B] uppercase tracking-wider">Root cause · </span>
              {lastRun.root_cause}
              {lastRun.root_cause_report?.pattern ? ` (${lastRun.root_cause_report.pattern})` : ''}
            </p>
          )}
          {lastRun.root_cause_report?.recommendation && (
            <p className="text-xs text-zinc-400 mt-2 font-mono leading-relaxed">
              <span className="text-[#52525B] uppercase tracking-wider">Fix · </span>
              {lastRun.root_cause_report.recommendation}
            </p>
          )}
          {lastRun.critic_report?.critique && (
            <p className="text-xs text-zinc-400 mt-2 font-mono leading-relaxed">
              <span className="text-[#52525B] uppercase tracking-wider">Critic · </span>
              {lastRun.critic_report.critique}
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
