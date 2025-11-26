import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Badge } from '../components/ui/badge'
import { Separator } from '../components/ui/separator'
import { Alert, AlertDescription } from '../components/ui/alert'
import Header from '../components/Header'
import CollapsedSidebar from '../components/CollapsedSidebar'
import ToastContainer from '../components/ToastContainer'
import ConfirmationModal from '../components/ConfirmationModal'
import { useToast } from '../hooks/useToast'
import { useConfirmation } from '../hooks/useConfirmation'
import { Play, Square, RotateCcw, Activity, Clock, CheckCircle, XCircle, AlertCircle, Settings, Save, Database, Inbox, Download, RefreshCw, Sparkles, Loader, Circle } from 'lucide-react'

interface WorkerInstance {
  worker_key: string
  worker_number: number
  worker_running: boolean
  thread_alive: boolean
  thread_name: string | null
  queue_name: string | null
}

interface WorkerTypeStatus {
  count: number
  instances: WorkerInstance[]
}

interface WorkerStatus {
  running: boolean
  worker_count: number
  tenant_count: number
  workers: Record<string, WorkerTypeStatus>
  queue_stats: Record<string, any>
  raw_data_stats: Record<string, {
    count: number
    oldest?: string
    newest?: string
  }>
}



interface WorkerPoolConfig {
  tier_configs: {
    [tier: string]: {
      extraction: number
      transform: number
      embedding: number
    }
  }
  current_tenant_tier: string
  current_tenant_allocation: {
    extraction: number
    transform: number
    embedding: number
  }
}

interface DatabaseCapacity {
  total_connections: number
  pool_size: number
  max_overflow: number
  reserved_for_ui: number
  available_for_workers: number
  current_worker_count: number
  max_recommended_workers: number
  current_usage_percent: number
  can_add_workers: boolean
  warning_message: string | null
}

interface QueueStats {
  message_count: number
  consumer_count: number
}

