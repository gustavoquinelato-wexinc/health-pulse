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
import { etlWebSocketService } from '../services/websocketService'

interface Job {
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

  useEffect(() => {
    if (user) {
      fetchJobs()
      // Initialize WebSocket service when user accesses ETL page
      etlWebSocketService.initializeService()
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
      // First, set the job status to RUNNING in the frontend
      setJobs(prevJobs =>
        prevJobs.map(job =>
          job.id === jobId
            ? { ...job, status: 'RUNNING', progress_percentage: 0, current_step: 'Starting...' }
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
      console.error('Error running job:', err)
      showError(
        'Failed to run job',
        err.response?.data?.detail || 'An error occurred'
      )
    }
  }



  const handleToggleJobActive = async (jobId: number, active: boolean) => {
    if (!user) return

    try {
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
      showSuccess(
        'Job Status Updated',
        response.data.message || `Job ${active ? 'activated' : 'deactivated'} successfully`
      )

      await fetchJobs()
    } catch (err: any) {
      console.error('Error toggling job active status:', err)
      showError(
        'Failed to update job status',
        err.response?.data?.detail || 'An error occurred'
      )
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

      {/* Toast Notifications */}
      <ToastContainer toasts={toasts} onRemoveToast={removeToast} />
    </div>
  )
}
