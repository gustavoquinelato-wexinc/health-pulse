import { useState, useEffect, useRef } from 'react'
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
import { etlWebSocketService, type ProgressUpdate, type StatusUpdate, type CompletionUpdate } from '../services/etlWebSocketService'
import { useTheme } from '../contexts/ThemeContext'

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
  const { theme } = useTheme()
  const [, setIsHovered] = useState(false)
  const [isToggling, setIsToggling] = useState(false)
  const [countdown, setCountdown] = useState<string>('Calculating...')

  // Real-time progress tracking
  const [progressPercentage, setProgressPercentage] = useState<number | null>(null)
  const [currentStep, setCurrentStep] = useState<string | null>(null)
  const [realTimeStatus, setRealTimeStatus] = useState<string>(job.status)
  const [wsVersion, setWsVersion] = useState<number>(etlWebSocketService.getInitializationVersion())

  // Throttle state updates to prevent UI freezing from rapid WebSocket messages
  const lastUpdateRef = useRef<number>(0)
  const THROTTLE_MS = 500 // Only update UI every 500ms max

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

    switch (realTimeStatus) {
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
    // Don't show countdown if job is not active or is currently running
    if (!job.active || ['RUNNING', 'EXTRACTING', 'QUEUED', 'QUEUED_TRANSFORM', 'TRANSFORMING', 'QUEUED_EMBEDDING', 'EMBEDDING'].includes(realTimeStatus)) {
      setCountdown('—')
      return
    }

    if (!job.next_run || job.next_run === null || job.next_run === undefined) {
      setCountdown('—')
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
  }, [job.next_run, job.active, realTimeStatus])

  // Check for WebSocket service reinitialization (e.g., after logout/login)
  useEffect(() => {
    const currentVersion = etlWebSocketService.getInitializationVersion()
    if (currentVersion !== wsVersion) {
      // Service was reinitialized, update version to trigger reconnection
      setWsVersion(currentVersion)
    }
  }, [wsVersion])

  // WebSocket connection for real-time progress tracking - only for active jobs
  useEffect(() => {
    // Only establish WebSocket connection for active jobs
    if (!job.active) {

      return
    }



    const cleanup = etlWebSocketService.connectToJob(job.job_name, {
      onProgress: (data: ProgressUpdate) => {
        // Throttle progress updates to prevent UI freezing
        const now = Date.now()
        if (now - lastUpdateRef.current < THROTTLE_MS) {
          return // Skip this update
        }
        lastUpdateRef.current = now

        setProgressPercentage(data.percentage)
        setCurrentStep(data.step)
        // Update status to RUNNING when we receive progress updates (if not already running)
        if (realTimeStatus !== 'RUNNING') {
          setRealTimeStatus('RUNNING')
        }
      },
      onStatus: (data: StatusUpdate) => {

        setRealTimeStatus(data.status)

        // Clear progress when job finishes
        if (!['EXTRACTING', 'QUEUED', 'QUEUED_TRANSFORM', 'TRANSFORMING', 'QUEUED_EMBEDDING', 'EMBEDDING'].includes(data.status)) {
          setProgressPercentage(null)
          setCurrentStep(null)
        }
      },
      onCompletion: (data: CompletionUpdate) => {

        setRealTimeStatus(data.success ? 'FINISHED' : 'FAILED')
        setProgressPercentage(null)
        setCurrentStep(null)

        // Notify parent component to refresh jobs
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('etl-job-completed', {
            detail: { jobId: job.id, success: data.success }
          }))
        }
      }
    })

    // Clear progress if job is not running
    if (!['EXTRACTING', 'QUEUED', 'QUEUED_TRANSFORM', 'TRANSFORMING', 'QUEUED_EMBEDDING', 'EMBEDDING'].includes(realTimeStatus)) {
      setProgressPercentage(null)
      setCurrentStep(null)
    }

    return cleanup
  }, [job.job_name, job.active, wsVersion]) // Include wsVersion to reconnect when service reinitializes

  // Update real-time status when job status changes
  useEffect(() => {
    setRealTimeStatus(job.status)
  }, [job.status])

  // Clear progress when job becomes inactive
  useEffect(() => {
    if (!job.active) {
      setProgressPercentage(null)
      setCurrentStep(null)
      setRealTimeStatus(job.status) // Reset to actual job status
    }
  }, [job.active, job.status])

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{
        opacity: 1,
        y: 0,
        scale: job.active ? 1 : 0.97  // Slightly smaller when inactive
      }}
      onMouseEnter={(e) => {
        setIsHovered(true)
        e.currentTarget.style.borderColor = 'var(--color-1)'
        e.currentTarget.style.boxShadow = theme === 'dark'
          ? '0 2px 2px 0 rgba(255, 255, 255, 0.08)'
          : '0 2px 2px 0 rgba(0, 0, 0, 0.12)'
      }}
      onMouseLeave={(e) => {
        setIsHovered(false)
        e.currentTarget.style.borderColor = theme === 'dark' ? '#4a5568' : '#9ca3af'
        e.currentTarget.style.boxShadow = theme === 'dark'
          ? '0 2px 2px 0 rgba(255, 255, 255, 0.05)'
          : '0 2px 2px 0 rgba(0, 0, 0, 0.1)'
      }}
      className="card transition-all duration-200 shadow-md"
      style={{
        backgroundColor: !job.active
          ? (theme === 'dark' ? 'rgba(0, 0, 0, 0.3)' : 'rgba(0, 0, 0, 0.04)')
          : undefined,
        opacity: !job.active ? 0.6 : 1,  // Darker when inactive
        padding: !job.active ? '1rem' : '1.5rem'  // Smaller padding when inactive (p-4 vs p-6)
      }}
    >
      <div className="flex items-center justify-between">
        {/* Left: Logo + Job Info */}
        <div className="flex items-center space-x-4 flex-1">
          {/* Integration Logo */}
          <div className="w-12 h-12 rounded-lg overflow-hidden flex items-center justify-center">
            <IntegrationLogo
              logoFilename={job.integration_logo_filename || 'default-integration.svg'}
              integrationName={job.integration_type || job.job_name}
              className="w-10 h-10 object-contain"
            />
          </div>

          {/* Job Name and Status */}
          <div className="flex-1">
            <div className="flex items-center space-x-2">
              <h3 className={`text-lg font-semibold ${!job.active ? 'text-gray-400' : 'text-primary'}`}>
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
              disabled={['EXTRACTING', 'QUEUED', 'QUEUED_TRANSFORM', 'TRANSFORMING', 'QUEUED_EMBEDDING', 'EMBEDDING'].includes(realTimeStatus)}
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
      {['EXTRACTING', 'QUEUED', 'QUEUED_TRANSFORM', 'TRANSFORMING', 'QUEUED_EMBEDDING', 'EMBEDDING'].includes(realTimeStatus) && (
        <div className="mt-4">
          {/* Progress Bar */}
          <div className="w-full bg-tertiary rounded-full h-2 overflow-hidden">
            <motion.div
              className="h-full bg-gradient-to-r from-blue-500 to-blue-600"
              initial={{ width: '0%' }}
              animate={{
                width: progressPercentage !== null ? `${progressPercentage}%` : '0%'
              }}
              transition={{ duration: 0.5, ease: 'easeOut' }}
            />
          </div>

          {/* Progress Info Row */}
          <div className="flex justify-between items-center mt-1">
            {/* Current Step Message (left) */}
            <div className="text-xs text-secondary flex-1">
              {currentStep || 'Processing...'}
            </div>

            {/* Progress Percentage (right) */}
            {progressPercentage !== null && (
              <div className="text-xs text-secondary ml-2">
                {Math.round(progressPercentage)}%
              </div>
            )}
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

