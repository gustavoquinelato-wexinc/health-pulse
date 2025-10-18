import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import axios from 'axios'
import { etlApi } from '../services/etlApiService'
import CollapsedSidebar from '../components/CollapsedSidebar'
import Header from '../components/Header'
import JobCard from '../components/JobCard'
import JobSettingsModal, { JobSettings } from '../components/JobSettingsModal'
import JiraJobDetailsModal from '../components/JiraJobDetailsModal'
import GitHubJobDetailsModal from '../components/GitHubJobDetailsModal'
import FabricJobDetailsModal from '../components/FabricJobDetailsModal'
import ADJobDetailsModal from '../components/ADJobDetailsModal'
import JobDetailsModal from '../components/JobDetailsModal'
import ToastContainer from '../components/ToastContainer'
import { useToast } from '../hooks/useToast'
import { useAuth } from '../contexts/AuthContext'
import { etlWebSocketService } from '../services/sessionWebSocketService'

interface Job {
  id: number
  job_name: string
  status: string
  active: boolean
  schedule_interval_minutes: number
  retry_interval_minutes: number
  integration_id?: number
  integration_type?: string
  integration_logo_filename?: string
  last_run_started_at?: string
  last_run_finished_at?: string
  next_run?: string
  error_message?: string
  retry_count: number
  checkpoint_data?: any
}