export default function QueueManagementPage() {
  const { toasts, removeToast, showSuccess, showError } = useToast()
  const { confirmation, hideConfirmation, confirmAction } = useConfirmation()

  const [workerStatus, setWorkerStatus] = useState<WorkerStatus | null>(null)
  const [workerConfig, setWorkerConfig] = useState<WorkerPoolConfig | null>(null)
  const [dbCapacity, setDbCapacity] = useState<DatabaseCapacity | null>(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [saveLoading, setSaveLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date())

  // Local state for worker counts (editable)
  const [extractionWorkers, setExtractionWorkers] = useState<number>(5)
  const [transformWorkers, setTransformWorkers] = useState<number>(5)
  const [embeddingWorkers, setEmbeddingWorkers] = useState<number>(15)

  // Original values to detect changes
  const [originalExtractionWorkers, setOriginalExtractionWorkers] = useState<number>(5)
  const [originalTransformWorkers, setOriginalTransformWorkers] = useState<number>(5)
  const [originalEmbeddingWorkers, setOriginalEmbeddingWorkers] = useState<number>(15)

  // Check if there are unsaved changes
  const hasUnsavedChanges =
    extractionWorkers !== originalExtractionWorkers ||
    transformWorkers !== originalTransformWorkers ||
    embeddingWorkers !== originalEmbeddingWorkers

  // Update document title
  useEffect(() => {
    document.title = 'Queue Management - PEM'
  }, [])

  const fetchWorkerStatus = async () => {
    try {
      // Use backend service URL directly for admin endpoints
      const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001'
      const response = await fetch(`${API_BASE_URL}/api/v1/admin/workers/status`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('pulse_token')}`,
          'Content-Type': 'application/json'
        }
      })

      if (!response.ok) {
        throw new Error(`Failed to fetch worker status: ${response.statusText}`)
      }

      const data = await response.json()
      setWorkerStatus(data)
      setLastUpdated(new Date())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch worker status')
    }
  }



  const fetchWorkerConfig = async (updateLocalState = false) => {
    try {
      const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001'
      const response = await fetch(`${API_BASE_URL}/api/v1/admin/workers/config`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('pulse_token')}`,
          'Content-Type': 'application/json'
        }
      })

      if (!response.ok) {
        throw new Error(`Failed to fetch worker config: ${response.statusText}`)
      }

      const data = await response.json()
      setWorkerConfig(data)

      // Only update local state on initial load or after successful save
      if (updateLocalState) {
        const allocation = data.current_tenant_allocation
        setExtractionWorkers(allocation.extraction)
        setTransformWorkers(allocation.transform)
        setEmbeddingWorkers(allocation.embedding)
        setOriginalExtractionWorkers(allocation.extraction)
        setOriginalTransformWorkers(allocation.transform)
        setOriginalEmbeddingWorkers(allocation.embedding)
      }
    } catch (err) {
      console.error('Failed to fetch worker config:', err)
    }
  }

  const fetchDatabaseCapacity = async () => {
    try {
      const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001'
      const response = await fetch(`${API_BASE_URL}/api/v1/admin/workers/db-capacity`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('pulse_token')}`,
          'Content-Type': 'application/json'
        }
      })

      if (!response.ok) {
        throw new Error(`Failed to fetch database capacity: ${response.statusText}`)
      }

      const data = await response.json()
      setDbCapacity(data)
    } catch (err) {
      console.error('Failed to fetch database capacity:', err)
    }
  }

  const updateWorkerCounts = async () => {
    setSaveLoading(true)
    setError(null)

    try {
      const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001'
      const response = await fetch(`${API_BASE_URL}/api/v1/admin/workers/config/update`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('pulse_token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          extraction_workers: extractionWorkers,
          transform_workers: transformWorkers,
          embedding_workers: embeddingWorkers
        })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || `Failed to update worker counts: ${response.statusText}`)
      }

      // Refresh config and update local state to match saved values
      await fetchWorkerConfig(true)
      await fetchDatabaseCapacity()

      // Show success message
      setError(null)
      showSuccess('Worker Counts Updated', 'Worker counts updated successfully. Restart worker pools to apply changes.')

      // Ask if user wants to restart workers using confirmation modal
      confirmAction(
        'Restart Worker Pools?',
        'Worker counts updated successfully! Changes will NOT take effect until worker pools are restarted. Would you like to restart all worker pools now?',
        async () => {
          // Automatically restart workers
          await performWorkerAction('restart')
        },
        'Restart Pools'
      )
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to update worker counts'
      setError(errorMessage)
      showError('Update Failed', errorMessage)
    } finally {
      setSaveLoading(false)
    }
  }

  const performWorkerAction = async (action: string, queueType?: string) => {
    const actionKey = queueType ? `${action}_${queueType}` : action
    setActionLoading(actionKey)
    setError(null)

    try {
      // Use backend service URL directly for admin endpoints
      const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001'
      const response = await fetch(`${API_BASE_URL}/api/v1/admin/workers/action`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('pulse_token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          action,
          queue_type: queueType || null
        })
      })

      if (!response.ok) {
        throw new Error(`Failed to ${action} workers: ${response.statusText}`)
      }

      const result = await response.json()

      if (!result.success) {
        throw new Error(result.message || `Failed to ${action} workers`)
      }

      // Refresh status after action
      await fetchWorkerStatus()

      // Show success message
      const scope = queueType ? `${queueType} workers` : 'all workers'
      showSuccess(`Workers ${action === 'start' ? 'Started' : action === 'stop' ? 'Stopped' : 'Restarted'}`, `${result.message} (${scope})`)
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${action} workers`)
      showError(`Worker ${action.charAt(0).toUpperCase() + action.slice(1)} Failed`, err instanceof Error ? err.message : `Failed to ${action} workers`)
    } finally {
      setActionLoading(null)
    }
  }



  // Manual refresh function
  const handleRefresh = async () => {
    setLoading(true)
    await Promise.all([
      fetchWorkerStatus(),
      fetchWorkerConfig(false), // Don't reset user's selections
      fetchDatabaseCapacity()
    ])
    setLoading(false)
  }

  // Helper function to check if workers are running for a specific queue type
  const areWorkersRunning = (queueType: 'extraction' | 'transform' | 'embedding'): boolean => {
    if (!workerStatus?.workers) return false

    const workerTypeStatus = workerStatus.workers[queueType]
    if (!workerTypeStatus?.instances) return false

    // Check if ANY worker instance is running
    return workerTypeStatus.instances.some(instance => instance.worker_running)
  }

  // Helper function to get message count for a queue type
  const getMessageCount = (queueType: 'extraction' | 'transform' | 'embedding'): number => {
    return workerStatus?.queue_stats?.tier_queues?.premium?.[queueType]?.message_count ?? 0
  }

  // Helper function to check if ALL workers are running (for global controls)
  const areAllWorkersRunning = (): boolean => {
    return areWorkersRunning('extraction') &&
           areWorkersRunning('transform') &&
           areWorkersRunning('embedding')
  }

  // Helper function to check if ALL workers are idle (for global controls)
  const areAllWorkersIdle = (): boolean => {
    return !areWorkersRunning('extraction') &&
           !areWorkersRunning('transform') &&
           !areWorkersRunning('embedding')
  }

  // Get status info for a queue (matching job card status)
  const getQueueStatusInfo = (queueType: 'extraction' | 'transform' | 'embedding') => {
    const isRunning = areWorkersRunning(queueType)
    const messageCount = getMessageCount(queueType)

    if (!isRunning) {
      // Workers are stopped/idle - show "Idle" status (gray circle)
      return {
        icon: <Circle className="w-4 h-4" />,
        color: 'text-gray-500',
        bgColor: 'bg-gray-100',
        label: 'Idle'
      }
    } else if (messageCount > 0) {
      // Workers are running and processing messages - show "Running" status (blue with spinning loader)
      return {
        icon: <Loader className="w-4 h-4 animate-spin" />,
        color: 'text-blue-500',
        bgColor: 'bg-blue-100',
        label: 'Running'
      }
    } else {
      // Workers are running but waiting for messages - show "Ready" status (cyan with clock)
      return {
        icon: <Clock className="w-4 h-4" />,
        color: 'text-cyan-500',
        bgColor: 'bg-cyan-100',
        label: 'Ready'
      }
    }
  }

  useEffect(() => {
    const loadData = async () => {
      setLoading(true)
      await Promise.all([
        fetchWorkerStatus(),
        fetchWorkerConfig(true), // Update local state on initial load
        fetchDatabaseCapacity()
      ])
      setLoading(false)
    }

    loadData()
    // No auto-refresh interval - user will manually refresh
  }, [])

  const getStatusIcon = (running: boolean, threadAlive: boolean) => {
    if (running && threadAlive) {
      return <CheckCircle className="h-4 w-4 text-green-500" />
    } else if (running && !threadAlive) {
      return <AlertCircle className="h-4 w-4 text-yellow-500" />
    } else {
      return <XCircle className="h-4 w-4 text-red-500" />
    }
  }



  const getDataStatusIcon = (status: string) => {
    switch (status) {
      case 'pending':
        return <Clock className="h-4 w-4 text-yellow-500" />
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />
      default:
        return <Activity className="h-4 w-4 text-blue-500" />
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen">
        <Header />
        <div className="flex">
          <CollapsedSidebar />
          <main className="flex-1 ml-16 py-8">
            <div className="ml-12 mr-12">
              <div className="flex items-center justify-center min-h-[400px]">
                <div className="text-center">
                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
                  <p className="text-secondary">Loading queue management...</p>
                </div>
              </div>
            </div>
          </main>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen">
      <Header />
      <div className="flex">
        <CollapsedSidebar />
        <main className="flex-1 ml-16 py-8">
          <div className="ml-12 mr-12">
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold text-primary">Queue Management</h1>
            <p className="text-secondary mt-2">Monitor and control ETL background workers</p>
          </div>
          <div className="text-sm text-secondary">
            Last updated: {lastUpdated.toLocaleTimeString()}
          </div>
        </div>

        {error && (
          <Alert className="mb-6 border-red-200 bg-red-50">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription className="text-red-800">{error}</AlertDescription>
          </Alert>
        )}

        {/* Unified Queue Management Card */}
        <Card className="border border-gray-400"
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = 'var(--color-1)'
            e.currentTarget.style.boxShadow = '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = '#9ca3af'
            e.currentTarget.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
          }}
        >
          {/* Card Header with Global Controls */}
          <CardHeader className="border-b border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Activity className="h-5 w-5" />
                  Worker Pools & Queue Management
                </CardTitle>
                <CardDescription className="mt-1">
                  Monitor and control all ETL background workers
                </CardDescription>
              </div>

              {/* Global Action Buttons */}
              <div className="flex items-center gap-3">
                <button
                  onClick={() => performWorkerAction('start')}
                  disabled={actionLoading === 'start' || areAllWorkersRunning()}
                  className={`btn-crud-create flex items-center gap-2 ${areAllWorkersRunning() ? 'opacity-50 cursor-not-allowed' : ''}`}
                  title={areAllWorkersRunning() ? 'All workers are already running or ready' : 'Start all workers (currently Idle)'}
                >
                  <Play className="h-4 w-4" />
                  <span>{actionLoading === 'start' ? 'Starting...' : 'Start All'}</span>
                </button>

                <button
                  onClick={() => performWorkerAction('stop')}
                  disabled={actionLoading === 'stop' || areAllWorkersIdle()}
                  className={`px-4 py-2 bg-gray-800 text-white rounded-lg hover:bg-gray-900 transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed ${areAllWorkersIdle() ? 'opacity-50 cursor-not-allowed' : ''}`}
                  title={areAllWorkersIdle() ? 'All workers are idle (not running)' : 'Stop all running workers'}
                >
                  <Square className="h-4 w-4" />
                  <span>{actionLoading === 'stop' ? 'Stopping...' : 'Stop All'}</span>
                </button>

                <button
                  onClick={() => performWorkerAction('restart')}
                  disabled={actionLoading === 'restart'}
                  className="btn-neutral-secondary flex items-center gap-2"
                >
                  <RotateCcw className="h-4 w-4" />
                  <span>{actionLoading === 'restart' ? 'Restarting...' : 'Restart All'}</span>
                </button>

                <button
                  onClick={handleRefresh}
                  disabled={loading}
                  className="btn-neutral-secondary flex items-center gap-2"
                  title="Refresh queue statistics"
                >
                  <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                  <span>{loading ? 'Refreshing...' : 'Refresh'}</span>
                </button>
              </div>
            </div>
          </CardHeader>

          <CardContent className="p-6">
            <div className="space-y-4">

              {/* Extraction Queue */}
              <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                <div className="flex items-center justify-between">
                  {/* Left: Queue Info */}
                  <div className="flex items-center space-x-4 flex-1">
                    {/* Queue Icon */}
                    <div className="w-10 h-10 rounded-lg flex items-center justify-center bg-white border border-gray-200">
                      <Download className="h-5 w-5 text-gray-600" />
                    </div>

                    {/* Queue Details */}
                    <div className="flex-1">
                      <h3 className="text-base font-semibold text-primary">Extraction Queue</h3>
                      <div className="flex items-center space-x-4 mt-1">
                        {/* Status Badge */}
                        {(() => {
                          const statusInfo = getQueueStatusInfo('extraction')
                          return (
                            <div className={`flex items-center space-x-1 ${statusInfo.color}`}>
                              {statusInfo.icon}
                              <span className="text-xs font-medium">{statusInfo.label}</span>
                            </div>
                          )
                        })()}

                        {/* Messages Count */}
                        <span className="text-xs text-secondary">
                          Messages: {workerStatus?.queue_stats?.tier_queues?.premium?.extraction?.message_count ?? 0}
                        </span>

                        {/* Active Workers */}
                        <span className="text-xs text-secondary">
                          Workers: {workerConfig?.current_tenant_allocation?.extraction ?? 0}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Right: Action Buttons */}
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => performWorkerAction('start', 'extraction')}
                      disabled={actionLoading === 'start_extraction' || areWorkersRunning('extraction')}
                      className={`btn-crud-create flex items-center space-x-2 text-sm px-3 py-1.5 ${areWorkersRunning('extraction') ? 'opacity-50 cursor-not-allowed' : ''}`}
                      title={areWorkersRunning('extraction') ? 'Workers are already running or ready' : 'Start workers (currently Idle)'}
                    >
                      <Play className="w-3.5 h-3.5" />
                      <span>{actionLoading === 'start_extraction' ? 'Starting...' : 'Start'}</span>
                    </button>
                    <button
                      onClick={() => performWorkerAction('stop', 'extraction')}
                      disabled={actionLoading === 'stop_extraction' || !areWorkersRunning('extraction')}
                      className={`px-3 py-1.5 bg-gray-800 text-white rounded-lg hover:bg-gray-900 transition-colors flex items-center space-x-2 text-sm disabled:opacity-50 disabled:cursor-not-allowed ${!areWorkersRunning('extraction') ? 'opacity-50 cursor-not-allowed' : ''}`}
                      title={!areWorkersRunning('extraction') ? 'Workers are idle (not running)' : 'Stop running workers'}
                    >
                      <Square className="w-3.5 h-3.5" />
                      <span>{actionLoading === 'stop_extraction' ? 'Stopping...' : 'Stop'}</span>
                    </button>
                  </div>
                </div>
              </div>

              {/* Transform Queue */}
              <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                <div className="flex items-center justify-between">
                  {/* Left: Queue Info */}
                  <div className="flex items-center space-x-4 flex-1">
                    {/* Queue Icon */}
                    <div className="w-10 h-10 rounded-lg flex items-center justify-center bg-white border border-gray-200">
                      <RefreshCw className="h-5 w-5 text-gray-600" />
                    </div>

                    {/* Queue Details */}
                    <div className="flex-1">
                      <h3 className="text-base font-semibold text-primary">Transform Queue</h3>
                      <div className="flex items-center space-x-4 mt-1">
                        {/* Status Badge */}
                        {(() => {
                          const statusInfo = getQueueStatusInfo('transform')
                          return (
                            <div className={`flex items-center space-x-1 ${statusInfo.color}`}>
                              {statusInfo.icon}
                              <span className="text-xs font-medium">{statusInfo.label}</span>
                            </div>
                          )
                        })()}

                        {/* Messages Count */}
                        <span className="text-xs text-secondary">
                          Messages: {workerStatus?.queue_stats?.tier_queues?.premium?.transform?.message_count ?? 0}
                        </span>

                        {/* Active Workers */}
                        <span className="text-xs text-secondary">
                          Workers: {workerConfig?.current_tenant_allocation?.transform ?? 0}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Right: Action Buttons */}
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => performWorkerAction('start', 'transform')}
                      disabled={actionLoading === 'start_transform' || areWorkersRunning('transform')}
                      className={`btn-crud-create flex items-center space-x-2 text-sm px-3 py-1.5 ${areWorkersRunning('transform') ? 'opacity-50 cursor-not-allowed' : ''}`}
                      title={areWorkersRunning('transform') ? 'Workers are already running or ready' : 'Start workers (currently Idle)'}
                    >
                      <Play className="w-3.5 h-3.5" />
                      <span>{actionLoading === 'start_transform' ? 'Starting...' : 'Start'}</span>
                    </button>
                    <button
                      onClick={() => performWorkerAction('stop', 'transform')}
                      disabled={actionLoading === 'stop_transform' || !areWorkersRunning('transform')}
                      className={`px-3 py-1.5 bg-gray-800 text-white rounded-lg hover:bg-gray-900 transition-colors flex items-center space-x-2 text-sm disabled:opacity-50 disabled:cursor-not-allowed ${!areWorkersRunning('transform') ? 'opacity-50 cursor-not-allowed' : ''}`}
                      title={!areWorkersRunning('transform') ? 'Workers are idle (not running)' : 'Stop running workers'}
                    >
                      <Square className="w-3.5 h-3.5" />
                      <span>{actionLoading === 'stop_transform' ? 'Stopping...' : 'Stop'}</span>
                    </button>
                  </div>
                </div>
              </div>

              {/* Embedding Queue */}
              <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                <div className="flex items-center justify-between">
                  {/* Left: Queue Info */}
                  <div className="flex items-center space-x-4 flex-1">
                    {/* Queue Icon */}
                    <div className="w-10 h-10 rounded-lg flex items-center justify-center bg-white border border-gray-200">
                      <Sparkles className="h-5 w-5 text-gray-600" />
                    </div>

                    {/* Queue Details */}
                    <div className="flex-1">
                      <h3 className="text-base font-semibold text-primary">Embedding Queue</h3>
                      <div className="flex items-center space-x-4 mt-1">
                        {/* Status Badge */}
                        {(() => {
                          const statusInfo = getQueueStatusInfo('embedding')
                          return (
                            <div className={`flex items-center space-x-1 ${statusInfo.color}`}>
                              {statusInfo.icon}
                              <span className="text-xs font-medium">{statusInfo.label}</span>
                            </div>
                          )
                        })()}

                        {/* Messages Count */}
                        <span className="text-xs text-secondary">
                          Messages: {workerStatus?.queue_stats?.tier_queues?.premium?.embedding?.message_count ?? 0}
                        </span>

                        {/* Active Workers */}
                        <span className="text-xs text-secondary">
                          Workers: {workerConfig?.current_tenant_allocation?.embedding ?? 0}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Right: Action Buttons */}
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => performWorkerAction('start', 'embedding')}
                      disabled={actionLoading === 'start_embedding' || areWorkersRunning('embedding')}
                      className={`btn-crud-create flex items-center space-x-2 text-sm px-3 py-1.5 ${areWorkersRunning('embedding') ? 'opacity-50 cursor-not-allowed' : ''}`}
                      title={areWorkersRunning('embedding') ? 'Workers are already running or ready' : 'Start workers (currently Idle)'}
                    >
                      <Play className="w-3.5 h-3.5" />
                      <span>{actionLoading === 'start_embedding' ? 'Starting...' : 'Start'}</span>
                    </button>
                    <button
                      onClick={() => performWorkerAction('stop', 'embedding')}
                      disabled={actionLoading === 'stop_embedding' || !areWorkersRunning('embedding')}
                      className={`px-3 py-1.5 bg-gray-800 text-white rounded-lg hover:bg-gray-900 transition-colors flex items-center space-x-2 text-sm disabled:opacity-50 disabled:cursor-not-allowed ${!areWorkersRunning('embedding') ? 'opacity-50 cursor-not-allowed' : ''}`}
                      title={!areWorkersRunning('embedding') ? 'Workers are idle (not running)' : 'Stop running workers'}
                    >
                      <Square className="w-3.5 h-3.5" />
                      <span>{actionLoading === 'stop_embedding' ? 'Stopping...' : 'Stop'}</span>
                    </button>
                  </div>
                </div>
              </div>

              {/* Divider */}
              <Separator className="my-6" />

              {/* Worker Configuration Section */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-base font-semibold text-primary flex items-center gap-2">
                      <Settings className="h-4 w-4" />
                      Worker Configuration
                    </h3>
                    <p className="text-xs text-secondary mt-1">Configure worker counts for each queue type</p>
                  </div>
                  <button
                    onClick={updateWorkerCounts}
                    disabled={saveLoading || !hasUnsavedChanges}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Save className="h-3.5 w-3.5" />
                    <span>{saveLoading ? 'Saving...' : 'Save Configuration'}</span>
                  </button>
                </div>

                {/* Database Capacity Warning */}
                {dbCapacity && dbCapacity.warning_message && (
                  <Alert className="border-yellow-200 bg-yellow-50">
                    <AlertCircle className="h-4 w-4 text-yellow-600" />
                    <AlertDescription className="text-yellow-800 text-xs">
                      {dbCapacity.warning_message}
                    </AlertDescription>
                  </Alert>
                )}

                {/* Database Capacity Stats */}
                {dbCapacity && (
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                    <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                      <div className="text-xs text-secondary">Total Connections</div>
                      <div className="text-xl font-bold">{dbCapacity.total_connections}</div>
                      <div className="text-xs text-secondary mt-1">Pool: {dbCapacity.pool_size} + Overflow: {dbCapacity.max_overflow}</div>
                    </div>
                    <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
                      <div className="text-xs text-secondary">Reserved for UI</div>
                      <div className="text-xl font-bold text-blue-600">{dbCapacity.reserved_for_ui}</div>
                      <div className="text-xs text-secondary mt-1">Frontend operations</div>
                    </div>
                    <div className="p-3 bg-green-50 rounded-lg border border-green-200">
                      <div className="text-xs text-secondary">Available for Workers</div>
                      <div className="text-xl font-bold text-green-600">{dbCapacity.available_for_workers}</div>
                      <div className="text-xs text-secondary mt-1">Max: {dbCapacity.max_recommended_workers}</div>
                    </div>
                    <div className={`p-3 rounded-lg border ${dbCapacity.current_usage_percent > 80 ? 'bg-red-50 border-red-200' : dbCapacity.current_usage_percent > 60 ? 'bg-yellow-50 border-yellow-200' : 'bg-green-50 border-green-200'}`}>
                      <div className="text-xs text-secondary">Current Usage</div>
                      <div className={`text-xl font-bold ${dbCapacity.current_usage_percent > 80 ? 'text-red-600' : dbCapacity.current_usage_percent > 60 ? 'text-yellow-600' : 'text-green-600'}`}>
                        {dbCapacity.current_usage_percent.toFixed(1)}%
                      </div>
                      <div className="text-xs text-secondary mt-1">{dbCapacity.current_worker_count} / {dbCapacity.max_recommended_workers} workers</div>
                    </div>
                  </div>
                )}

                {/* Worker Count Configuration */}
                <div className="p-4 bg-white rounded-lg border border-gray-200">
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                    {/* Extraction Workers */}
                    <div>
                      <label className="block text-xs font-semibold text-gray-700 mb-2">
                        Extraction Workers
                      </label>
                      <input
                        type="number"
                        min="1"
                        max={dbCapacity?.max_recommended_workers ?? 100}
                        value={extractionWorkers}
                        onChange={(e) => setExtractionWorkers(parseInt(e.target.value) || 1)}
                        disabled={saveLoading}
                        className="w-full p-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm font-semibold text-center"
                      />
                      <div className="text-xs text-secondary mt-1">
                        Current: {originalExtractionWorkers}
                      </div>
                    </div>

                    {/* Transform Workers */}
                    <div>
                      <label className="block text-xs font-semibold text-gray-700 mb-2">
                        Transform Workers
                      </label>
                      <input
                        type="number"
                        min="1"
                        max={dbCapacity?.max_recommended_workers ?? 100}
                        value={transformWorkers}
                        onChange={(e) => setTransformWorkers(parseInt(e.target.value) || 1)}
                        disabled={saveLoading}
                        className="w-full p-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm font-semibold text-center"
                      />
                      <div className="text-xs text-secondary mt-1">
                        Current: {originalTransformWorkers}
                      </div>
                    </div>

                    {/* Embedding Workers */}
                    <div>
                      <label className="block text-xs font-semibold text-gray-700 mb-2">
                        Embedding Workers
                      </label>
                      <input
                        type="number"
                        min="1"
                        max={dbCapacity?.max_recommended_workers ?? 100}
                        value={embeddingWorkers}
                        onChange={(e) => setEmbeddingWorkers(parseInt(e.target.value) || 1)}
                        disabled={saveLoading}
                        className="w-full p-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm font-semibold text-center"
                      />
                      <div className="text-xs text-secondary mt-1">
                        Current: {originalEmbeddingWorkers}
                      </div>
                    </div>
                  </div>

                  {/* Total Workers Summary */}
                  <div className="mt-4 p-3 bg-gray-50 rounded-lg border border-gray-200">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-semibold">Total Workers:</span>
                      <div className="flex items-center gap-3">
                        <span className="text-lg font-bold">
                          {extractionWorkers + transformWorkers + embeddingWorkers}
                        </span>
                        {dbCapacity && (
                          <Badge variant={
                            (extractionWorkers + transformWorkers + embeddingWorkers) > dbCapacity.max_recommended_workers
                              ? "destructive"
                              : "default"
                          }>
                            {(extractionWorkers + transformWorkers + embeddingWorkers) > dbCapacity.max_recommended_workers
                              ? "Exceeds Limit!"
                              : "Within Limits"}
                          </Badge>
                        )}
                      </div>
                    </div>
                    {dbCapacity && (extractionWorkers + transformWorkers + embeddingWorkers) > dbCapacity.max_recommended_workers && (
                      <div className="mt-2 text-xs text-red-600">
                        ⚠️ Total workers ({extractionWorkers + transformWorkers + embeddingWorkers}) exceeds recommended maximum ({dbCapacity.max_recommended_workers}).
                      </div>
                    )}
                  </div>

                  {/* Important Notes */}
                  <Alert className="border-blue-200 bg-blue-50 mt-4">
                    <AlertCircle className="h-3.5 w-3.5 text-blue-600" />
                    <AlertDescription className="text-blue-800">
                      <div className="text-xs"><strong>Important:</strong> Changes require worker pool restart to take effect. Each worker uses 1 database connection.</div>
                    </AlertDescription>
                  </Alert>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
          </div>
        </main>
      </div>

      {/* Toast Container */}
      <ToastContainer toasts={toasts} onRemoveToast={removeToast} />

      {/* Confirmation Modal */}
      <ConfirmationModal
        isOpen={confirmation.isOpen}
        onClose={hideConfirmation}
        onConfirm={confirmation.onConfirm}
        title={confirmation.title}
        message={confirmation.message}
        confirmText={confirmation.confirmText}
        cancelText={confirmation.cancelText}
        type={confirmation.type}
        icon={confirmation.icon}
      />
    </div>
  )
}
