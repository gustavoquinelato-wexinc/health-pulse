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
import { Play, Square, RotateCcw, Activity, Clock, CheckCircle, XCircle, AlertCircle, Settings, Save, Database, Inbox } from 'lucide-react'

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

type Tab = 'overview' | 'configuration'

export default function QueueManagementPage() {
  const [searchParams, setSearchParams] = useSearchParams()
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

  // Initialize active tab from URL or default to 'overview'
  const [activeTab, setActiveTab] = useState<Tab>(() => {
    const tabFromUrl = searchParams.get('tab') as Tab
    const validTabs: Tab[] = ['overview', 'configuration']
    return validTabs.includes(tabFromUrl) ? tabFromUrl : 'overview'
  })

  // Update document title based on active tab
  useEffect(() => {
    const titles = {
      'overview': 'Queue Management - Overview',
      'configuration': 'Queue Management - Configuration'
    }
    document.title = `${titles[activeTab]} - PEM`
  }, [activeTab])

  // Handle tab change and update URL
  const handleTabChange = (tab: Tab) => {
    setActiveTab(tab)
    setSearchParams({ tab })
  }

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

    // Auto-refresh every 5 seconds for real-time queue stats (don't update local state on refresh)
    const interval = setInterval(() => {
      fetchWorkerStatus()
      fetchWorkerConfig(false) // Don't reset user's selections
      fetchDatabaseCapacity()
    }, 5000)

    return () => clearInterval(interval)
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

        {/* Tabs */}
        <div className="border-b border-gray-300 mb-6">
          <nav className="flex space-x-8">
            <button
              onClick={() => handleTabChange('overview')}
              className={`py-3 px-1 border-b-2 font-medium text-sm flex items-center space-x-2 transition-colors ${
                activeTab === 'overview'
                  ? 'border-primary text-primary'
                  : 'border-transparent text-secondary hover:text-primary hover:border-gray-300'
              }`}
            >
              <Activity className="w-4 h-4" />
              <span>Overview</span>
            </button>
            <button
              onClick={() => handleTabChange('configuration')}
              className={`py-3 px-1 border-b-2 font-medium text-sm flex items-center space-x-2 transition-colors ${
                activeTab === 'configuration'
                  ? 'border-primary text-primary'
                  : 'border-transparent text-secondary hover:text-primary hover:border-gray-300'
              }`}
            >
              <Settings className="w-4 h-4" />
              <span>Configuration</span>
            </button>
          </nav>
        </div>

        {/* Overview Tab Content */}
        {activeTab === 'overview' && (
          <div className="space-y-6">

        {/* Global Worker Controls */}
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
          <CardHeader>
            <CardTitle>Global Worker Controls</CardTitle>
            <CardDescription>
              Control all ETL background workers (affects all queue types)
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-4">
              <Button
                onClick={() => performWorkerAction('start')}
                disabled={actionLoading === 'start'}
                className="flex items-center gap-2"
              >
                <Play className="h-4 w-4" />
                {actionLoading === 'start' ? 'Starting...' : 'Start All Workers'}
              </Button>

              <Button
                variant="outline"
                onClick={() => performWorkerAction('stop')}
                disabled={actionLoading === 'stop'}
                className="flex items-center gap-2"
              >
                <Square className="h-4 w-4" />
                {actionLoading === 'stop' ? 'Stopping...' : 'Stop All Workers'}
              </Button>

              <Button
                variant="outline"
                onClick={() => performWorkerAction('restart')}
                disabled={actionLoading === 'restart'}
                className="flex items-center gap-2"
              >
                <RotateCcw className="h-4 w-4" />
                {actionLoading === 'restart' ? 'Restarting...' : 'Restart All Workers'}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Queue Statistics - Real-time */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Extraction Queue */}
          <Card className="border border-green-400"
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = 'var(--color-1)'
              e.currentTarget.style.boxShadow = '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = '#4ade80'
              e.currentTarget.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
            }}
          >
            <CardHeader className="bg-green-50">
              <CardTitle className="flex items-center gap-2 text-green-900">
                <Inbox className="h-5 w-5" />
                Extraction Queue
              </CardTitle>
              <CardDescription>Premium tier extraction queue</CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Messages in Queue:</span>
                  <Badge variant="default" className="text-lg px-3 py-1">
                    {workerStatus?.queue_stats?.tier_queues?.premium?.extraction?.message_count ?? 0}
                  </Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Active Workers:</span>
                  <Badge variant={workerStatus?.workers && Object.keys(workerStatus.workers).some(k => k.includes('extraction')) ? "default" : "destructive"}>
                    {workerConfig?.current_tenant_allocation?.extraction ?? 0}
                  </Badge>
                </div>
                <Separator />

                {/* Worker Controls */}
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    onClick={() => performWorkerAction('start', 'extraction')}
                    disabled={actionLoading === 'start_extraction'}
                    className="flex-1 bg-green-600 hover:bg-green-700 h-8"
                  >
                    <Play className="h-3 w-3 mr-1" />
                    {actionLoading === 'start_extraction' ? 'Starting...' : 'Start'}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => performWorkerAction('stop', 'extraction')}
                    disabled={actionLoading === 'stop_extraction'}
                    className="flex-1 h-8"
                  >
                    <Square className="h-3 w-3 mr-1" />
                    {actionLoading === 'stop_extraction' ? 'Stopping...' : 'Stop'}
                  </Button>
                </div>

                <Separator />

                {/* Worker Status List */}
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold text-green-900">Worker Status:</h4>
                  {workerStatus?.workers && Object.entries(workerStatus.workers)
                    .filter(([key]) => key.includes('extraction'))
                    .map(([key, workerData]) => (
                      <div key={key} className="space-y-1">
                        {workerData.instances.map((instance) => (
                          <div key={instance.worker_key} className="flex items-center justify-between text-xs bg-white p-2 rounded border border-green-200">
                            <div className="flex items-center gap-2">
                              {getStatusIcon(instance.worker_running, instance.thread_alive)}
                              <span>Worker {instance.worker_number + 1}</span>
                            </div>
                            <span className={instance.worker_running && instance.thread_alive ? "text-green-600 font-medium" : "text-red-600"}>
                              {instance.worker_running && instance.thread_alive ? "Running" : "Stopped"}
                            </span>
                          </div>
                        ))}
                      </div>
                    ))}
                  {(!workerStatus?.workers || !Object.keys(workerStatus.workers).some(k => k.includes('extraction'))) && (
                    <div className="text-xs text-secondary text-center p-2 bg-white rounded border border-green-200">
                      No workers running
                    </div>
                  )}
                </div>

                <div className="text-xs text-secondary pt-2">
                  Queue: extraction_queue_premium
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Transform Queue */}
          <Card className="border border-blue-400"
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = 'var(--color-1)'
              e.currentTarget.style.boxShadow = '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = '#60a5fa'
              e.currentTarget.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
            }}
          >
            <CardHeader className="bg-blue-50">
              <CardTitle className="flex items-center gap-2 text-blue-900">
                <Inbox className="h-5 w-5" />
                Transform Queue
              </CardTitle>
              <CardDescription>Premium tier transform queue</CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Messages in Queue:</span>
                  <Badge variant="default" className="text-lg px-3 py-1">
                    {workerStatus?.queue_stats?.tier_queues?.premium?.transform?.message_count ?? 0}
                  </Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Active Workers:</span>
                  <Badge variant={workerStatus?.workers && Object.keys(workerStatus.workers).some(k => k.includes('transform')) ? "default" : "destructive"}>
                    {workerConfig?.current_tenant_allocation?.transform ?? 0}
                  </Badge>
                </div>
                <Separator />

                {/* Worker Controls */}
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    onClick={() => performWorkerAction('start', 'transform')}
                    disabled={actionLoading === 'start_transform'}
                    className="flex-1 bg-blue-600 hover:bg-blue-700 h-8"
                  >
                    <Play className="h-3 w-3 mr-1" />
                    {actionLoading === 'start_transform' ? 'Starting...' : 'Start'}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => performWorkerAction('stop', 'transform')}
                    disabled={actionLoading === 'stop_transform'}
                    className="flex-1 h-8"
                  >
                    <Square className="h-3 w-3 mr-1" />
                    {actionLoading === 'stop_transform' ? 'Stopping...' : 'Stop'}
                  </Button>
                </div>

                <Separator />

                {/* Worker Status List */}
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold text-blue-900">Worker Status:</h4>
                  {workerStatus?.workers && Object.entries(workerStatus.workers)
                    .filter(([key]) => key.includes('transform'))
                    .map(([key, workerData]) => (
                      <div key={key} className="space-y-1">
                        {workerData.instances.map((instance) => (
                          <div key={instance.worker_key} className="flex items-center justify-between text-xs bg-white p-2 rounded border border-blue-200">
                            <div className="flex items-center gap-2">
                              {getStatusIcon(instance.worker_running, instance.thread_alive)}
                              <span>Worker {instance.worker_number + 1}</span>
                            </div>
                            <span className={instance.worker_running && instance.thread_alive ? "text-blue-600 font-medium" : "text-red-600"}>
                              {instance.worker_running && instance.thread_alive ? "Running" : "Stopped"}
                            </span>
                          </div>
                        ))}
                      </div>
                    ))}
                  {(!workerStatus?.workers || !Object.keys(workerStatus.workers).some(k => k.includes('transform'))) && (
                    <div className="text-xs text-secondary text-center p-2 bg-white rounded border border-blue-200">
                      No workers running
                    </div>
                  )}
                </div>

                <div className="text-xs text-secondary pt-2">
                  Queue: transform_queue_premium
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Embedding Queue */}
          <Card className="border border-purple-400"
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = 'var(--color-1)'
              e.currentTarget.style.boxShadow = '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = '#c084fc'
              e.currentTarget.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
            }}
          >
            <CardHeader className="bg-purple-50">
              <CardTitle className="flex items-center gap-2 text-purple-900">
                <Inbox className="h-5 w-5" />
                Embedding Queue
              </CardTitle>
              <CardDescription>Premium tier embedding queue</CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Messages in Queue:</span>
                  <Badge variant="default" className="text-lg px-3 py-1">
                    {workerStatus?.queue_stats?.tier_queues?.premium?.embedding?.message_count ?? 0}
                  </Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Active Workers:</span>
                  <Badge variant={workerStatus?.workers && Object.keys(workerStatus.workers).some(k => k.includes('embedding')) ? "default" : "destructive"}>
                    {workerConfig?.current_tenant_allocation?.embedding ?? 0}
                  </Badge>
                </div>
                <Separator />

                {/* Worker Controls */}
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    onClick={() => performWorkerAction('start', 'embedding')}
                    disabled={actionLoading === 'start_embedding'}
                    className="flex-1 bg-purple-600 hover:bg-purple-700 h-8"
                  >
                    <Play className="h-3 w-3 mr-1" />
                    {actionLoading === 'start_embedding' ? 'Starting...' : 'Start'}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => performWorkerAction('stop', 'embedding')}
                    disabled={actionLoading === 'stop_embedding'}
                    className="flex-1 h-8"
                  >
                    <Square className="h-3 w-3 mr-1" />
                    {actionLoading === 'stop_embedding' ? 'Stopping...' : 'Stop'}
                  </Button>
                </div>

                <Separator />

                {/* Worker Status List */}
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold text-purple-900">Worker Status:</h4>
                  {workerStatus?.workers && Object.entries(workerStatus.workers)
                    .filter(([key]) => key.includes('embedding'))
                    .map(([key, workerData]) => (
                      <div key={key} className="space-y-1">
                        {workerData.instances.map((instance) => (
                          <div key={instance.worker_key} className="flex items-center justify-between text-xs bg-white p-2 rounded border border-purple-200">
                            <div className="flex items-center gap-2">
                              {getStatusIcon(instance.worker_running, instance.thread_alive)}
                              <span>Worker {instance.worker_number + 1}</span>
                            </div>
                            <span className={instance.worker_running && instance.thread_alive ? "text-purple-600 font-medium" : "text-red-600"}>
                              {instance.worker_running && instance.thread_alive ? "Running" : "Stopped"}
                            </span>
                          </div>
                        ))}
                      </div>
                    ))}
                  {(!workerStatus?.workers || !Object.keys(workerStatus.workers).some(k => k.includes('embedding'))) && (
                    <div className="text-xs text-secondary text-center p-2 bg-white rounded border border-purple-200">
                      No workers running
                    </div>
                  )}
                </div>

                <div className="text-xs text-secondary pt-2">
                  Queue: embedding_queue_premium
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

          </div>
        )}

        {/* Configuration Tab Content */}
        {activeTab === 'configuration' && (
          <div className="space-y-6">

        {/* Configuration Header with Save Button */}
        <div className="rounded-lg bg-table-container shadow-md overflow-hidden border border-gray-400">
          <div className="px-6 py-5 flex justify-between items-center bg-table-header">
            <div>
              <h2 className="text-lg font-semibold text-table-header">Worker Configuration</h2>
              <p className="text-sm text-secondary mt-1">Configure worker counts for each queue type</p>
            </div>
            <button
              onClick={updateWorkerCounts}
              disabled={saveLoading || !hasUnsavedChanges}
              className="px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2 font-medium shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Save className="h-4 w-4" />
              <span>{saveLoading ? 'Saving...' : 'Save Configuration'}</span>
            </button>
          </div>
        </div>

        {/* Database Capacity Warning */}
        {dbCapacity && dbCapacity.warning_message && (
          <Alert className="border-yellow-200 bg-yellow-50">
            <AlertCircle className="h-4 w-4 text-yellow-600" />
            <AlertDescription className="text-yellow-800">
              {dbCapacity.warning_message}
            </AlertDescription>
          </Alert>
        )}

        {/* Database Capacity Card */}
        {dbCapacity && (
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
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Database className="h-5 w-5" />
                Database Connection Pool Capacity
              </CardTitle>
              <CardDescription>
                Monitor database connection usage and worker limits
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  <div className="p-3 bg-gray-50 rounded-lg">
                    <div className="text-xs text-secondary">Total Connections</div>
                    <div className="text-2xl font-bold">{dbCapacity.total_connections}</div>
                    <div className="text-xs text-secondary mt-1">Pool: {dbCapacity.pool_size} + Overflow: {dbCapacity.max_overflow}</div>
                  </div>
                  <div className="p-3 bg-blue-50 rounded-lg">
                    <div className="text-xs text-secondary">Reserved for UI</div>
                    <div className="text-2xl font-bold text-blue-600">{dbCapacity.reserved_for_ui}</div>
                    <div className="text-xs text-secondary mt-1">Frontend operations</div>
                  </div>
                  <div className="p-3 bg-green-50 rounded-lg">
                    <div className="text-xs text-secondary">Available for Workers</div>
                    <div className="text-2xl font-bold text-green-600">{dbCapacity.available_for_workers}</div>
                    <div className="text-xs text-secondary mt-1">Max recommended: {dbCapacity.max_recommended_workers}</div>
                  </div>
                  <div className={`p-3 rounded-lg ${dbCapacity.current_usage_percent > 80 ? 'bg-red-50' : dbCapacity.current_usage_percent > 60 ? 'bg-yellow-50' : 'bg-green-50'}`}>
                    <div className="text-xs text-secondary">Current Usage</div>
                    <div className={`text-2xl font-bold ${dbCapacity.current_usage_percent > 80 ? 'text-red-600' : dbCapacity.current_usage_percent > 60 ? 'text-yellow-600' : 'text-green-600'}`}>
                      {dbCapacity.current_usage_percent.toFixed(1)}%
                    </div>
                    <div className="text-xs text-secondary mt-1">{dbCapacity.current_worker_count} / {dbCapacity.max_recommended_workers} workers</div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Worker Count Configuration Card */}
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
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Settings className="h-5 w-5" />
              Worker Count Configuration
            </CardTitle>
            <CardDescription>
              Configure the number of workers for each queue type
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-6">
              {/* Worker Count Inputs */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Extraction Workers */}
                <div className="p-4 bg-green-50 rounded-lg border border-green-200">
                  <label className="block text-sm font-semibold text-green-900 mb-2">
                    Extraction Workers
                  </label>
                  <input
                    type="number"
                    min="1"
                    max={dbCapacity?.max_recommended_workers ?? 100}
                    value={extractionWorkers}
                    onChange={(e) => setExtractionWorkers(parseInt(e.target.value) || 1)}
                    disabled={saveLoading}
                    className="w-full p-3 border border-green-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 text-lg font-semibold text-center"
                  />
                  <div className="text-xs text-secondary mt-2">
                    Current: {originalExtractionWorkers} workers
                  </div>
                </div>

                {/* Transform Workers */}
                <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                  <label className="block text-sm font-semibold text-blue-900 mb-2">
                    Transform Workers
                  </label>
                  <input
                    type="number"
                    min="1"
                    max={dbCapacity?.max_recommended_workers ?? 100}
                    value={transformWorkers}
                    onChange={(e) => setTransformWorkers(parseInt(e.target.value) || 1)}
                    disabled={saveLoading}
                    className="w-full p-3 border border-blue-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-lg font-semibold text-center"
                  />
                  <div className="text-xs text-secondary mt-2">
                    Current: {originalTransformWorkers} workers
                  </div>
                </div>

                {/* Embedding Workers */}
                <div className="p-4 bg-purple-50 rounded-lg border border-purple-200">
                  <label className="block text-sm font-semibold text-purple-900 mb-2">
                    Embedding Workers
                  </label>
                  <input
                    type="number"
                    min="1"
                    max={dbCapacity?.max_recommended_workers ?? 100}
                    value={embeddingWorkers}
                    onChange={(e) => setEmbeddingWorkers(parseInt(e.target.value) || 1)}
                    disabled={saveLoading}
                    className="w-full p-3 border border-purple-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-lg font-semibold text-center"
                  />
                  <div className="text-xs text-secondary mt-2">
                    Current: {originalEmbeddingWorkers} workers
                  </div>
                </div>
              </div>

              {/* Total Workers Summary */}
              <div className="p-4 bg-gray-50 rounded-lg border border-gray-300">
                <div className="flex items-center justify-between">
                  <span className="font-semibold">Total Workers:</span>
                  <div className="flex items-center gap-4">
                    <span className="text-2xl font-bold">
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
                  <div className="mt-2 text-sm text-red-600">
                    ⚠️ Total workers ({extractionWorkers + transformWorkers + embeddingWorkers}) exceeds recommended maximum ({dbCapacity.max_recommended_workers}).
                    Reduce worker counts or increase DB_POOL_SIZE and DB_MAX_OVERFLOW in .env file.
                  </div>
                )}
              </div>

              {/* Important Notes */}
              <Alert className="border-blue-200 bg-blue-50">
                <AlertCircle className="h-4 w-4 text-blue-600" />
                <AlertDescription className="text-blue-800 space-y-2">
                  <div><strong>Important Notes:</strong></div>
                  <ul className="list-disc list-inside space-y-1 text-xs">
                    <li><strong>Restart Required:</strong> Changes will NOT take effect until worker pools are restarted</li>
                    <li><strong>Database Connections:</strong> Each worker uses 1 database connection. Monitor capacity above.</li>
                    <li><strong>Recommended Limits:</strong> Stay within {dbCapacity?.max_recommended_workers ?? 64} workers to maintain 20% buffer</li>
                    <li><strong>Scaling Up:</strong> To add more workers, increase DB_POOL_SIZE and DB_MAX_OVERFLOW in .env file</li>
                    <li><strong>Premium Tier:</strong> All workers are in the premium tier shared pool</li>
                  </ul>
                </AlertDescription>
              </Alert>
            </div>
          </CardContent>
        </Card>
          </div>
        )}
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