export default function HomePage() {
  const { user } = useAuth()
  const { toasts, removeToast, showSuccess, showError } = useToast()
  const [jobs, setJobs] = useState<Job[]>([])
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null)
  const [selectedJobName, setSelectedJobName] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [settingsModalOpen, setSettingsModalOpen] = useState(false)
  const [selectedJobForSettings, setSelectedJobForSettings] = useState<Job | null>(null)

  // Activation confirmation modal state
  const [activationModal, setActivationModal] = useState({
    isOpen: false,
    jobId: 0,
    jobName: '',
    integrationId: 0,
    integrationName: ''
  })

  useEffect(() => {
    if (user) {
      fetchJobs()
      // WebSocket service is already initialized in AuthContext after login
      // No need to initialize again here
      // Refresh every 30 seconds
      const interval = setInterval(fetchJobs, 30000)
      return () => clearInterval(interval)
    }
  }, [user])

  // Listen for job completion events
  useEffect(() => {
    const handleJobCompletion = (event: CustomEvent) => {
      const { jobId, success } = event.detail


      // Update the job status in the local state
      setJobs(prevJobs =>
        prevJobs.map(job =>
          job.id === jobId
            ? {
                ...job,
                status: success ? 'FINISHED' : 'FAILED',
                progress_percentage: null,
                current_step: null
              }
            : job
        )
      )

      // Refresh jobs from server to get updated data
      setTimeout(() => fetchJobs(), 1000)
    }

    window.addEventListener('etl-job-completed', handleJobCompletion as EventListener)

    return () => {
      window.removeEventListener('etl-job-completed', handleJobCompletion as EventListener)
    }
  }, [])

  const fetchJobs = async () => {
    if (!user) return

    try {
      // Use etlApi service which has authentication headers configured
      const response = await etlApi.get(`/jobs?tenant_id=${user.tenant_id}`)
      // Sort jobs alphabetically by job_name
      const sortedJobs = response.data.sort((a: Job, b: Job) =>
        a.job_name.localeCompare(b.job_name)
      )
      setJobs(sortedJobs)
      setError(null)
    } catch (err: any) {
      console.error('Error fetching jobs:', err)
      setError(err.response?.data?.detail || 'Failed to fetch jobs')
    } finally {
      setLoading(false)
    }
  }

  const handleRunNow = async (jobId: number) => {
    if (!user) return

    try {
      // First, set the job status to RUNNING and clear next_run in the frontend
      setJobs(prevJobs =>
        prevJobs.map(job =>
          job.id === jobId
            ? { ...job, status: 'RUNNING', next_run: undefined, progress_percentage: 0, current_step: 'Starting...' }
            : job
        )
      )

      // Then call the backend to start the extraction
      const response = await etlApi.post(`/jobs/${jobId}/run-now?tenant_id=${user.tenant_id}`)

      showSuccess(
        'Job Triggered',
        response.data.message || 'Job execution started'
      )

    } catch (err: any) {
      // Show error toast (no console.error - toast is enough)
      showError(
        'Failed to run job',
        err.response?.data?.detail || 'An error occurred'
      )
    }
  }



  const handleToggleJobActive = async (jobId: number, active: boolean) => {
    if (!user) return

    // If activating, check if integration is inactive first
    if (active) {
      const job = jobs.find(j => j.id === jobId)
      if (job && job.integration_id) {
        // Get all integrations to check if this job's integration is inactive
        try {
          const integrationsResponse = await etlApi.get('/integrations')
          const integrations = integrationsResponse.data
          const integration = integrations.find((i: any) => i.id === job.integration_id)

          if (integration && !integration.active) {
            // Show confirmation modal
            setActivationModal({
              isOpen: true,
              jobId,
              jobName: job.job_name,
              integrationId: job.integration_id,
              integrationName: integration.name
            })
            return
          }
        } catch (err) {
          // If we can't check integration, proceed with normal activation
          // This will let the backend handle the validation
        }
      }
    }

    // Proceed with toggle
    await performToggleJobActive(jobId, active)
  }

  const performToggleJobActive = async (jobId: number, active: boolean, activateIntegration: boolean = false) => {
    if (!user) return

    try {
      // If we need to activate integration first
      if (activateIntegration && activationModal.integrationId) {
        await etlApi.post(
          `/integrations/${activationModal.integrationId}/toggle-active`,
          { active: true }
        )
      }

      const response = await etlApi.post(
        `/jobs/${jobId}/toggle-active?tenant_id=${user.tenant_id}`,
        { active }
      )

      // Find the job name for WebSocket management
      const job = jobs.find(j => j.id === jobId)
      if (job) {
        // Dynamically manage WebSocket connection based on active status
        etlWebSocketService.handleJobToggle(job.job_name, active)
      }

      // Show success toast
      const message = activateIntegration
        ? `Integration and job activated successfully`
        : response.data.message || `Job ${active ? 'activated' : 'deactivated'} successfully`

      showSuccess(
        'Job Status Updated',
        message
      )

      // Close modal if open
      setActivationModal({ isOpen: false, jobId: 0, jobName: '', integrationId: 0, integrationName: '' })

      await fetchJobs()
    } catch (err: any) {
      // Extract error message from response
      const errorDetail = err.response?.data?.detail || 'An error occurred'

      // Show more helpful error message (no console.error - toast is enough)
      showError(
        'Cannot Toggle Job Status',
        errorDetail
      )

      // Close modal if open
      setActivationModal({ isOpen: false, jobId: 0, jobName: '', integrationId: 0, integrationName: '' })

      // Don't update the UI - keep the toggle in its current state
      // The fetchJobs() call will ensure the UI reflects the actual state
      await fetchJobs()
    }
  }

  const handleSaveJobSettings = async (jobId: number, settings: JobSettings) => {
    if (!user) return

    try {
      const response = await etlApi.post(
        `/jobs/${jobId}/settings?tenant_id=${user.tenant_id}`,
        settings
      )

      // Close modal first to prevent flash
      setSettingsModalOpen(false)
      setSelectedJobForSettings(null)

      // Then refresh jobs and show success
      await fetchJobs()

      showSuccess(
        'Settings Updated',
        response.data.message || 'Job settings updated successfully'
      )
    } catch (err: any) {
      console.error('Error saving job settings:', err)
      showError(
        'Failed to save settings',
        err.response?.data?.detail || 'An error occurred'
      )
      throw err // Re-throw to prevent modal from closing
    }
  }

  return (
    <div className="min-h-screen">
      <Header />

      <div className="flex">
        <CollapsedSidebar />

        <main className="flex-1 ml-16 py-8">
          <div className="ml-12 mr-12">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="space-y-6"
            >
            {/* Page Header */}
            <div className="space-y-2">
              <h1 className="text-3xl font-bold text-primary">
                ETL Jobs Dashboard
              </h1>
              <p className="text-secondary">
                Monitor and control your autonomous data synchronization jobs
              </p>
            </div>

            {/* Error Display */}
            {error && (
              <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
                <p className="font-medium">Error</p>
                <p className="text-sm">{error}</p>
              </div>
            )}

            {/* Loading State */}
            {loading && (
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
              </div>
            )}

            {/* Job Cards */}
            {!loading && (
              <div className="space-y-4">
                {jobs.map((job) => (
                  <JobCard
                    key={job.id}
                    job={job}
                    onRunNow={handleRunNow}
                    onToggleActive={handleToggleJobActive}
                    onShowDetails={(jobId) => {
                      setSelectedJobId(jobId)
                      const selectedJob = jobs.find(j => j.id === jobId)
                      setSelectedJobName(selectedJob?.job_name || null)
                    }}
                    onSettings={(job) => {
                      setSelectedJobForSettings(job)
                      setSettingsModalOpen(true)
                    }}
                  />
                ))}
              </div>
            )}
            </motion.div>
          </div>
        </main>
      </div>

      {/* Job Details Modals - Render based on job name */}
      {selectedJobName === 'Jira' && (
        <JiraJobDetailsModal
          jobId={selectedJobId}
          onClose={() => {
            setSelectedJobId(null)
            setSelectedJobName(null)
          }}
        />
      )}

      {selectedJobName === 'GitHub' && (
        <GitHubJobDetailsModal
          jobId={selectedJobId}
          onClose={() => {
            setSelectedJobId(null)
            setSelectedJobName(null)
          }}
        />
      )}

      {selectedJobName === 'WEX Fabric' && (
        <FabricJobDetailsModal
          jobId={selectedJobId}
          onClose={() => {
            setSelectedJobId(null)
            setSelectedJobName(null)
          }}
        />
      )}

      {selectedJobName === 'WEX AD' && (
        <ADJobDetailsModal
          jobId={selectedJobId}
          onClose={() => {
            setSelectedJobId(null)
            setSelectedJobName(null)
          }}
        />
      )}

      {/* Default modal for Vectorization or any other job */}
      {selectedJobName && !['Jira', 'GitHub', 'WEX Fabric', 'WEX AD'].includes(selectedJobName) && (
        <JobDetailsModal
          jobId={selectedJobId}
          onClose={() => {
            setSelectedJobId(null)
            setSelectedJobName(null)
          }}
        />
      )}

      {/* Job Settings Modal */}
      {selectedJobForSettings && (
        <JobSettingsModal
          isOpen={settingsModalOpen}
          onClose={() => {
            setSettingsModalOpen(false)
            setSelectedJobForSettings(null)
          }}
          onSave={(settings: JobSettings) => handleSaveJobSettings(selectedJobForSettings.id, settings)}
          currentSettings={{
            schedule_interval_minutes: selectedJobForSettings.schedule_interval_minutes,
            retry_interval_minutes: selectedJobForSettings.retry_interval_minutes
          }}
          jobName={selectedJobForSettings.job_name}
        />
      )}

      {/* Activation Confirmation Modal */}
      {activationModal.isOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full mx-4">
            <div className="p-6">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                Activate Integration?
              </h3>

              <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-md p-3 mb-4">
                <div className="flex">
                  <svg className="w-5 h-5 text-yellow-400 mr-2 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                  <div>
                    <p className="text-sm text-yellow-800 dark:text-yellow-200">
                      <strong>Integration is inactive</strong>
                    </p>
                    <p className="text-sm text-yellow-700 dark:text-yellow-300 mt-1">
                      The job <strong>{activationModal.jobName}</strong> requires the integration <strong>{activationModal.integrationName}</strong> to be active.
                    </p>
                  </div>
                </div>
              </div>

              <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                Would you like to activate both the integration and the job?
              </p>

              <div className="flex justify-end space-x-3">
                <button
                  onClick={() => setActivationModal({ isOpen: false, jobId: 0, jobName: '', integrationId: 0, integrationName: '' })}
                  className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-500"
                >
                  Cancel
                </button>
                <button
                  onClick={() => performToggleJobActive(activationModal.jobId, true, true)}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  Activate Both
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Toast Notifications */}
      <ToastContainer toasts={toasts} onRemoveToast={removeToast} />
    </div>
  )
}
