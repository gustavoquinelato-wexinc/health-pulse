interface FilterToolbarProps {
  disabled?: boolean
}

export default function FilterToolbar({ disabled = true }: FilterToolbarProps) {
  return (
    <div className="bg-secondary border border-default rounded-lg p-3 grid grid-cols-1 md:grid-cols-4 gap-3">
      <div className="flex flex-col">
        <label className="text-xs text-secondary mb-1">Date Range</label>
        <select className="bg-primary border border-default rounded px-2 py-2 text-sm" disabled={disabled} defaultValue="30">
          <option value="30">Last 30 days</option>
          <option value="90">Last 90 days</option>
          <option value="180">Last 180 days</option>
          <option value="365">Last 1 year</option>
          <option value="1825">Last 5 years</option>
        </select>
      </div>
      <div className="flex flex-col">
        <label className="text-xs text-secondary mb-1">Team</label>
        <select className="bg-primary border border-default rounded px-2 py-2 text-sm" disabled>
          <option>All teams (SOON)</option>
        </select>
      </div>
      <div className="flex flex-col">
        <label className="text-xs text-secondary mb-1">WorkItem Type</label>
        <select className="bg-primary border border-default rounded px-2 py-2 text-sm" disabled>
          <option>All types (SOON)</option>
        </select>
      </div>
      <div className="flex items-end">
        <button className="btn btn-primary opacity-60 cursor-not-allowed" disabled>
          Apply Filters (SOON)
        </button>
      </div>
    </div>
  )
}

