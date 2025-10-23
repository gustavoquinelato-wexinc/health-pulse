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
  const [resetStartTime, setResetStartTime] = useState<number | null>(null)
  // Throttle state updates to prevent UI freezing from rapid WebSocket messages
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
      // Query the server to get accurate server time
      const initializeCountdown = async () => {
        try {
          if (!user?.tenant_id) {
            console.warn(`⚠️ Cannot initialize countdown: user or tenant_id not available`)
            return
          }

          const response = await jobsApi.checkJobCompletion(job.id, user.tenant_id)
          const serverTime = new Date(response.data.server_time).getTime()
          const finishedTime = job.last_run_finished_at ? new Date(job.last_run_finished_at).getTime() : 0
          const elapsedSeconds = Math.floor((serverTime - finishedTime) / 1000)
          const remainingSeconds = Math.max(0, 30 - elapsedSeconds)

          console.log(`🔄 Reset countdown calculation (using server time):`)
          console.log(`   last_run_finished_at: ${job.last_run_finished_at}`)
          console.log(`   server_time: ${response.data.server_time}`)
          console.log(`   elapsedSeconds: ${elapsedSeconds}`)
          console.log(`   remainingSeconds: ${remainingSeconds}`)

          if (remainingSeconds > 0) {
            console.log(`🔄 Restoring reset countdown: ${remainingSeconds}s remaining`)
            setResetCountdown(remainingSeconds)
            setResetStartTime(serverTime)
          } else {
            // More than 30 seconds have passed, reset immediately
            console.log(`🔄 More than 30s passed since job finished, resetting immediately`)
            setResetCountdown(null)
          }
        } catch (error) {
          console.error(`❌ Error initializing countdown:`, error)
        }
      }

      initializeCountdown()
    }
  }, [realTimeStatus, job.last_run_finished_at, job.id, user?.tenant_id])

  // Reset countdown timer - decrements every second
  useEffect(() => {
    if (resetCountdown === null || resetCountdown <= 0) {
      return
    }

    const interval = setInterval(() => {
      setResetCountdown(prev => {
        if (prev === null || prev <= 0) {
          return null
        }
        // Decrement, allowing it to reach 0 so the reset trigger effect can fire
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(interval)
  }, [resetCountdown])

  // Trigger reset when countdown reaches 0
  useEffect(() => {
    if (resetCountdown === 0) {
      console.log(`⏰ Reset countdown reached 0, triggering reset now`)
      // Perform the reset
      const performReset = async () => {
        try {
          if (user?.tenant_id) {
            await jobsApi.resetJobStatus(job.id, user.tenant_id)
            console.log(`✅ Job ${job.id} status reset to READY in database (countdown timeout)`)
          }
        } catch (error) {
          console.error(`❌ Failed to reset job ${job.id} status:`, error)
        }
        setRealTimeStatus('READY')
        setFinishedTransitionTimer(null)
        setResetCountdown(null)
      }
      performReset()
    }
  }, [resetCountdown, job.id, user?.tenant_id])

  // Sync realTimeStatus with job.status prop when it changes (handles API updates)
  useEffect(() => {
    // Only update if the job status has actually changed
    if (job.status !== realTimeStatus) {
      console.log(`🔄 Job status updated from API: ${realTimeStatus} → ${job.status}`)
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
          // Always update job progress and step statuses (even after FINISHED)
          setJobProgress(data)
          setIsJobRunning(data.isActive)

          // Update overall status based on job progress
          // IMPORTANT: Once job is FINISHED or FAILED, don't let WebSocket change it back to RUNNING
          // But still allow step status updates
          if (data.isActive && (realTimeStatus === 'FINISHED' || realTimeStatus === 'FAILED')) {
            console.log(`🔒 Ignoring WebSocket attempt to change status back to RUNNING - job already ${realTimeStatus}`)
            return
          }

          if (data.isActive) {
            setRealTimeStatus('RUNNING')
            // Clear any existing finished transition timer
            if (finishedTransitionTimer) {
              clearTimeout(finishedTransitionTimer)
              setFinishedTransitionTimer(null)
            }
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
              // Clear any existing finished transition timer
              if (finishedTransitionTimer) {
                clearTimeout(finishedTransitionTimer)
                setFinishedTransitionTimer(null)
              }
            } else if (allFinished) {
              setRealTimeStatus('FINISHED')

              // Clear any existing timer first
              if (finishedTransitionTimer) {
                clearTimeout(finishedTransitionTimer)
              }

              // Hybrid approach: Check if all steps are truly finished
              // If yes, reset immediately. If no, wait 30 seconds and try again.
              const checkAndReset = async () => {
                try {
                  if (!user?.tenant_id) {
                    console.warn(`⚠️ Cannot check job completion: user or tenant_id not available`)
                    // Fallback: wait 30s and reset anyway
                    setResetCountdown(30)
                    setTimeout(performReset, 30000)
                    return
                  }

                  // Check if all steps are truly finished
                  const completionCheck = await jobsApi.checkJobCompletion(job.id, user.tenant_id)
                  console.log(`🔍 Job ${job.id} completion check:`, completionCheck.data)

                  if (completionCheck.data.all_finished) {
                    // All steps are finished, reset immediately
                    console.log(`✅ All steps finished, resetting job immediately`)
                    await performReset()
                  } else {
                    // Not all steps finished yet, wait 30 seconds and try again
                    console.log(`⏳ Not all steps finished yet, waiting 30 seconds...`)
                    setResetCountdown(30)
                    const timer = setTimeout(checkAndReset, 30000)
                    setFinishedTransitionTimer(timer)
                  }
                } catch (error) {
                  console.error(`❌ Error checking job completion:`, error)
                  // Fallback: wait 30s and reset anyway
                  setResetCountdown(30)
                  const timer = setTimeout(performReset, 30000)
                  setFinishedTransitionTimer(timer)
                }
              }

              const performReset = async () => {
                try {
                  // Call backend to reset job status in database
                  if (user?.tenant_id) {
                    await jobsApi.resetJobStatus(job.id, user.tenant_id)
                    console.log(`✅ Job ${job.id} status reset to READY in database`)
                  } else {
                    console.warn(`⚠️ Cannot reset job ${job.id} status: user or tenant_id not available`)
                  }
                } catch (error) {
                  console.error(`❌ Failed to reset job ${job.id} status in database:`, error)
                }
                // Update frontend state regardless of backend call result
                setRealTimeStatus('READY')
                setFinishedTransitionTimer(null)
                setResetCountdown(null)
              }

              // Start the check and reset process
              checkAndReset()
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

                {/* Reset Countdown Timer - Show when resetting */}
                {resetCountdown !== null && (
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

