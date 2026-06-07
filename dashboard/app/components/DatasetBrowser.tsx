'use client'

interface Dataset {
  dataset_id: string
  dataset_name: string
  example_count: number
  created_at: string
}

interface Props {
  datasets: Dataset[]
}

export function DatasetBrowser({ datasets }: Props) {
  return (
    <div className="bg-[#111113] border border-[#27272A] p-5" style={{ borderRadius: '4px' }}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-mono text-zinc-300 uppercase tracking-wider">
          Phoenix Datasets
        </h2>
        <span className="text-xs font-mono text-[#52525B]">
          {datasets.length} naviguard datasets
        </span>
      </div>

      {datasets.length === 0 ? (
        <div className="text-center py-8">
          <p className="text-xs font-mono text-[#3F3F46]">No datasets yet</p>
          <p className="text-xs font-mono text-[#27272A] mt-1">
            Run pipeline to build retraining datasets
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {datasets.map(d => (
            <div
              key={d.dataset_id}
              className="border border-[#27272A] p-3 bg-[#18181B]"
              style={{ borderRadius: '4px' }}
            >
              <div className="flex items-center justify-between">
                <p className="text-sm font-mono text-zinc-200 truncate max-w-xs">
                  {d.dataset_name}
                </p>
                <span className="text-xs font-mono text-[#EC4899] ml-2 flex-shrink-0">
                  {d.example_count} examples
                </span>
              </div>
              <div className="flex gap-4 mt-1">
                <span className="text-xs font-mono text-[#52525B]">
                  id: {d.dataset_id.slice(0, 16)}...
                </span>
                {d.created_at && (
                  <span className="text-xs font-mono text-[#3F3F46]">
                    {d.created_at.slice(0, 10)}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="mt-4 pt-4 border-t border-[#27272A]">
        <p className="text-xs font-mono text-[#3F3F46]">
          Datasets built from failure traces via Phoenix MCP add-dataset-examples
        </p>
      </div>
    </div>
  )
}
