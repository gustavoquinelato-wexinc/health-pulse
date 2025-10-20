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
import { etlWebSocketService, type WorkerStatusUpdate, type JobProgress } from '../services/etlWebSocketService'
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

  // Real-time worker status tracking
  const [jobProgress, setJobProgress] = useState<JobProgress | null>(null)
  const [realTimeStatus, setRealTimeStatus] = useState<string>(job.status)
  const [wsVersion, setWsVersion] = useState<number>(etlWebSocketService.getInitializationVersion())
  const [isJobRunning, setIsJobRunning] = useState<boolean>(false)
  const [isWebSocketConnected, setIsWebSocketConnected] = useState<boolean>(false)
  // Throttle state updates to prevent UI freezing from rapid WebSocket messages
  const lastUpdateRef = useRef<number>(0)
  // Track WebSocket connection to prevent React StrictMode double connections
  const wsConnectionRef = useRef<(() => void) | null>(null)

  // Get display name for step from step data or fallback
  const getStepDisplayName = (stepName: string) => {
    if (jobProgress?.steps && jobProgress.steps[stepName]?.display_name) {
      return jobProgress.steps[stepName].display_name
    }
    // Fallback: format step name nicely
    return stepName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
  }

  // Get available steps from job progress data, sorted by order
  const getAvailableSteps = () => {
    if (jobProgress?.steps) {
      // Sort steps by order field
      return Object.entries(jobProgress.steps)
        .sort(([, a], [, b]) => (a.order || 0) - (b.order || 0))
        .map(([stepName]) => stepName)
    }

    // Fallback to default Jira steps if no step data available
    return ['jira_projects_and_issue_types', 'jira_statuses_and_relationships', 'jira_issues_with_changelogs', 'jira_dev_status']
  }

  // Helper function to get current step being processed
  const getCurrentStep = () => {
    if (!jobProgress?.isActive) return null

    // Check which worker is currently running and return a user-friendly step name
    if (jobProgress.extraction.status === 'running' && jobProgress.extraction.step) {
      return `Extracting ${getStepDisplayName(jobProgress.extraction.step)}...`
    }
    if (jobProgress.transform.status === 'running' && jobProgress.transform.step) {
      return `Transforming ${getStepDisplayName(jobProgress.transform.step)}...`
    }
    if (jobProgress.embedding.status === 'running' && jobProgress.embedding.step) {
      return `Creating embeddings for ${getStepDisplayName(jobProgress.embedding.step)}...`
    }

    // Fallback to generic messages
    if (jobProgress.extraction.status === 'running') {
      return 'Extracting data...'
    }
    if (jobProgress.transform.status === 'running') {
      return 'Transforming data...'
    }
    if (jobProgress.embedding.status === 'running') {
      return 'Creating embeddings...'
    }

    return null
  }

  // Helper function to get step status from WebSocket data
  const getStepStatus = (stepName: string, workerType: 'extraction' | 'transform' | 'embedding') => {
    // Use detailed step data if available
    if (jobProgress?.steps && jobProgress.steps[stepName]) {
      return jobProgress.steps[stepName][workerType]
    }

    // Fallback to current worker status matching
    if (!jobProgress) return 'idle'

    const worker = jobProgress[workerType]
    if (worker.step === stepName) {
      return worker.status
    }

    return 'idle'
  }

  // Helper function to get step progress overview
  const getStepProgress = (stepName: string) => {
    const extraction = getStepStatus(stepName, 'extraction')
    const transform = getStepStatus(stepName, 'transform')
    const embedding = getStepStatus(stepName, 'embedding')

    // Determine overall step status
    if ([extraction, transform, embedding].includes('running')) return 'running'
    if ([extraction, transform, embedding].includes('failed')) return 'failed'
    if ([extraction, transform, embedding].every(s => s === 'finished')) return 'finished'
    if ([extraction, transform, embedding].some(s => s === 'finished')) return 'partial'

    return 'idle'
  }

  // Helper function to get worker status display info
  const getWorkerStatusInfo = (workerType: 'extraction' | 'transform' | 'embedding') => {
    if (!jobProgress) {
      return {
        status: 'idle',
        color: 'bg-gray-300',
        textColor: 'text-gray-500',
        displayText: 'Idle',
        stepText: ''
      }
    }

    const worker = jobProgress[workerType]
    const stepText = worker.step ? ` (${getStepDisplayName(worker.step)})` : ''

    switch (worker.status) {
      case 'running':
        return {
          status: 'running',
          color: 'bg-blue-500 animate-pulse',
          textColor: 'text-blue-600',
          displayText: 'Running',
          stepText
        }
      case 'finished':
        return {
          status: 'finished',
          color: 'bg-green-500',
          textColor: 'text-green-600',
          displayText: 'Finished',
          stepText: ''
        }
      case 'failed':
        return {
          status: 'failed',
          color: 'bg-red-500',
          textColor: 'text-red-600',
          displayText: 'Failed',
          stepText: ''
        }
      default:
        return {
          status: 'idle',
          color: 'bg-gray-300',
          textColor: 'text-gray-500',
          displayText: 'Idle',
          stepText: ''
        }
    }
  }
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
    if (!job.active || realTimeStatus === 'RUNNING' || isJobRunning) {
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
      // Clean up any existing connection
      if (wsConnectionRef.current) {
        wsConnectionRef.current()
        wsConnectionRef.current = null
      }
      return
    }

    // If we already have a connection, don't create another one (React StrictMode protection)
    if (wsConnectionRef.current) {
      return wsConnectionRef.current
    }

    // Function to attempt WebSocket connection with retry for service initialization
    const connectWithRetry = (retryCount = 0): (() => void) => {
      // Check if service is ready
      if (!etlWebSocketService.isReady()) {
        if (retryCount < 10) { // Retry up to 10 times (1 second total)
          setTimeout(() => connectWithRetry(retryCount + 1), 100)
        }
        return () => {} // Return empty cleanup function
      }

      // Get tenant ID from job or context (assuming it's available)
      const tenantId = 1 // TODO: Get from context or job data

      console.log(`[JobCard] Connecting to WebSocket for job ${job.id}, tenant ${tenantId}`)

      const cleanup = etlWebSocketService.connectToJob(tenantId, job.id, {
        onWorkerStatus: (data: WorkerStatusUpdate) => {
          console.log(`[JobCard] Received worker status:`, data)

          // Throttle updates to prevent UI freezing
          const now = Date.now()
          if (now - lastUpdateRef.current < THROTTLE_MS) {
            return
          }
          lastUpdateRef.current = now

          // Update real-time status based on worker activity
          if (data.status === 'running') {
            setRealTimeStatus('RUNNING')
            setIsJobRunning(true)
          } else if (data.status === 'failed') {
            setRealTimeStatus('FAILED')
            setIsJobRunning(false)
          }
        },
        onJobProgress: (data: JobProgress) => {
          console.log(`[JobCard] Received job progress:`, data)

          setJobProgress(data)
          setIsJobRunning(data.isActive)
          setIsWebSocketConnected(true) // Mark as connected when receiving data

          // Update overall status based on job progress
          if (data.isActive) {
            setRealTimeStatus('RUNNING')
          } else {
            // Check if all workers finished successfully
            const allFinished = data.extraction.status === 'finished' &&
                              data.transform.status === 'finished' &&
                              data.embedding.status === 'finished'
            const anyFailed = data.extraction.status === 'failed' ||
                            data.transform.status === 'failed' ||
                            data.embedding.status === 'failed'

            if (anyFailed) {
              setRealTimeStatus('FAILED')
            } else if (allFinished) {
              setRealTimeStatus('FINISHED')
            }
          }
        }
      })

      return cleanup
    }

    const cleanup = connectWithRetry()
    wsConnectionRef.current = cleanup

    // Return cleanup function that clears the ref and calls the actual cleanup
    return () => {
      if (wsConnectionRef.current) {
        wsConnectionRef.current()
        wsConnectionRef.current = null
      }
    }
  }, [job.id, job.active, wsVersion]) // Include wsVersion to reconnect when service reinitializes

  // Update real-time status when job status changes
  useEffect(() => {
    setRealTimeStatus(job.status)
  }, [job.status])

  // Clear state when job becomes inactive
  useEffect(() => {
    if (!job.active) {
      setRealTimeStatus(job.status) // Reset to actual job status
      setJobProgress(null) // Clear worker progress
      setIsJobRunning(false)
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
              disabled={isJobRunning || realTimeStatus === 'RUNNING'}
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

      {/* Worker Status Display (show when job is running or has worker progress) */}
      {(realTimeStatus === 'RUNNING' || isJobRunning || jobProgress) && (
        <div className="mt-4">
          {/* Current Step Message */}
          {getCurrentStep() && (
            <div className="text-xs text-secondary mb-2">
              {getCurrentStep()}
            </div>
          )}

          {/* Step-Based Progress Display */}
          <div className="mt-3 space-y-1.5">
            {/* Steps Grid - Dynamic Layout */}
            <div className={`grid gap-2 text-xs ${getAvailableSteps().length <= 2 ? 'grid-cols-1' : 'grid-cols-2'}`}>
              {getAvailableSteps().map((stepName) => {
                const stepProgress = getStepProgress(stepName)
                const stepDisplayName = getStepDisplayName(stepName)

                return (
                  <div key={stepName} className="flex items-center justify-between p-2 bg-background/50 rounded border border-border/30">
                    {/* Step Name */}
                    <span className="text-secondary font-medium text-xs leading-tight truncate flex-1 mr-2" title={stepDisplayName}>
                      {stepDisplayName}
                    </span>

                    {/* Worker Status Grid */}
                    <div className="flex flex-col space-y-0.5">
                      <div className="flex items-center space-x-0.5">
                        {/* Extraction */}
                        <div
                          className={`w-1.5 h-1.5 rounded-sm ${
                            getStepStatus(stepName, 'extraction') === 'running' ? 'bg-blue-500 animate-pulse' :
                            getStepStatus(stepName, 'extraction') === 'finished' ? 'bg-green-500' :
                            getStepStatus(stepName, 'extraction') === 'failed' ? 'bg-red-500' :
                            'bg-gray-300'
                          }`}
                          title={`Extraction: ${getStepStatus(stepName, 'extraction')}`}
                        />
                        {/* Transform */}
                        <div
                          className={`w-1.5 h-1.5 rounded-sm ${
                            getStepStatus(stepName, 'transform') === 'running' ? 'bg-blue-500 animate-pulse' :
                            getStepStatus(stepName, 'transform') === 'finished' ? 'bg-green-500' :
                            getStepStatus(stepName, 'transform') === 'failed' ? 'bg-red-500' :
                            'bg-gray-300'
                          }`}
                          title={`Transform: ${getStepStatus(stepName, 'transform')}`}
                        />
                        {/* Embedding */}
                        <div
                          className={`w-1.5 h-1.5 rounded-sm ${
                            getStepStatus(stepName, 'embedding') === 'running' ? 'bg-blue-500 animate-pulse' :
                            getStepStatus(stepName, 'embedding') === 'finished' ? 'bg-green-500' :
                            getStepStatus(stepName, 'embedding') === 'failed' ? 'bg-red-500' :
                            'bg-gray-300'
                          }`}
                          title={`Embedding: ${getStepStatus(stepName, 'embedding')}`}
                        />
                      </div>

                      {/* Overall Step Status */}
                      <div className="flex justify-center">
                        <div className={`text-xs font-bold ${
                          stepProgress === 'running' ? 'text-blue-600' :
                          stepProgress === 'finished' ? 'text-green-600' :
                          stepProgress === 'failed' ? 'text-red-600' :
                          stepProgress === 'partial' ? 'text-yellow-600' :
                          'text-gray-400'
                        }`}>
                          {stepProgress === 'running' ? '⚡' :
                           stepProgress === 'finished' ? '✓' :
                           stepProgress === 'failed' ? '✗' :
                           stepProgress === 'partial' ? '◐' :
                           '○'}
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Compact Legend */}
            <div className="flex items-center justify-between pt-1.5 border-t border-border/30">
              <div className="flex items-center space-x-2 text-[10px] text-secondary">
                <div className="flex items-center space-x-0.5">
                  <div className="w-1.5 h-1.5 bg-gray-300 rounded-sm" />
                  <span>Idle</span>
                </div>
                <div className="flex items-center space-x-0.5">
                  <div className="w-1.5 h-1.5 bg-blue-500 rounded-sm" />
                  <span>Run</span>
                </div>
                <div className="flex items-center space-x-0.5">
                  <div className="w-1.5 h-1.5 bg-green-500 rounded-sm" />
                  <span>Done</span>
                </div>
              </div>
              <div className="text-[10px] text-secondary font-mono">
                E·T·V
              </div>
            </div>
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

