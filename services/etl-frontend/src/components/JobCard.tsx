import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import {
  Play,
  Clock,
  Info,
  CheckCircle,
  XCircle,
  Loader,
  AlertCircle,
  Settings
} from 'lucide-react'
import IntegrationLogo from './IntegrationLogo'

interface JobCardProps {
  job: {
    id: number
    job_name: string
    status: string
    active: boolean
    schedule_interval_minutes: number
    retry_interval_minutes: number
    integration_type?: string
    integration_logo_filename?: string
    last_run_started_at?: string
    last_run_finished_at?: string
    next_run?: string
    error_message?: string
    retry_count: number
  }
  onRunNow: (jobId: number) => void
  onShowDetails: (jobId: number) => void
  onToggleActive: (jobId: number, active: boolean) => void
  onSettings: (job: any) => void
}

export default function JobCard({ job, onRunNow, onShowDetails, onToggleActive, onSettings }: JobCardProps) {
  const [, setIsHovered] = useState(false)
  const [isToggling, setIsToggling] = useState(false)
  const [countdown, setCountdown] = useState<string>('Calculating...')

  // Get status icon and color
  const getStatusInfo = () => {
    if (!job.active) {
      return {
        icon: <XCircle className="w-5 h-5" />,
        color: 'text-gray-400',
        bgColor: 'bg-gray-100',
        label: 'Inactive'
      }
    }

    switch (job.status) {
      case 'RUNNING':
        return {
          icon: <Loader className="w-5 h-5 animate-spin" />,
          color: 'text-blue-500',
          bgColor: 'bg-blue-100',
          label: 'Running'
        }
      case 'FINISHED':
        return {
          icon: <CheckCircle className="w-5 h-5" />,
          color: 'text-green-500',
          bgColor: 'bg-green-100',
          label: 'Finished'
        }
      case 'FAILED':
        return {
          icon: <AlertCircle className="w-5 h-5" />,
          color: 'text-red-500',
          bgColor: 'bg-red-100',
          label: 'Failed'
        }
      case 'READY':
        return {
          icon: <Clock className="w-5 h-5" />,
          color: 'text-green-500',
          bgColor: 'bg-green-100',
          label: 'Ready'
        }
      default:
        return {
          icon: <Clock className="w-5 h-5" />,
          color: 'text-gray-500',
          bgColor: 'bg-gray-100',
          label: 'Unknown'
        }
    }
  }

  const statusInfo = getStatusInfo()

  // Format last run time
  const formatLastRun = () => {
    if (!job.last_run_finished_at) return 'Never'

    const date = new Date(job.last_run_finished_at)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMins / 60)
    const diffDays = Math.floor(diffHours / 24)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays < 7) return `${diffDays}d ago`
    return date.toLocaleDateString()
  }

  // Format interval to readable string
  const formatInterval = (minutes: number): string => {
    if (minutes < 60) return `${minutes}m`
    const hours = Math.floor(minutes / 60)
    const mins = minutes % 60
    if (mins === 0) return `${hours}h`
    return `${hours}h ${mins}m`
  }



  // Format datetime with timezone
  const formatDateTimeWithTZ = (dateStr: string | undefined): string => {
    if (!dateStr) return 'Never'

    const date = new Date(dateStr)
    const options: Intl.DateTimeFormatOptions = {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      timeZoneName: 'short'
    }

    return date.toLocaleString('en-US', options)
  }

  // Calculate countdown timer
  useEffect(() => {
    if (!job.next_run || !job.active) {
      setCountdown('Calculating...')
      return
    }

    const updateCountdown = () => {
      const now = new Date()
      const nextRun = new Date(job.next_run!)
      const diff = nextRun.getTime() - now.getTime()

      // If time has passed, show "Overdue"
      if (diff <= 0) {
        const overdueMins = Math.floor(Math.abs(diff) / 60000)
        if (overdueMins > 60) {
          const hours = Math.floor(overdueMins / 60)
          setCountdown(`Overdue by ${hours}h`)
        } else if (overdueMins > 0) {
          setCountdown(`Overdue by ${overdueMins}m`)
        } else {
          setCountdown('Starting now...')
        }
        return
      }

      const totalSeconds = Math.floor(diff / 1000)
      const hours = Math.floor(totalSeconds / 3600)
      const minutes = Math.floor((totalSeconds % 3600) / 60)
      const seconds = totalSeconds % 60

      if (hours > 0) {
        setCountdown(`${hours}h ${minutes}m`)
      } else if (minutes > 0) {
        setCountdown(`${minutes}m ${seconds}s`)
      } else {
        setCountdown(`${seconds}s`)
      }
    }

    // Update immediately
    updateCountdown()

    // Update every second
    const interval = setInterval(updateCountdown, 1000)

    return () => clearInterval(interval)
  }, [job.next_run, job.active])

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      onMouseEnter={(e) => {
        setIsHovered(true)
        e.currentTarget.style.borderColor = 'var(--color-1)'
        e.currentTarget.style.boxShadow = '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)'
      }}
      onMouseLeave={(e) => {
        setIsHovered(false)
        e.currentTarget.style.borderColor = 'transparent'
        e.currentTarget.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
      }}
      className={`card p-6 transition-all duration-200 border border-transparent shadow-md ${
        !job.active ? 'opacity-60' : ''
      }`}
    >
      <div className="flex items-center justify-between">
        {/* Left: Logo + Job Info */}
        <div className="flex items-center space-x-4 flex-1">
          {/* Integration Logo */}
          <div className="w-12 h-12 rounded-lg overflow-hidden flex items-center justify-center bg-tertiary">
            <IntegrationLogo
              logoFilename={job.integration_logo_filename || 'default-integration.svg'}
              integrationName={job.integration_type || job.job_name}
              className="w-10 h-10 object-contain"
            />
          </div>

          {/* Job Name and Status */}
          <div className="flex-1">
            <div className="flex items-center space-x-2">
              <h3 className="text-lg font-semibold text-primary">
                {job.job_name.toUpperCase()}
              </h3>
              {!job.active && (
                <span className="text-xs px-2 py-1 rounded bg-gray-200 text-gray-600">
                  Inactive
                </span>
              )}
            </div>

            {/* Show details only when active */}
            {job.active && (
              <div className="flex items-center space-x-4 mt-1">
                {/* Status Badge */}
                <div className={`flex items-center space-x-1 ${statusInfo.color}`}>
                  {statusInfo.icon}
                  <span className="text-sm font-medium">{statusInfo.label}</span>
                </div>

                {/* Schedule Interval */}
                <span className="text-sm text-secondary">
                  Interval: {formatInterval(job.schedule_interval_minutes)}
                </span>

                {/* Last Run */}
                <span className="text-sm text-secondary">
                  Last run: {formatLastRun()}
                </span>

                {/* Error Indicator */}
                {job.error_message && (
                  <span className="text-xs text-red-500 flex items-center space-x-1">
                    <AlertCircle className="w-3 h-3" />
                    <span>Error</span>
                  </span>
                )}

                {/* Retry Count */}
                {job.retry_count > 0 && (
                  <span className="text-xs text-orange-500">
                    Retries: {job.retry_count}
                  </span>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right: Action Buttons */}
        <div className="flex items-center space-x-2">
          {/* Run Now Button - Only show when active */}
          {job.active && (
            <button
              onClick={() => onRunNow(job.id)}
              className="btn-crud-create px-4 py-2 rounded-lg flex items-center space-x-2"
              title="Manually trigger job"
              disabled={job.status === 'RUNNING'}
            >
              <Play className="w-4 h-4" />
              <span>Run Now</span>
            </button>
          )}

          {/* Settings Button - Only show when active */}
          {job.active && (
            <button
              onClick={() => onSettings(job)}
              className="p-2 rounded-lg hover:bg-tertiary transition-colors"
              title="Job Settings"
            >
              <Settings className="w-5 h-5 text-secondary" />
            </button>
          )}

          {/* Details Button - Only show when active */}
          {job.active && (
            <button
              onClick={() => onShowDetails(job.id)}
              className="p-2 rounded-lg hover:bg-tertiary transition-colors"
              title="View Details"
            >
              <Info className="w-5 h-5 text-secondary" />
            </button>
          )}

          {/* On/Off Toggle - Always visible */}
          <div className="flex items-center space-x-2">
            <button
              onClick={() => {
                setIsToggling(true)
                try {
                  onToggleActive(job.id, !job.active)
                } finally {
                  setIsToggling(false)
                }
              }}
              disabled={isToggling}
              className={`relative inline-flex h-5 w-10 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 ${
                job.active
                  ? 'bg-gradient-to-r from-green-500 to-green-600 focus:ring-green-500'
                  : 'bg-gray-300 focus:ring-gray-400'
              } ${isToggling ? 'opacity-50 cursor-not-allowed' : ''}`}
              title={job.active ? 'Deactivate job' : 'Activate job'}
            >
              <span className="sr-only">Toggle job active</span>
              <motion.span
                className="inline-block h-3 w-3 transform rounded-full bg-white shadow-lg"
                animate={{ x: job.active ? 24 : 4 }}
                transition={{ type: 'spring', stiffness: 500, damping: 30 }}
              />
            </button>
            <span className="text-sm text-secondary w-8">
              {job.active ? 'On' : 'Off'}
            </span>
          </div>
        </div>
      </div>

      {/* Progress Bar (if running) */}
      {job.status === 'RUNNING' && (
        <div className="mt-4">
          <div className="w-full bg-tertiary rounded-full h-2 overflow-hidden">
            <motion.div
              className="h-full bg-gradient-to-r from-blue-500 to-blue-600"
              initial={{ width: '0%' }}
              animate={{ width: '100%' }}
              transition={{ duration: 2, repeat: Infinity }}
            />
          </div>
        </div>
      )}

      {/* Additional Info Row - Show when active */}
      {job.active && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="mt-4 pt-4 border-t border-border"
        >
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <span className="text-secondary">Last Run:</span>
              <span className="ml-2 text-primary font-medium text-xs">
                {formatDateTimeWithTZ(job.last_run_finished_at)}
              </span>
            </div>
            <div>
              <span className="text-secondary">Next Run:</span>
              <span className="ml-2 text-primary font-medium text-xs">
                {job.next_run ? formatDateTimeWithTZ(job.next_run) : 'Calculating...'}
              </span>
            </div>
            <div>
              <span className="text-secondary">Countdown:</span>
              <span className="ml-2 text-primary font-medium font-mono">
                {countdown}
              </span>
            </div>
          </div>
        </motion.div>
      )}
    </motion.div>
  )
}

