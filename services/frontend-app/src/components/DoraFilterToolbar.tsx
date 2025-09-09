
import { useEffect, useState } from 'react'

interface FilterOptions {
  team: string[]
  project_key: string[]
  wit_to: string[]
  aha_initiative: string[]
  aha_project_code: string[]
  aha_milestone: string[]
}

interface DoraFilterToolbarProps {
  selectedMetric?: string
  onMetricChange?: (metric: string) => void
  filters?: {
    team?: string
    project_key?: string
    wit_to?: string
    aha_initiative?: string
    aha_project_code?: string
    aha_milestone?: string
  }
  onFiltersChange?: (filters: any) => void
  disabled?: boolean
}

const doraMetricOptions = [
  { value: 'lead-time', label: 'Lead Time for Changes' },
  // Hidden for now - keeping in code for future implementation
  // { value: 'deployment-frequency', label: 'Deployment Frequency' },
  // { value: 'change-failure-rate', label: 'Change Failure Rate' },
  // { value: 'time-to-restore', label: 'Time to Restore' }
]

export default function DoraFilterToolbar({
  selectedMetric = 'lead-time',
  onMetricChange,
  filters = {},
  onFiltersChange,
  disabled = false
}: DoraFilterToolbarProps) {

  const [filterOptions, setFilterOptions] = useState<FilterOptions>({
    team: [],
    project_key: [],
    wit_to: [],
    aha_initiative: [],
    aha_project_code: [],
    aha_milestone: []
  })
  const [loading, setLoading] = useState(true)

  // Fetch filter options on component mount
  useEffect(() => {
    const fetchFilterOptions = async () => {
      try {
        const token = localStorage.getItem('pulse_token') || document.cookie
          .split('; ')
          .find(row => row.startsWith('pulse_token='))
          ?.split('=')[1]

        if (!token) {
          console.error('No authentication token found')
          return
        }

        const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001'
        const response = await fetch(`${apiBase}/api/v1/metrics/dora/filter-options`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        })

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }

        const data = await response.json()
        setFilterOptions(data.filter_options)
      } catch (error) {
        console.error('Error fetching filter options:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchFilterOptions()
  }, [])

  const handleFilterChange = (key: string, value: string) => {
    const newFilters = { ...filters, [key]: value || undefined }
    onFiltersChange?.(newFilters)
  }

  return (
    <div className="card p-4 hover:shadow-md transition-all duration-300">
      {/* Single Row - All Filters - Use full width */}
      <div className="grid grid-cols-1 md:grid-cols-7 gap-3">
        <div className="flex flex-col">
          <label className="text-xs text-secondary mb-1">Metric</label>
          <select
            className="bg-primary border border-default rounded px-2 py-2 text-sm"
            value={selectedMetric}
            onChange={(e) => onMetricChange?.(e.target.value)}
            disabled={disabled}
          >
            {doraMetricOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        {/* 2. Project Key */}
        <div className="flex flex-col">
          <label className="text-xs text-secondary mb-1">Project Key</label>
          <select
            className="bg-primary border border-default rounded px-2 py-2 text-sm"
            value={filters.project_key || ''}
            onChange={(e) => handleFilterChange('project_key', e.target.value)}
            disabled={disabled || loading}
          >
            <option value="">All Projects</option>
            {filterOptions.project_key?.map((key) => (
              <option key={key} value={key}>
                {key}
              </option>
            )) || []}
          </select>
        </div>
        {/* 3. Team */}
        <div className="flex flex-col">
          <label className="text-xs text-secondary mb-1">Team</label>
          <select
            className="bg-primary border border-default rounded px-2 py-2 text-sm"
            value={filters.team || ''}
            onChange={(e) => handleFilterChange('team', e.target.value)}
            disabled={disabled || loading}
          >
            <option value="">All Teams</option>
            {filterOptions.team?.map((team) => (
              <option key={team} value={team}>
                {team}
              </option>
            )) || []}
          </select>
        </div>
        {/* 4. WorkItem Type */}
        <div className="flex flex-col">
          <label className="text-xs text-secondary mb-1">WorkItem Type</label>
          <select
            className="bg-primary border border-default rounded px-2 py-2 text-sm"
            value={filters.wit_to || ''}
            onChange={(e) => handleFilterChange('wit_to', e.target.value)}
            disabled={disabled || loading}
          >
            <option value="">All Types</option>
            {filterOptions.wit_to?.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            )) || []}
          </select>
        </div>
        {/* 5. Aha Initiative */}
        <div className="flex flex-col">
          <label className="text-xs text-secondary mb-1">Aha Initiative</label>
          <select
            className="bg-primary border border-default rounded px-2 py-2 text-sm"
            value={filters.aha_initiative || ''}
            onChange={(e) => handleFilterChange('aha_initiative', e.target.value)}
            disabled={disabled || loading}
          >
            <option value="">All Initiatives</option>
            {filterOptions.aha_initiative?.map((initiative) => (
              <option key={initiative} value={initiative}>
                {initiative}
              </option>
            )) || []}
          </select>
        </div>
        {/* 6. Aha Milestone */}
        <div className="flex flex-col">
          <label className="text-xs text-secondary mb-1">Aha Milestone</label>
          <select
            className="bg-primary border border-default rounded px-2 py-2 text-sm"
            value={filters.aha_milestone || ''}
            onChange={(e) => handleFilterChange('aha_milestone', e.target.value)}
            disabled={disabled || loading}
          >
            <option value="">All Milestones</option>
            {filterOptions.aha_milestone?.map((milestone) => (
              <option key={milestone} value={milestone}>
                {milestone}
              </option>
            )) || []}
          </select>
        </div>
        {/* 7. Aha Project Code */}
        <div className="flex flex-col">
          <label className="text-xs text-secondary mb-1">Aha Project Code</label>
          <select
            className="bg-primary border border-default rounded px-2 py-2 text-sm"
            value={filters.aha_project_code || ''}
            onChange={(e) => handleFilterChange('aha_project_code', e.target.value)}
            disabled={disabled || loading}
          >
            <option value="">All Project Codes</option>
            {filterOptions.aha_project_code?.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            )) || []}
          </select>
        </div>
      </div>
    </div>
  )
}
