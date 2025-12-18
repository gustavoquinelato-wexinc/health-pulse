import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { Badge } from '../components/ui/badge'
import { Alert, AlertDescription } from '../components/ui/alert'
import Header from '../components/Header'
import CollapsedSidebar from '../components/CollapsedSidebar'
import ToastContainer from '../components/ToastContainer'
import ConfirmationModal from '../components/ConfirmationModal'
import { useToast } from '../hooks/useToast'
import { useConfirmation } from '../hooks/useConfirmation'
import { Play, Square, Activity, AlertCircle, Settings, Save, Download, Sparkles, TrendingUp, Database, HelpCircle, X } from 'lucide-react'

interface QueueMessageStats {
  publish: number
  deliver: number
  ack: number
  get_empty: number
  publish_rate: number
  deliver_rate: number
  ack_rate: number
}

interface QueueInfo {
  name: string
  vhost: string
  state: string
  messages: number
  messages_ready: number
  messages_unacknowledged: number
  consumers: number
  consumer_utilisation: number
  memory: number
  message_stats: QueueMessageStats | null
}

interface QueuesStatus {
  extraction: QueueInfo
  transform: QueueInfo
  embedding: QueueInfo
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

interface WorkerStatus {
  running: boolean
  workers: {
    [key: string]: {
      tier: string
      type: string
      count: number
      instances: Array<{
        worker_key: string
        worker_number: number
        worker_running: boolean
        thread_alive: boolean
      }>
    }
  }
  queue_stats: any
  raw_data_stats: any
}

export default function QueueManagementPage() {
  const { toasts, removeToast, showSuccess, showError } = useToast()
  const { confirmation, hideConfirmation, confirmAction } = useConfirmation()

  const [queuesStatus, setQueuesStatus] = useState<QueuesStatus | null>(null)
  const [workerStatus, setWorkerStatus] = useState<WorkerStatus | null>(null)
  const [workerConfig, setWorkerConfig] = useState<WorkerPoolConfig | null>(null)
  const [dbCapacity, setDbCapacity] = useState<DatabaseCapacity | null>(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [saveLoading, setSaveLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date())
  const [showHelpModal, setShowHelpModal] = useState(false)

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

  const fetchQueuesStatus = async () => {
    try {
      // Use backend service URL directly for admin endpoints
      const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001'
      const response = await fetch(`${API_BASE_URL}/api/v1/admin/queues/status`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('pulse_token')}`,
          'Content-Type': 'application/json'
        }
      })

      if (!response.ok) {
        throw new Error(`Failed to fetch queues status: ${response.statusText}`)
      }

      const data = await response.json()
      console.log('Queues Status Response:', data)
      setQueuesStatus(data)
      setLastUpdated(new Date())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch queues status')
      showError('Fetch Failed', err instanceof Error ? err.message : 'Failed to fetch queues status')
    }
  }

  const fetchWorkerStatus = async () => {
    try {
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
      console.log('Worker Status Response:', data)
      setWorkerStatus(data)
    } catch (err) {
      console.error('Failed to fetch worker status:', err)
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

      // Show success message first
      const scope = queueType ? `${queueType} workers` : 'all workers'
      showSuccess(`Workers ${action === 'start' ? 'Started' : action === 'stop' ? 'Stopped' : 'Restarted'}`, `${result.message} (${scope})`)

      // Wait a moment for workers to fully start/stop, then refresh status
      await new Promise(resolve => setTimeout(resolve, 500))
      await Promise.all([
        fetchQueuesStatus(),
        fetchWorkerStatus()
      ])
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${action} workers`)
      showError(`Worker ${action.charAt(0).toUpperCase() + action.slice(1)} Failed`, err instanceof Error ? err.message : `Failed to ${action} workers`)
    } finally {
      setActionLoading(null)
    }
  }


  // Get queue status info - matches RabbitMQ state exactly
  const getQueueStatusInfo = (queueType: 'extraction' | 'transform' | 'embedding') => {
    if (!queuesStatus) {
      return {
        color: 'text-gray-500',
        bgColor: 'bg-gray-100',
        label: 'unknown'
      }
    }

    const queueInfo = queuesStatus[queueType]
    const state = queueInfo.state.toLowerCase()

    // Match RabbitMQ states exactly - "running" is blue (like job statuses)
    if (state === 'running') {
      return {
        color: 'text-blue-500',
        bgColor: 'bg-blue-100',
        label: 'running'
      }
    } else if (state === 'idle') {
      return {
        color: 'text-gray-500',
        bgColor: 'bg-gray-100',
        label: 'idle'
      }
    } else {
      return {
        color: 'text-gray-500',
        bgColor: 'bg-gray-100',
        label: state
      }
    }
  }

  // Get worker status info (our internal worker processes)
  const getWorkerStatusInfo = (queueType: 'extraction' | 'transform' | 'embedding') => {
    if (!workerStatus || !workerConfig) {
      return {
        color: 'text-gray-500',
        bgColor: 'bg-gray-100',
        label: 'stopped'
      }
    }

    // Get the tier and construct the worker key
    const tier = workerConfig.current_tenant_tier
    const workerKey = `${tier}_${queueType}`
    const workerInfo = workerStatus.workers[workerKey]

    if (!workerInfo) {
      return {
        color: 'text-gray-500',
        bgColor: 'bg-gray-100',
        label: 'stopped'
      }
    }

    // Check if any worker instances are running
    const hasRunningWorkers = workerInfo.instances.some(instance => instance.worker_running)

    if (hasRunningWorkers) {
      return {
        color: 'text-blue-500',
        bgColor: 'bg-blue-100',
        label: 'running'
      }
    } else {
      return {
        color: 'text-gray-500',
        bgColor: 'bg-gray-100',
        label: 'stopped'
      }
    }
  }

  // Helper function to check if workers are running for a specific queue type
  const areWorkersRunning = (queueType: 'extraction' | 'transform' | 'embedding'): boolean => {
    if (!workerStatus || !workerConfig) return false

    const tier = workerConfig.current_tenant_tier
    const workerKey = `${tier}_${queueType}`
    const workerInfo = workerStatus.workers[workerKey]

    if (!workerInfo) return false

    // Check if any worker instances are running
    return workerInfo.instances.some(instance => instance.worker_running)
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

  // Helper function to format memory size
  const formatMemory = (bytes: number): string => {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`
  }

  // Helper function to format rate (messages per second)
  const formatRate = (rate: number): string => {
    if (rate === 0) return '0/s'
    if (rate < 1) return `${rate.toFixed(2)}/s`
    return `${rate.toFixed(1)}/s`
  }

  // Helper function to format worker count (show total or 0)
  const formatWorkerCount = (queueType: 'extraction' | 'transform' | 'embedding'): string => {
    if (!workerConfig) return '0'

    const total = workerConfig.current_tenant_allocation[queueType] ?? 0
    const running = areWorkersRunning(queueType)

    return running ? `${total}` : '0'
  }

  useEffect(() => {
    const loadData = async () => {
      setLoading(true)
      await Promise.all([
        fetchQueuesStatus(),
        fetchWorkerStatus(),
        fetchWorkerConfig(true), // Update local state on initial load
        fetchDatabaseCapacity()
      ])
      setLoading(false)
    }

    loadData()

    // Auto-refresh every 3 seconds
    const interval = setInterval(async () => {
      await Promise.all([
        fetchQueuesStatus(),
        fetchWorkerStatus()
      ])
    }, 3000)

    return () => clearInterval(interval)
  }, [])

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
                  className={`btn-crud-cancel flex items-center gap-2 ${areAllWorkersIdle() ? 'opacity-50 cursor-not-allowed' : ''}`}
                  title={areAllWorkersIdle() ? 'All workers are idle (not running)' : 'Stop all running workers'}
                >
                  <Square className="h-4 w-4" />
                  <span>{actionLoading === 'stop' ? 'Stopping...' : 'Stop All'}</span>
                </button>
              </div>
            </div>
          </CardHeader>

          <CardContent className="p-6">
            {/* Three Queues - All in One Row */}
            <div className="grid grid-cols-3 gap-4">

              {/* Extraction Queue */}
              <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                <div className="flex flex-col space-y-3">
                  {/* Queue Icon & Title */}
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-white border border-gray-200">
                        <Download className="h-4 w-4 text-gray-600" />
                      </div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm font-semibold text-primary">Extraction</h3>
                        <Badge variant="default" className="text-xs px-2 py-0.5 bg-gradient-1-2 text-white border-0 rounded">
                          Premium
                        </Badge>
                      </div>
                    </div>
                    {/* Action Buttons - Icon Only */}
                    <div className="flex items-center space-x-1">
                      <button
                        onClick={() => performWorkerAction('start', 'extraction')}
                        disabled={actionLoading === 'start_extraction' || areWorkersRunning('extraction')}
                        className={`p-2 rounded-lg hover:bg-tertiary transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${areWorkersRunning('extraction') ? 'opacity-50 cursor-not-allowed' : ''}`}
                        title={areWorkersRunning('extraction') ? 'Workers are already running or ready' : 'Start workers'}
                      >
                        <Play className="w-4 h-4 text-secondary" />
                      </button>
                      <button
                        onClick={() => performWorkerAction('stop', 'extraction')}
                        disabled={actionLoading === 'stop_extraction' || !areWorkersRunning('extraction')}
                        className={`p-2 rounded-lg hover:bg-tertiary transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${!areWorkersRunning('extraction') ? 'opacity-50 cursor-not-allowed' : ''}`}
                        title={!areWorkersRunning('extraction') ? 'Workers are idle' : 'Stop workers'}
                      >
                        <Square className="w-4 h-4 text-secondary" />
                      </button>
                    </div>
                  </div>

                  {/* Status Badges & Stats */}
                  {(() => {
                    const queueStatusInfo = getQueueStatusInfo('extraction')
                    const workerStatusInfo = getWorkerStatusInfo('extraction')
                    const queueInfo = queuesStatus?.extraction
                    return (
                      <>
                        <div className="space-y-2">
                          {/* Queue Status */}
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-gray-500">Queue:</span>
                              <Badge variant="default" className={`text-xs px-2 py-0.5 ${queueStatusInfo.bgColor} ${queueStatusInfo.color} border-0 rounded`}>
                                {queueStatusInfo.label}
                              </Badge>
                            </div>
                            <span className="text-xs text-secondary">
                              {queueInfo?.messages ?? 0} messages
                            </span>
                          </div>

                          {/* Worker Status */}
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-gray-500">Workers:</span>
                              <Badge variant="default" className={`text-xs px-2 py-0.5 ${workerStatusInfo.bgColor} ${workerStatusInfo.color} border-0 rounded`}>
                                {workerStatusInfo.label}
                              </Badge>
                            </div>
                            <span className="text-xs text-secondary">
                              {formatWorkerCount('extraction')} workers
                            </span>
                          </div>
                        </div>

                        {/* Additional Queue Metrics */}
                        {queueInfo && (
                          <div className="pt-2 border-t border-gray-200 space-y-1">
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-gray-500 flex items-center gap-1">
                                <Database className="w-3 h-3" />
                                Memory
                              </span>
                              <span className="text-secondary font-medium">{formatMemory(queueInfo.memory)}</span>
                            </div>
                            {queueInfo.message_stats && (
                              <>
                                <div className="flex items-center justify-between text-xs">
                                  <span className="text-gray-500 flex items-center gap-1">
                                    <TrendingUp className="w-3 h-3" />
                                    Published
                                  </span>
                                  <span className="text-secondary font-medium">
                                    {queueInfo.message_stats.publish.toLocaleString()} ({formatRate(queueInfo.message_stats.publish_rate)})
                                  </span>
                                </div>
                                <div className="flex items-center justify-between text-xs">
                                  <span className="text-gray-500">Delivered</span>
                                  <span className="text-secondary font-medium">
                                    {queueInfo.message_stats.deliver.toLocaleString()} ({formatRate(queueInfo.message_stats.deliver_rate)})
                                  </span>
                                </div>
                                <div className="flex items-center justify-between text-xs">
                                  <span className="text-gray-500">Acknowledged</span>
                                  <span className="text-secondary font-medium">
                                    {queueInfo.message_stats.ack.toLocaleString()} ({formatRate(queueInfo.message_stats.ack_rate)})
                                  </span>
                                </div>
                              </>
                            )}
                          </div>
                        )}
                      </>
                    )
                  })()}
                </div>
              </div>

              {/* Transform Queue */}
              <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                <div className="flex flex-col space-y-3">
                  {/* Queue Icon & Title */}
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-white border border-gray-200">
                        <Activity className="h-4 w-4 text-gray-600" />
                      </div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm font-semibold text-primary">Transform</h3>
                        <Badge variant="default" className="text-xs px-2 py-0.5 bg-gradient-1-2 text-white border-0 rounded">
                          Premium
                        </Badge>
                      </div>
                    </div>
                    {/* Action Buttons - Icon Only */}
                    <div className="flex items-center space-x-1">
                      <button
                        onClick={() => performWorkerAction('start', 'transform')}
                        disabled={actionLoading === 'start_transform' || areWorkersRunning('transform')}
                        className={`p-2 rounded-lg hover:bg-tertiary transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${areWorkersRunning('transform') ? 'opacity-50 cursor-not-allowed' : ''}`}
                        title={areWorkersRunning('transform') ? 'Workers are already running or ready' : 'Start workers'}
                      >
                        <Play className="w-4 h-4 text-secondary" />
                      </button>
                      <button
                        onClick={() => performWorkerAction('stop', 'transform')}
                        disabled={actionLoading === 'stop_transform' || !areWorkersRunning('transform')}
                        className={`p-2 rounded-lg hover:bg-tertiary transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${!areWorkersRunning('transform') ? 'opacity-50 cursor-not-allowed' : ''}`}
                        title={!areWorkersRunning('transform') ? 'Workers are idle' : 'Stop workers'}
                      >
                        <Square className="w-4 h-4 text-secondary" />
                      </button>
                    </div>
                  </div>

                  {/* Status Badges & Stats */}
                  {(() => {
                    const queueStatusInfo = getQueueStatusInfo('transform')
                    const workerStatusInfo = getWorkerStatusInfo('transform')
                    const queueInfo = queuesStatus?.transform
                    return (
                      <>
                        <div className="space-y-2">
                          {/* Queue Status */}
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-gray-500">Queue:</span>
                              <Badge variant="default" className={`text-xs px-2 py-0.5 ${queueStatusInfo.bgColor} ${queueStatusInfo.color} border-0 rounded`}>
                                {queueStatusInfo.label}
                              </Badge>
                            </div>
                            <span className="text-xs text-secondary">
                              {queueInfo?.messages ?? 0} messages
                            </span>
                          </div>

                          {/* Worker Status */}
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-gray-500">Workers:</span>
                              <Badge variant="default" className={`text-xs px-2 py-0.5 ${workerStatusInfo.bgColor} ${workerStatusInfo.color} border-0 rounded`}>
                                {workerStatusInfo.label}
                              </Badge>
                            </div>
                            <span className="text-xs text-secondary">
                              {formatWorkerCount('transform')} workers
                            </span>
                          </div>
                        </div>

                        {/* Additional Queue Metrics */}
                        {queueInfo && (
                          <div className="pt-2 border-t border-gray-200 space-y-1">
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-gray-500 flex items-center gap-1">
                                <Database className="w-3 h-3" />
                                Memory
                              </span>
                              <span className="text-secondary font-medium">{formatMemory(queueInfo.memory)}</span>
                            </div>
                            {queueInfo.message_stats && (
                              <>
                                <div className="flex items-center justify-between text-xs">
                                  <span className="text-gray-500 flex items-center gap-1">
                                    <TrendingUp className="w-3 h-3" />
                                    Published
                                  </span>
                                  <span className="text-secondary font-medium">
                                    {queueInfo.message_stats.publish.toLocaleString()} ({formatRate(queueInfo.message_stats.publish_rate)})
                                  </span>
                                </div>
                                <div className="flex items-center justify-between text-xs">
                                  <span className="text-gray-500">Delivered</span>
                                  <span className="text-secondary font-medium">
                                    {queueInfo.message_stats.deliver.toLocaleString()} ({formatRate(queueInfo.message_stats.deliver_rate)})
                                  </span>
                                </div>
                                <div className="flex items-center justify-between text-xs">
                                  <span className="text-gray-500">Acknowledged</span>
                                  <span className="text-secondary font-medium">
                                    {queueInfo.message_stats.ack.toLocaleString()} ({formatRate(queueInfo.message_stats.ack_rate)})
                                  </span>
                                </div>
                              </>
                            )}
                          </div>
                        )}
                      </>
                    )
                  })()}
                </div>
              </div>

              {/* Embedding Queue */}
              <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                <div className="flex flex-col space-y-3">
                  {/* Queue Icon & Title */}
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-white border border-gray-200">
                        <Sparkles className="h-4 w-4 text-gray-600" />
                      </div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm font-semibold text-primary">Embedding</h3>
                        <Badge variant="default" className="text-xs px-2 py-0.5 bg-gradient-1-2 text-white border-0 rounded">
                          Premium
                        </Badge>
                      </div>
                    </div>
                    {/* Action Buttons - Icon Only */}
                    <div className="flex items-center space-x-1">
                      <button
                        onClick={() => performWorkerAction('start', 'embedding')}
                        disabled={actionLoading === 'start_embedding' || areWorkersRunning('embedding')}
                        className={`p-2 rounded-lg hover:bg-tertiary transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${areWorkersRunning('embedding') ? 'opacity-50 cursor-not-allowed' : ''}`}
                        title={areWorkersRunning('embedding') ? 'Workers are already running or ready' : 'Start workers'}
                      >
                        <Play className="w-4 h-4 text-secondary" />
                      </button>
                      <button
                        onClick={() => performWorkerAction('stop', 'embedding')}
                        disabled={actionLoading === 'stop_embedding' || !areWorkersRunning('embedding')}
                        className={`p-2 rounded-lg hover:bg-tertiary transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${!areWorkersRunning('embedding') ? 'opacity-50 cursor-not-allowed' : ''}`}
                        title={!areWorkersRunning('embedding') ? 'Workers are idle' : 'Stop workers'}
                      >
                        <Square className="w-4 h-4 text-secondary" />
                      </button>
                    </div>
                  </div>

                  {/* Status Badges & Stats */}
                  {(() => {
                    const queueStatusInfo = getQueueStatusInfo('embedding')
                    const workerStatusInfo = getWorkerStatusInfo('embedding')
                    const queueInfo = queuesStatus?.embedding
                    return (
                      <>
                        <div className="space-y-2">
                          {/* Queue Status */}
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-gray-500">Queue:</span>
                              <Badge variant="default" className={`text-xs px-2 py-0.5 ${queueStatusInfo.bgColor} ${queueStatusInfo.color} border-0 rounded`}>
                                {queueStatusInfo.label}
                              </Badge>
                            </div>
                            <span className="text-xs text-secondary">
                              {queueInfo?.messages ?? 0} messages
                            </span>
                          </div>

                          {/* Worker Status */}
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-gray-500">Workers:</span>
                              <Badge variant="default" className={`text-xs px-2 py-0.5 ${workerStatusInfo.bgColor} ${workerStatusInfo.color} border-0 rounded`}>
                                {workerStatusInfo.label}
                              </Badge>
                            </div>
                            <span className="text-xs text-secondary">
                              {formatWorkerCount('embedding')} workers
                            </span>
                          </div>
                        </div>

                        {/* Additional Queue Metrics */}
                        {queueInfo && (
                          <div className="pt-2 border-t border-gray-200 space-y-1">
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-gray-500 flex items-center gap-1">
                                <Database className="w-3 h-3" />
                                Memory
                              </span>
                              <span className="text-secondary font-medium">{formatMemory(queueInfo.memory)}</span>
                            </div>
                            {queueInfo.message_stats && (
                              <>
                                <div className="flex items-center justify-between text-xs">
                                  <span className="text-gray-500 flex items-center gap-1">
                                    <TrendingUp className="w-3 h-3" />
                                    Published
                                  </span>
                                  <span className="text-secondary font-medium">
                                    {queueInfo.message_stats.publish.toLocaleString()} ({formatRate(queueInfo.message_stats.publish_rate)})
                                  </span>
                                </div>
                                <div className="flex items-center justify-between text-xs">
                                  <span className="text-gray-500">Delivered</span>
                                  <span className="text-secondary font-medium">
                                    {queueInfo.message_stats.deliver.toLocaleString()} ({formatRate(queueInfo.message_stats.deliver_rate)})
                                  </span>
                                </div>
                                <div className="flex items-center justify-between text-xs">
                                  <span className="text-gray-500">Acknowledged</span>
                                  <span className="text-secondary font-medium">
                                    {queueInfo.message_stats.ack.toLocaleString()} ({formatRate(queueInfo.message_stats.ack_rate)})
                                  </span>
                                </div>
                              </>
                            )}
                          </div>
                        )}
                      </>
                    )
                  })()}
                </div>
              </div>

            </div>
          </CardContent>
        </Card>

        {/* Separate Worker Configuration Card */}
          <Card className="border border-gray-400 mt-6"
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = 'var(--color-1)'
              e.currentTarget.style.boxShadow = '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = '#9ca3af'
              e.currentTarget.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
            }}
          >
            <CardHeader className="border-b border-gray-200">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <Settings className="h-5 w-5" />
                      Worker Configuration
                    </CardTitle>
                    <CardDescription className="mt-1">
                      Configure worker counts for each queue type
                    </CardDescription>
                  </div>
                  <button
                    onClick={() => setShowHelpModal(true)}
                    className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
                    title="Help"
                  >
                    <HelpCircle className="h-5 w-5 text-gray-500" />
                  </button>
                </div>
              </div>
            </CardHeader>

            <CardContent className="p-6">
              <div className="space-y-4">
                {/* Database Capacity Warning */}
                {dbCapacity && dbCapacity.warning_message && (
                  <Alert className="border-yellow-200 bg-yellow-50">
                    <AlertCircle className="h-4 w-4 text-yellow-600" />
                    <AlertDescription className="text-yellow-800 text-xs">
                      {dbCapacity.warning_message}
                    </AlertDescription>
                  </Alert>
                )}

                {/* Worker Count Configuration - MOVED TO TOP */}
                <div className="p-4 bg-white rounded-lg border border-gray-200">
                  <h3 className="text-sm font-semibold text-primary mb-3">Worker Pool Allocation</h3>
                  <div className="flex items-end gap-4">
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 flex-1">
                      {/* Extraction Workers */}
                      <div>
                        <label className="text-xs text-secondary mb-2 block">Extraction Workers</label>
                        <input
                          type="number"
                          min="1"
                          max={dbCapacity?.max_recommended_workers ?? 100}
                          value={extractionWorkers}
                          onChange={(e) => setExtractionWorkers(parseInt(e.target.value) || 1)}
                          disabled={saveLoading}
                          className="w-full p-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-lg font-semibold text-center"
                        />
                      </div>

                      {/* Transform Workers */}
                      <div>
                        <label className="text-xs text-secondary mb-2 block">Transform Workers</label>
                        <input
                          type="number"
                          min="1"
                          max={dbCapacity?.max_recommended_workers ?? 100}
                          value={transformWorkers}
                          onChange={(e) => setTransformWorkers(parseInt(e.target.value) || 1)}
                          disabled={saveLoading}
                          className="w-full p-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-lg font-semibold text-center"
                        />
                      </div>

                      {/* Embedding Workers */}
                      <div>
                        <label className="text-xs text-secondary mb-2 block">Embedding Workers</label>
                        <input
                          type="number"
                          min="1"
                          max={dbCapacity?.max_recommended_workers ?? 100}
                          value={embeddingWorkers}
                          onChange={(e) => setEmbeddingWorkers(parseInt(e.target.value) || 1)}
                          disabled={saveLoading}
                          className="w-full p-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-lg font-semibold text-center"
                        />
                      </div>
                    </div>

                    {/* Total Workers Summary - Compact */}
                    <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 rounded-lg border border-gray-200 h-[42px]">
                      <span className="text-xs text-secondary whitespace-nowrap">Total:</span>
                      <span className="text-sm font-bold">
                        {extractionWorkers + transformWorkers + embeddingWorkers}
                      </span>
                    </div>

                    {/* Capacity Status Indicator */}
                    {dbCapacity && (() => {
                      const totalWorkers = extractionWorkers + transformWorkers + embeddingWorkers;
                      const maxWorkers = dbCapacity.max_recommended_workers;
                      const availableWorkers = dbCapacity.available_for_workers;

                      // Calculate percentage of available capacity (before 20% buffer)
                      const usagePercent = (totalWorkers / availableWorkers) * 100;

                      let status: 'SAFE' | 'WARNING' | 'CRITICAL';
                      let variant: 'default' | 'destructive';
                      let bgColor: string;

                      if (totalWorkers > maxWorkers) {
                        // Above the 80% buffer threshold (max_recommended_workers already has 20% buffer)
                        status = 'CRITICAL';
                        variant = 'destructive';
                        bgColor = 'bg-red-50 border-red-300';
                      } else if (usagePercent > 80) {
                        // Between 80% and the buffer threshold
                        status = 'WARNING';
                        variant = 'default';
                        bgColor = 'bg-yellow-50 border-yellow-300';
                      } else {
                        // Under 80%
                        status = 'SAFE';
                        variant = 'default';
                        bgColor = 'bg-green-50 border-green-300';
                      }

                      return (
                        <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border h-[42px] ${bgColor}`}>
                          <Badge
                            variant={variant}
                            className="text-xs px-2 py-0.5 font-semibold"
                          >
                            {status}
                          </Badge>
                          <span className="text-xs text-secondary">
                            {totalWorkers}/{maxWorkers}
                          </span>
                        </div>
                      );
                    })()}


                    {/* Save Button */}
                    <button
                      onClick={updateWorkerCounts}
                      disabled={saveLoading || !hasUnsavedChanges}
                      className="btn-crud-create disabled:opacity-50 disabled:cursor-not-allowed min-w-[180px] flex items-center gap-2 h-[42px]"
                    >
                      <Save className="h-4 w-4 flex-shrink-0" />
                      <span className="whitespace-nowrap">{saveLoading ? 'Saving...' : 'Save Configuration'}</span>
                    </button>
                  </div>
                </div>

                {/* Database Capacity Stats - Consolidated */}
                {dbCapacity && (
                  <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                    <div className="flex items-center gap-2 mb-3">
                      <Database className="h-4 w-4 text-gray-600" />
                      <h3 className="text-sm font-semibold text-primary">Database Connection Pool</h3>
                    </div>
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
                      <div>
                        <div className="text-xs text-secondary mb-1">Total Connections</div>
                        <div className="font-bold text-lg">{dbCapacity.total_connections}</div>
                        <div className="text-xs text-secondary mt-0.5">Pool: {dbCapacity.pool_size} + Overflow: {dbCapacity.max_overflow}</div>
                      </div>
                      <div>
                        <div className="text-xs text-secondary mb-1">Reserved for UI</div>
                        <div className="font-bold text-lg">{dbCapacity.reserved_for_ui}</div>
                        <div className="text-xs text-secondary mt-0.5">Frontend operations</div>
                      </div>
                      <div>
                        <div className="text-xs text-secondary mb-1">Available for Workers</div>
                        <div className="font-bold text-lg">{dbCapacity.available_for_workers}</div>
                        <div className="text-xs text-secondary mt-0.5">
                          Max: {dbCapacity.max_recommended_workers} <span className="text-gray-400">(20% buffer)</span>
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-secondary mb-1">Current Usage</div>
                        <div className={`font-bold text-lg ${dbCapacity.current_usage_percent > 80 ? 'text-red-600' : dbCapacity.current_usage_percent > 60 ? 'text-yellow-600' : 'text-green-600'}`}>
                          {dbCapacity.current_usage_percent.toFixed(1)}%
                        </div>
                        <div className="text-xs text-secondary mt-0.5">{dbCapacity.current_worker_count} / {dbCapacity.max_recommended_workers} workers</div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Important Notes */}
                <Alert className="border-blue-200 bg-blue-50 mt-4">
                  <AlertCircle className="h-3.5 w-3.5 text-blue-600" />
                  <AlertDescription className="text-blue-800">
                    <div className="text-xs"><strong>Important:</strong> Changes require worker pool restart to take effect. Each worker uses 1 database connection.</div>
                  </AlertDescription>
                </Alert>
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

      {/* Help Modal */}
      {showHelpModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-white border-b border-gray-200 p-4 flex items-center justify-between">
              <h2 className="text-xl font-bold text-primary flex items-center gap-2">
                <HelpCircle className="h-5 w-5" />
                Worker Configuration Help
              </h2>
              <button
                onClick={() => setShowHelpModal(false)}
                className="p-1 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <X className="h-5 w-5 text-gray-500" />
              </button>
            </div>
            <div className="p-6 space-y-6">
              {/* Database Connection Pool */}
              <div>
                <h3 className="text-lg font-semibold text-primary mb-2 flex items-center gap-2">
                  <Database className="h-4 w-4" />
                  Database Connection Pool
                </h3>
                <p className="text-sm text-secondary mb-3">
                  The database has a limited number of connections available. Workers consume these connections to process data.
                </p>
                <div className="space-y-2 text-sm">
                  <div className="flex gap-2">
                    <span className="font-semibold min-w-[140px]">Total Connections:</span>
                    <span className="text-secondary">Maximum database connections (pool + overflow)</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="font-semibold min-w-[140px]">Reserved for UI:</span>
                    <span className="text-secondary">Connections reserved for frontend operations</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="font-semibold min-w-[140px]">Available for Workers:</span>
                    <span className="text-secondary">Connections available for background workers</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="font-semibold min-w-[140px]">Current Usage:</span>
                    <span className="text-secondary">Percentage of worker connections currently in use</span>
                  </div>
                </div>
              </div>

              {/* Worker Types */}
              <div>
                <h3 className="text-lg font-semibold text-primary mb-2">Worker Types</h3>
                <div className="space-y-3">
                  <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                    <div className="flex items-center gap-2 mb-1">
                      <Download className="h-4 w-4 text-gray-600" />
                      <h4 className="font-semibold text-sm">Extraction Workers</h4>
                    </div>
                    <p className="text-xs text-secondary">
                      Fetch data from external sources (Jira, GitHub). Each worker handles API requests and stores raw data.
                    </p>
                  </div>
                  <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                    <div className="flex items-center gap-2 mb-1">
                      <TrendingUp className="h-4 w-4 text-gray-600" />
                      <h4 className="font-semibold text-sm">Transform Workers</h4>
                    </div>
                    <p className="text-xs text-secondary">
                      Process and transform raw data into structured format. Maps custom fields and prepares data for storage.
                    </p>
                  </div>
                  <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                    <div className="flex items-center gap-2 mb-1">
                      <Sparkles className="h-4 w-4 text-gray-600" />
                      <h4 className="font-semibold text-sm">Embedding Workers</h4>
                    </div>
                    <p className="text-xs text-secondary">
                      Generate AI embeddings for semantic search. Processes transformed data and stores vectors in Qdrant.
                    </p>
                  </div>
                </div>
              </div>

              {/* Best Practices */}
              <div>
                <h3 className="text-lg font-semibold text-primary mb-2">Best Practices</h3>
                <ul className="space-y-2 text-sm text-secondary">
                  <li className="flex gap-2">
                    <span className="text-blue-500 font-bold">•</span>
                    <span><strong>Stay within limits:</strong> Keep total workers below the recommended maximum to maintain system stability</span>
                  </li>
                  <li className="flex gap-2">
                    <span className="text-blue-500 font-bold">•</span>
                    <span><strong>Each worker = 1 connection:</strong> Every worker uses one database connection while active</span>
                  </li>
                  <li className="flex gap-2">
                    <span className="text-blue-500 font-bold">•</span>
                    <span><strong>Restart required:</strong> Changes only take effect after restarting worker pools</span>
                  </li>
                  <li className="flex gap-2">
                    <span className="text-blue-500 font-bold">•</span>
                    <span><strong>Monitor usage:</strong> Watch the current usage percentage to avoid overloading the database</span>
                  </li>
                  <li className="flex gap-2">
                    <span className="text-blue-500 font-bold">•</span>
                    <span><strong>Balance allocation:</strong> Distribute workers based on your workload (more extraction for large syncs, more embedding for AI features)</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
