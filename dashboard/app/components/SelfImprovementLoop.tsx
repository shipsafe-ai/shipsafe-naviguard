'use client'

interface Props {
  hasRegressions: boolean
  hasDataset: boolean
  hasExperiment: boolean
  loopClosed: boolean
}

interface Step {
  id: string
  label: string
  sublabel: string
  active: boolean
  mcp_tool?: string
}

export function SelfImprovementLoop({ hasRegressions, hasDataset, hasExperiment, loopClosed }: Props) {
  const steps: Step[] = [
    {
      id: 'monitor',
      label: 'ModelMonitor',
      sublabel: 'list-traces, get-spans',
      active: true,
      mcp_tool: 'Phoenix MCP',
    },
    {
      id: 'detect',
      label: 'RegressionDetector',
      sublabel: 'get-span-annotations',
      active: hasRegressions,
      mcp_tool: 'Phoenix MCP',
    },
    {
      id: 'analyze',
      label: 'RootCauseAnalyzer',
      sublabel: 'get-session, Gemini',
      active: hasRegressions,
      mcp_tool: 'Gemini + MCP',
    },
    {
      id: 'dataset',
      label: 'DatasetBuilder',
      sublabel: 'add-dataset-examples',
      active: hasDataset,
      mcp_tool: 'Phoenix MCP',
    },
    {
      id: 'experiment',
      label: 'ExperimentRunner',
      sublabel: 'upsert-prompt',
      active: hasExperiment,
      mcp_tool: 'Phoenix MCP',
    },
    {
      id: 'critic',
      label: 'Critic',
      sublabel: 'get-trace (verify)',
      active: hasExperiment,
      mcp_tool: 'Phoenix MCP',
    },
  ]

  return (
    <div className="bg-[#111113] border border-[#27272A] p-5" style={{ borderRadius: '4px' }}>
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-sm font-mono text-zinc-300 uppercase tracking-wider">
          Self-Improvement Loop
        </h2>
        <div className="flex items-center gap-2">
          <span
            className="text-xs font-mono px-2 py-0.5"
            style={{
              backgroundColor: loopClosed ? '#14532D' : '#18181B',
              color: loopClosed ? '#4ADE80' : '#52525B',
              border: `1px solid ${loopClosed ? '#166534' : '#27272A'}`,
              borderRadius: '2px',
            }}
          >
            {loopClosed ? 'LOOP CLOSED' : 'LOOP OPEN'}
          </span>
        </div>
      </div>

      <div className="relative flex items-start justify-between">
        {steps.map((step, idx) => (
          <div key={step.id} className="flex items-center">
            <div className="flex flex-col items-center">
              <div
                className="w-10 h-10 flex items-center justify-center text-xs font-mono font-bold transition-all duration-500"
                style={{
                  backgroundColor: step.active ? '#EC4899' : '#18181B',
                  border: `1px solid ${step.active ? '#EC4899' : '#27272A'}`,
                  color: step.active ? '#fff' : '#52525B',
                  borderRadius: '4px',
                }}
              >
                {idx + 1}
              </div>
              <p
                className="text-xs font-mono mt-2 text-center max-w-20"
                style={{ color: step.active ? '#E4E4E7' : '#52525B' }}
              >
                {step.label}
              </p>
              <p className="text-xs font-mono text-center mt-0.5" style={{ color: '#3F3F46', fontSize: '9px' }}>
                {step.sublabel}
              </p>
              {step.mcp_tool && (
                <span
                  className="text-xs font-mono mt-1 px-1"
                  style={{
                    color: step.active ? '#EC4899' : '#27272A',
                    border: `1px solid ${step.active ? '#BE185D' : '#27272A'}`,
                    borderRadius: '2px',
                    fontSize: '8px',
                  }}
                >
                  {step.mcp_tool}
                </span>
              )}
            </div>

            {idx < steps.length - 1 && (
              <div
                className="h-px w-8 mt-[-20px] mx-1 transition-all duration-500"
                style={{
                  backgroundColor: step.active && steps[idx + 1].active ? '#EC4899' : '#27272A',
                }}
              />
            )}
          </div>
        ))}

        {loopClosed && (
          <div className="absolute -bottom-3 left-0 right-0 flex items-center justify-center">
            <div
              className="text-xs font-mono px-3 py-1"
              style={{
                color: '#4ADE80',
                backgroundColor: '#14532D',
                border: '1px solid #166534',
                borderRadius: '4px',
              }}
            >
              Loop closed — naviguard-proposed prompt active in Phoenix
            </div>
          </div>
        )}
      </div>

      <div className="mt-8 pt-4 border-t border-[#27272A] flex gap-6 text-xs font-mono text-[#3F3F46]">
        <span>NaviGuard traces its own improvements</span>
        <span>•</span>
        <span>All Phoenix operations via MCP (no direct REST)</span>
        <span>•</span>
        <span>Human gate before any write</span>
      </div>
    </div>
  )
}
