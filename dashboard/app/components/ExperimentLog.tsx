'use client'

interface Experiment {
  prompt_version_id: string
  prompt_identifier: string
  prompt_tag: string
  dataset_id: string
  change_summary: string
  created_at: string
}

interface Props {
  experiments: Experiment[]
}

export function ExperimentLog({ experiments }: Props) {
  return (
    <div className="bg-[#111113] border border-[#27272A] p-5" style={{ borderRadius: '4px' }}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-mono text-zinc-300 uppercase tracking-wider">
          Experiment Log
        </h2>
        <span className="text-xs font-mono text-[#52525B]">
          {experiments.length} prompt versions
        </span>
      </div>

      {experiments.length === 0 ? (
        <div className="text-center py-8">
          <p className="text-xs font-mono text-[#3F3F46]">No experiments yet</p>
          <p className="text-xs font-mono text-[#27272A] mt-1">
            Approve proposals to create Phoenix prompt versions
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {experiments.map(e => (
            <div
              key={e.prompt_version_id}
              className="border border-[#27272A] p-3 bg-[#18181B]"
              style={{ borderRadius: '4px' }}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono text-[#52525B]">
                  {e.prompt_identifier}
                </span>
                <span
                  className="text-xs font-mono px-2 py-0.5 border"
                  style={{
                    color: '#EC4899',
                    borderColor: '#EC4899',
                    borderRadius: '2px',
                  }}
                >
                  {e.prompt_tag || 'naviguard-proposed'}
                </span>
              </div>
              <p className="text-sm text-zinc-300 mt-1 font-mono text-xs leading-relaxed">
                {e.change_summary.slice(0, 80)}{e.change_summary.length > 80 ? '...' : ''}
              </p>
              <div className="flex gap-4 mt-2">
                <span className="text-xs font-mono text-[#3F3F46]">
                  v: {e.prompt_version_id.slice(0, 14)}...
                </span>
                {e.created_at && (
                  <span className="text-xs font-mono text-[#3F3F46]">
                    {e.created_at.slice(0, 10)}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="mt-4 pt-4 border-t border-[#27272A]">
        <p className="text-xs font-mono text-[#3F3F46]">
          Prompt versions created via Phoenix MCP upsert-prompt + add-prompt-version-tag
        </p>
      </div>
    </div>
  )
}
