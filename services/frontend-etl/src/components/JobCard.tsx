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
import { etlWebSocketService, type JobProgress } from '../services/etlWebSocketService'
import { jobsApi } from '../services/etlApiService'
import { useTheme } from '../contexts/ThemeContext'
import { useAuth } from '../contexts/AuthContext'

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
  const { user } = useAuth()
  const [, setIsHovered] = useState(false)
  const [isToggling, setIsToggling] = useState(false)
  const [countdown, setCountdown] = useState<string>('Calculating...')

  // Real-time worker status tracking
  const [jobProgress, setJobProgress] = useState<JobProgress | null>(null)
  const [realTimeStatus, setRealTimeStatus] = useState<string>(job.status)
  const [wsVersion, setWsVersion] = useState<number>(etlWebSocketService.getInitializationVersion())
  const [isJobRunning, setIsJobRunning] = useState<boolean>(false)
  const [finishedTransitionTimer, setFinishedTransitionTimer] = useState<NodeJS.Timeout | null>(null)
  const [resetCountdown, setResetCountdown] = useState<number | null>(null)
  const [jobToken, setJobToken] = useState<string | null>(null)  // 🔑 Store execution token
  // Track if we're currently resetting to prevent WebSocket from interfering
  const isResettingRef = useRef<boolean>(false)
  // Track reset attempts for exponential backoff: 30s → 60s → 180s
  const resetAttemptsRef = useRef<number>(0)
  // Throttle state updates to prevent UI freezing from rapid WebSocket messages
  // Track WebSocket connection to prevent React StrictMode double connections
  const wsConnectionRef = useRef<(() => void) | null>(null)
  // 🔑 Track when countdown started (local time) to avoid relying on stale job.last_run_finished_at
  const countdownStartTimeRef = useRef<number | null>(null)
  // 🔑 Track the initial countdown value (30, 60, 180, or 300 seconds)
  const initialCountdownRef = useRef<number | null>(null)

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
      case 'RATE_LIMIT_REACHED':
        return {
          icon: <AlertCircle className="w-5 h-5" />,
          color: 'text-yellow-600',
          bgColor: 'bg-yellow-100',
          label: 'Rate Limited'
        }
      case 'READY':
        return {
          icon: <Clock className="w-5 h-5" />,
          color: 'text-cyan-500',
          bgColor: 'bg-cyan-100',
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

  // Initialize reset countdown if job is FINISHED (handles page refresh)
  useEffect(() => {
    if (realTimeStatus === 'FINISHED' && resetCountdown === null) {
      // Job is finished but countdown not started - initialize it
      // Query the server to get accurate server time and check if steps are truly finished
      const initializeCountdown = async () => {
        try {
          if (!user?.tenant_id) {
            return
          }

          const response = await jobsApi.checkJobCompletion(job.id, user.tenant_id)
          const serverTime = new Date(response.data.server_time).getTime()
          const finishedTime = job.last_run_finished_at ? new Date(job.last_run_finished_at).getTime() : 0
          const elapsedSeconds = Math.floor((serverTime - finishedTime) / 1000)

          // Check if all steps are truly finished
          if (response.data.all_finished) {
            // All steps finished, use standard 30-second countdown
            const remainingSeconds = Math.max(0, 30 - elapsedSeconds)
            if (remainingSeconds > 0) {
              setResetCountdown(remainingSeconds)
              resetAttemptsRef.current = 0
            } else {
              // More than 30 seconds have passed, trigger reset immediately
              setResetCountdown(0)
              resetAttemptsRef.current = 0
            }
          } else {
            // Steps still running, use exponential backoff retry logic
            // Start with 30 seconds for first attempt
            setResetCountdown(30)
            resetAttemptsRef.current = 0
          }
        } catch (error) {
          // Silently handle error - default to 30 second countdown
          setResetCountdown(30)
          resetAttemptsRef.current = 0
        }
      }

      initializeCountdown()
    }
  }, [realTimeStatus, job.last_run_finished_at, job.id, user?.tenant_id])

  // Reset countdown timer - calculates remaining time based on server time (not local state)
  // 🔑 Initialize countdown start time when countdown is first set
  // This ensures the countdown starts AFTER the UI has rendered the FINISHED status
  useEffect(() => {
    if (resetCountdown === null || realTimeStatus !== 'FINISHED') {
      return
    }

    // Only set the start time once, when the countdown is first initialized
    if (countdownStartTimeRef.current === null) {
      countdownStartTimeRef.current = Date.now()
    }
  }, [resetCountdown, realTimeStatus])

  // 🔑 Countdown timer effect - decrements every second
  useEffect(() => {
    if (resetCountdown === null || realTimeStatus !== 'FINISHED') {
      return
    }

    if (countdownStartTimeRef.current === null) {
      // Should not happen, but fallback just in case
      return
    }

    const interval = setInterval(() => {
      try {
        const elapsedSeconds = Math.floor((Date.now() - countdownStartTimeRef.current!) / 1000)
        const initialCountdown = initialCountdownRef.current || 30
        const remainingSeconds = Math.max(0, initialCountdown - elapsedSeconds)

        if (remainingSeconds <= 0) {
          // Timer expired, trigger reset
          setResetCountdown(0)
        } else {
          // Update countdown based on elapsed time
          setResetCountdown(remainingSeconds)
        }
      } catch (error) {
        // Silently handle error - continue with local countdown
        setResetCountdown(prev => {
          if (prev === null || prev <= 0) {
            return null
          }
          return prev - 1
        })
      }
    }, 1000)

    return () => clearInterval(interval)
  }, [realTimeStatus])

  // Trigger reset when countdown reaches 0
  useEffect(() => {
    if (resetCountdown === 0) {
      // Perform the reset
      const performReset = async () => {
        try {
          // Mark that we're resetting to prevent WebSocket interference
          isResettingRef.current = true

          if (user?.tenant_id) {
            // 🔑 Check for remaining messages in embedding queue using token
            if (jobToken) {
              try {
                const remainingCheck = await jobsApi.checkRemainingMessages(job.id, jobToken, user.tenant_id)

                if (remainingCheck.data.has_remaining_messages) {
                  // Messages still being processed, extend countdown
                  console.info(`⏱️ Messages still in queue, extending countdown for job ${job.id}`)

                  // Extend countdown based on attempt number (exponential backoff)
                  const nextCountdown = resetAttemptsRef.current === 0 ? 60 : (resetAttemptsRef.current === 1 ? 180 : 300)
                  setResetCountdown(nextCountdown)
                  resetAttemptsRef.current += 1
                  countdownStartTimeRef.current = Date.now()
                  initialCountdownRef.current = nextCountdown
                  return
                }
              } catch (error) {
                console.warn(`Failed to check remaining messages: ${error}`)
                // Continue with reset anyway
              }
            }

            // First check if all steps are truly finished
            const completionCheck = await jobsApi.checkJobCompletion(job.id, user.tenant_id)

            if (completionCheck.data.all_finished) {
              // All steps are finished, proceed with reset
              await jobsApi.resetJobStatus(job.id, user.tenant_id)

              // Fetch updated job status to get final step states
              const updatedStatus = await jobsApi.checkJobCompletion(job.id, user.tenant_id)

              // Update job progress with reset step statuses (all idle)
              if (updatedStatus.data.steps) {
                const stepsData: { [stepName: string]: any } = {}
                Object.entries(updatedStatus.data.steps).forEach(([stepName, stepData]: [string, any]) => {
                  stepsData[stepName] = {
                    order: stepData.order || 0,
                    display_name: stepData.display_name || stepName,
                    extraction: stepData.extraction || 'idle',
                    transform: stepData.transform || 'idle',
                    embedding: stepData.embedding || 'idle'
                  }
                })

                setJobProgress({
                  extraction: { status: 'idle' },
                  transform: { status: 'idle' },
                  embedding: { status: 'idle' },
                  isActive: false,
                  overall: 'READY',  // 🔑 Set to READY after reset
                  token: null,  // 🔑 Clear token when resetting
                  steps: stepsData
                })

                // 🔑 Clear the stored token
                setJobToken(null)
              }

              resetAttemptsRef.current = 0 // Reset attempt counter
              countdownStartTimeRef.current = null  // 🔑 Clear countdown start time
              initialCountdownRef.current = null  // 🔑 Clear initial countdown value
              setRealTimeStatus('READY')
              setFinishedTransitionTimer(null)
              setResetCountdown(null)
              setIsJobRunning(false)  // 🔑 Ensure Run Now button is re-enabled
            } else {
              // Steps are still running, schedule another reset attempt with exponential backoff
              resetAttemptsRef.current += 1
              // Backoff: 30s → 60s → 180s → 300s (and keep 300s for all subsequent attempts)
              let nextDelay: number
              if (resetAttemptsRef.current === 1) {
                nextDelay = 60
              } else if (resetAttemptsRef.current === 2) {
                nextDelay = 180
              } else {
                nextDelay = 300  // Final tier: keep retrying every 5 minutes
              }

              setResetCountdown(nextDelay)
              setFinishedTransitionTimer(null)
            }
          }
        } catch (error) {
          // Silently handle error - retry with exponential backoff
          resetAttemptsRef.current += 1
          let nextDelay: number
          if (resetAttemptsRef.current === 1) {
            nextDelay = 60
          } else if (resetAttemptsRef.current === 2) {
            nextDelay = 180
          } else {
            nextDelay = 300
          }
          setResetCountdown(nextDelay)
        } finally {
          // Clear the resetting flag after a short delay to allow UI to update
          setTimeout(() => {
            isResettingRef.current = false
          }, 500)
        }
      }
      performReset()
    }
  }, [resetCountdown, job.id, user?.tenant_id])

  // Sync realTimeStatus with job.status prop when it changes (handles API updates)
  useEffect(() => {
    // Only update if the job status has actually changed
    if (job.status !== realTimeStatus) {
      setRealTimeStatus(job.status)
    }
  }, [job.status])

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

      const cleanup = etlWebSocketService.connectToJob(tenantId, job.id, {
        onJobProgress: (data: JobProgress) => {
          // If we're currently resetting, ignore WebSocket updates to prevent interference
          if (isResettingRef.current) {
            return
          }

          // Always update job progress and step statuses (even after FINISHED)
          setJobProgress(data)
          setIsJobRunning(data.isActive)

          // 🔑 Capture the execution token when job starts running
          if (data.overall === 'RUNNING' && !jobToken && data.token) {
            setJobToken(data.token)
          }

          // 🔑 CRITICAL FIX: Use the overall status from database directly
          // Don't try to calculate it from individual worker statuses
          // The backend already has the correct overall status
          if (data.overall === 'RUNNING') {
            setRealTimeStatus('RUNNING')
            // Clear any existing finished transition timer
            if (finishedTransitionTimer) {
              clearTimeout(finishedTransitionTimer)
              setFinishedTransitionTimer(null)
            }
          } else if (data.overall === 'FAILED') {
            setRealTimeStatus('FAILED')
            // Clear any existing finished transition timer
            if (finishedTransitionTimer) {
              clearTimeout(finishedTransitionTimer)
              setFinishedTransitionTimer(null)
            }
          } else if (data.overall === 'FINISHED') {
            // 🔑 CRITICAL: Set countdown FIRST before updating status
            // This ensures the countdown effect triggers immediately
            if (resetCountdown === null) {
              // Only initialize countdown if not already running
              setResetCountdown(30)
              initialCountdownRef.current = 30  // 🔑 Track initial countdown value
              resetAttemptsRef.current = 0
              // 🔑 Set countdown start time immediately when FINISHED is received
              countdownStartTimeRef.current = Date.now()
            } else {
              // Countdown already running - extend it if possible
              // Extend up to 300 seconds (5 minutes) when new messages arrive
              setResetCountdown(prev => {
                if (prev === null) return 30
                // Extend countdown but cap at 300 seconds
                const newCountdown = Math.min(prev + 30, 300)
                initialCountdownRef.current = newCountdown  // 🔑 Update initial countdown value
                return newCountdown
              })
            }

            // 🔑 THEN update the status to FINISHED
            setRealTimeStatus('FINISHED')

            // Clear any existing timer first
            if (finishedTransitionTimer) {
              clearTimeout(finishedTransitionTimer)
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
      // Clear any pending finished transition timer
      if (finishedTransitionTimer) {
        clearTimeout(finishedTransitionTimer)
        setFinishedTransitionTimer(null)
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
      // Clear any pending finished transition timer
      if (finishedTransitionTimer) {
        clearTimeout(finishedTransitionTimer)
        setFinishedTransitionTimer(null)
      }
    }
  }, [job.active, job.status, finishedTransitionTimer])

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

                {/* Rate Limit Countdown - Show when rate limited */}
                {realTimeStatus === 'RATE_LIMIT_REACHED' && (
                  <div className="flex items-center space-x-1 text-yellow-600">
                    <Clock className="w-4 h-4" />
                    <span className="text-sm font-medium">Resumes in {countdown}</span>
                  </div>
                )}

                {/* Reset Countdown Timer - Show when resetting */}
                {resetCountdown !== null && realTimeStatus !== 'RATE_LIMIT_REACHED' && (
                  <div className="flex items-center space-x-1 text-blue-500">
                    <Clock className="w-4 h-4" />
                    <span className="text-sm font-medium">Resetting in {resetCountdown}s</span>
                  </div>
                )}

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
              title={realTimeStatus === 'RATE_LIMIT_REACHED' ? 'Job will resume automatically when rate limit resets' : 'Manually trigger job'}
              disabled={isJobRunning || realTimeStatus === 'RUNNING' || realTimeStatus === 'RATE_LIMIT_REACHED'}
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
          {/* Step-Based Progress Display */}
          <div className="mt-3 space-y-1.5">
            {/* Steps Grid - 4 steps per row on desktop, 2 on mobile */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
              {getAvailableSteps().map((stepName) => {
                const stepDisplayName = getStepDisplayName(stepName)

                return (
                  <div key={stepName} className="flex items-center justify-between p-2 bg-background/50 rounded border border-border/30">
                    {/* Step Name */}
                    <span className="text-secondary font-medium text-xs leading-tight truncate flex-1 mr-2" title={stepDisplayName}>
                      {stepDisplayName}
                    </span>

                    {/* Worker Status Grid - 3 circles with labels vertically centered */}
                    <div className="flex items-center space-x-2">
                      {/* Extraction */}
                      <div className="flex flex-col items-center space-y-0.5">
                        <div
                          className={`w-3 h-3 rounded-full ${
                            getStepStatus(stepName, 'extraction') === 'running' ? 'bg-blue-500 animate-pulse' :
                            getStepStatus(stepName, 'extraction') === 'finished' ? 'bg-green-500' :
                            getStepStatus(stepName, 'extraction') === 'failed' ? 'bg-red-500' :
                            'bg-gray-300'
                          }`}
                          title={`Extraction: ${getStepStatus(stepName, 'extraction')}`}
                        />
                        <span className="text-[8px] text-secondary font-mono">E</span>
                      </div>
                      {/* Transform */}
                      <div className="flex flex-col items-center space-y-0.5">
                        <div
                          className={`w-3 h-3 rounded-full ${
                            getStepStatus(stepName, 'transform') === 'running' ? 'bg-blue-500 animate-pulse' :
                            getStepStatus(stepName, 'transform') === 'finished' ? 'bg-green-500' :
                            getStepStatus(stepName, 'transform') === 'failed' ? 'bg-red-500' :
                            'bg-gray-300'
                          }`}
                          title={`Transform: ${getStepStatus(stepName, 'transform')}`}
                        />
                        <span className="text-[8px] text-secondary font-mono">T</span>
                      </div>
                      {/* Embedding */}
                      <div className="flex flex-col items-center space-y-0.5">
                        <div
                          className={`w-3 h-3 rounded-full ${
                            getStepStatus(stepName, 'embedding') === 'running' ? 'bg-blue-500 animate-pulse' :
                            getStepStatus(stepName, 'embedding') === 'finished' ? 'bg-green-500' :
                            getStepStatus(stepName, 'embedding') === 'failed' ? 'bg-red-500' :
                            'bg-gray-300'
                          }`}
                          title={`Embedding: ${getStepStatus(stepName, 'embedding')}`}
                        />
                        <span className="text-[8px] text-secondary font-mono">E</span>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Color Legend */}
            <div className="mt-3 pt-2">
              <div className="flex items-center space-x-3 text-[10px] text-secondary">
                <div className="flex items-center space-x-1">
                  <div className="w-2 h-2 bg-gray-300 rounded-full" />
                  <span>Idle</span>
                </div>
                <div className="flex items-center space-x-1">
                  <div className="w-2 h-2 bg-blue-500 rounded-full" />
                  <span>Running</span>
                </div>
                <div className="flex items-center space-x-1">
                  <div className="w-2 h-2 bg-green-500 rounded-full" />
                  <span>Done</span>
                </div>
                <div className="flex items-center space-x-1">
                  <div className="w-2 h-2 bg-red-500 rounded-full" />
                  <span>Failed</span>
                </div>
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
                {realTimeStatus === 'RUNNING' ? '—' : (job.next_run ? formatDateTimeWithTZ(job.next_run) : '—')}
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

