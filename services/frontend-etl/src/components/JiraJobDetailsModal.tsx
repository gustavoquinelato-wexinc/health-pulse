import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Clock, AlertCircle, Calendar, Activity, Database } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { etlApi } from '../services/etlApiService'

interface JobDetails {
  id: number
  job_name: string
  execution_order: number
  status: string
  active: boolean
  integration_id?: number
  last_run_started_at?: string
  last_success_at?: string
  created_at: string
  last_updated_at: string
  error_message?: string
  retry_count: number
  current_step?: string
}

interface JiraJobDetailsModalProps {
  jobId: number | null
  onClose: () => void
}

export default function JiraJobDetailsModal({ jobId, onClose }: JiraJobDetailsModalProps) {
  const { user } = useAuth()
  const [jobDetails, setJobDetails] = useState<JobDetails | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (jobId) {
      fetchJobDetails()
    }
  }, [jobId])

  const fetchJobDetails = async () => {
    if (!jobId || !user) return

    setLoading(true)
    setError(null)

    try {
      const response = await etlApi.get(`/jobs/${jobId}?tenant_id=${user.tenant_id}`)
      setJobDetails(response.data)
    } catch (err: any) {
      console.error('Error fetching job details:', err)
      setError(err.response?.data?.detail || 'Failed to fetch job details')
    } finally {
      setLoading(false)
    }
  }

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return 'Never'
    return new Date(dateStr).toLocaleString()
  }

  const formatDuration = (startStr?: string, endStr?: string) => {
    if (!startStr || !endStr) return 'N/A'
    
    const start = new Date(startStr).getTime()
    const end = new Date(endStr).getTime()
    const diffMs = end - start
    const diffMins = Math.floor(diffMs / 60000)
    const diffSecs = Math.floor((diffMs % 60000) / 1000)
    
    if (diffMins > 0) {
      return `${diffMins}m ${diffSecs}s`
    }
    return `${diffSecs}s`
  }

  if (!jobId) return null

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          className="card max-w-4xl w-full max-h-[90vh] overflow-y-auto"
        >
          {/* Header */}
          <div className="sticky top-0 bg-secondary z-10 px-6 py-4 border-b border-border flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <img
                src="/assets/integrations/jira.svg"
                alt="Jira"
                className="w-8 h-8 object-contain"
              />
              <h2 className="text-2xl font-bold text-primary">
                Jira Sync Job Details
              </h2>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-tertiary transition-colors"
            >
              <X className="w-5 h-5 text-secondary" />
            </button>
          </div>

          {/* Content */}
          <div className="p-6">
            {loading && (
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
              </div>
            )}

            {error && (
              <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
                <p className="font-medium">Error</p>
                <p className="text-sm">{error}</p>
              </div>
            )}

            {jobDetails && !loading && (
              <div className="space-y-6">
                {/* Status Overview */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="card p-4">
                    <div className="flex items-center space-x-2 mb-2">
                      <Activity className="w-4 h-4 text-secondary" />
                      <span className="text-sm text-secondary">Status</span>
                    </div>
                    <p className="text-lg font-semibold text-primary">{jobDetails.status}</p>
                  </div>

                  <div className="card p-4">
                    <div className="flex items-center space-x-2 mb-2">
                      <Calendar className="w-4 h-4 text-secondary" />
                      <span className="text-sm text-secondary">Execution Order</span>
                    </div>
                    <p className="text-lg font-semibold text-primary">#{jobDetails.execution_order}</p>
                  </div>

                  <div className="card p-4">
                    <div className="flex items-center space-x-2 mb-2">
                      <AlertCircle className="w-4 h-4 text-secondary" />
                      <span className="text-sm text-secondary">Retry Count</span>
                    </div>
                    <p className="text-lg font-semibold text-primary">{jobDetails.retry_count}</p>
                  </div>
                </div>

                {/* Jira-Specific Information */}
                <div className="card p-4">
                  <h3 className="text-lg font-semibold text-primary mb-4 flex items-center space-x-2">
                    <Database className="w-5 h-5" />
                    <span>Jira Sync Configuration</span>
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-secondary">Sync Type:</span>
                      <p className="text-primary font-medium mt-1">Incremental (JQL-based)</p>
                    </div>
                    <div>
                      <span className="text-secondary">Data Extracted:</span>
                      <p className="text-primary font-medium mt-1">Issues, Changelogs, Dev Status</p>
                    </div>
                    <div>
                      <span className="text-secondary">Progress Steps:</span>
                      <p className="text-primary font-medium mt-1">5 steps (20% each)</p>
                    </div>
                    <div>
                      <span className="text-secondary">Batch Size:</span>
                      <p className="text-primary font-medium mt-1">100 issues per batch</p>
                    </div>
                  </div>
                </div>

                {/* Timing Information */}
                <div className="card p-4">
                  <h3 className="text-lg font-semibold text-primary mb-4 flex items-center space-x-2">
                    <Clock className="w-5 h-5" />
                    <span>Timing Information</span>
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-secondary">Last Run Started:</span>
                      <p className="text-primary font-medium mt-1">
                        {formatDate(jobDetails.last_run_started_at)}
                      </p>
                    </div>
                    <div>
                      <span className="text-secondary">Last Success:</span>
                      <p className="text-primary font-medium mt-1">
                        {formatDate(jobDetails.last_success_at)}
                      </p>
                    </div>
                    <div>
                      <span className="text-secondary">Created At:</span>
                      <p className="text-primary font-medium mt-1">
                        {formatDate(jobDetails.created_at)}
                      </p>
                    </div>
                    <div>
                      <span className="text-secondary">Last Updated:</span>
                      <p className="text-primary font-medium mt-1">
                        {formatDate(jobDetails.last_updated_at)}
                      </p>
                    </div>
                    {jobDetails.last_run_started_at && jobDetails.last_success_at && (
                      <div>
                        <span className="text-secondary">Last Run Duration:</span>
                        <p className="text-primary font-medium mt-1">
                          {formatDuration(jobDetails.last_run_started_at, jobDetails.last_success_at)}
                        </p>
                      </div>
                    )}
                  </div>
                </div>

                {/* Error Information */}
                {jobDetails.error_message && (
                  <div className="card p-4 bg-red-50 border border-red-200">
                    <h3 className="text-lg font-semibold text-red-700 mb-2 flex items-center space-x-2">
                      <AlertCircle className="w-5 h-5" />
                      <span>Error Details</span>
                    </h3>
                    <p className="text-sm text-red-600 font-mono bg-white p-3 rounded">
                      {jobDetails.error_message}
                    </p>
                  </div>
                )}

                {/* Current Step Information */}
                {jobDetails.current_step && (
                  <div className="card p-4">
                    <h3 className="text-lg font-semibold text-primary mb-4">Current Status</h3>
                    <p className="text-sm text-secondary mb-2">
                      Current Step: <span className="text-primary font-medium">{jobDetails.current_step}</span>
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="sticky bottom-0 bg-secondary px-6 py-4 border-t border-border flex justify-end">
            <button
              onClick={onClose}
              className="btn-neutral-primary px-6 py-2 rounded-lg"
            >
              Close
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  )
}

