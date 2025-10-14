import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Badge } from '../components/ui/badge'
import { Separator } from '../components/ui/separator'
import { Alert, AlertDescription } from '../components/ui/alert'
import Header from '../components/Header'
import CollapsedSidebar from '../components/CollapsedSidebar'
import { Play, Square, RotateCcw, Activity, Clock, CheckCircle, XCircle, AlertCircle, Settings } from 'lucide-react'

interface WorkerStatus {
  running: boolean
  worker_count: number
  tenant_count: number
  workers: Record<string, {
    worker_running: boolean
    thread_alive: boolean
    thread_name: string
  }>
  tenants: Record<string, {
    worker_count: number
    workers: Record<string, {
      worker_key: string
      worker_running: boolean
      thread_alive: boolean
      thread_name: string
    }>
  }>
  queue_stats: Record<string, any>
  raw_data_stats: Record<string, {
    count: number
    oldest?: string
    newest?: string
  }>
}

interface WorkerLogs {
  logs: string[]
  total_lines: number
}

interface WorkerConfig {
  tenant_id: number
  transform_workers: number
  vectorization_workers: number
}

export default function QueueManagementPage() {
  const [workerStatus, setWorkerStatus] = useState<WorkerStatus | null>(null)
  const [workerLogs, setWorkerLogs] = useState<WorkerLogs | null>(null)
  const [workerConfig, setWorkerConfig] = useState<WorkerConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [scaleLoading, setScaleLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date())

  // Local state for worker count selectors
  const [transformWorkers, setTransformWorkers] = useState(1)
  const [vectorizationWorkers, setVectorizationWorkers] = useState(1)
  const [activeTab, setActiveTab] = useState('overview')

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

  const fetchWorkerLogs = async () => {
    try {
      // Use backend service URL directly for admin endpoints
      const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001'
      const response = await fetch(`${API_BASE_URL}/api/v1/admin/workers/logs?lines=20`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('pulse_token')}`,
          'Content-Type': 'application/json'
        }
      })

      if (!response.ok) {
        throw new Error(`Failed to fetch worker logs: ${response.statusText}`)
      }

      const data = await response.json()
      setWorkerLogs(data)
    } catch (err) {
      console.error('Failed to fetch worker logs:', err)
      // Don't set error for logs - it's not critical
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
        setTransformWorkers(data.transform_workers)
        setVectorizationWorkers(data.vectorization_workers)
      }
    } catch (err) {
      console.error('Failed to fetch worker config:', err)
    }
  }

  const setWorkerScale = async (transformWorkers: number, vectorizationWorkers: number) => {
    setScaleLoading(true)
    setError(null)

    try {
      const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001'
      const response = await fetch(`${API_BASE_URL}/api/v1/admin/workers/config/scale`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('pulse_token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          transform_workers: transformWorkers,
          vectorization_workers: vectorizationWorkers
        })
      })

      if (!response.ok) {
        throw new Error(`Failed to set worker scale: ${response.statusText}`)
      }

      const data = await response.json()

      // Refresh config and update local state to match saved values
      await fetchWorkerConfig(true)

      // Show success message
      setError(null)
      alert(`Worker configuration updated to ${transformWorkers} transform + ${vectorizationWorkers} vectorization workers. Please restart workers to apply changes.`)
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to set worker scale`)
    } finally {
      setScaleLoading(false)
    }
  }

  const performWorkerAction = async (action: string) => {
    setActionLoading(action)
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
        body: JSON.stringify({ action })
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
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${action} workers`)
    } finally {
      setActionLoading(null)
    }
  }



  useEffect(() => {
    const loadData = async () => {
      setLoading(true)
      await Promise.all([fetchWorkerStatus(), fetchWorkerLogs(), fetchWorkerConfig(true)]) // Update local state on initial load
      setLoading(false)
    }

    loadData()

    // Auto-refresh every 10 seconds (don't update local state on refresh)
    const interval = setInterval(() => {
      fetchWorkerStatus()
      fetchWorkerLogs()
      fetchWorkerConfig(false) // Don't reset user's selections
    }, 10000)

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

  const getStatusBadge = (running: boolean, threadAlive: boolean) => {
    if (running && threadAlive) {
      return <Badge variant="default" className="bg-green-100 text-green-800">Running</Badge>
    } else if (running && !threadAlive) {
      return <Badge variant="secondary" className="bg-yellow-100 text-yellow-800">Starting</Badge>
    } else {
      return <Badge variant="destructive">Stopped</Badge>
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
              onClick={() => setActiveTab('overview')}
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
              onClick={() => setActiveTab('configuration')}
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
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Worker Status Card */}
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
                <Activity className="h-5 w-5" />
                Worker Status
              </CardTitle>
              <CardDescription>
                Current status of ETL background workers
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="font-medium">Manager Running:</span>
                  <Badge variant={workerStatus?.running ? "default" : "destructive"}>
                    {workerStatus?.running ? "Active" : "Inactive"}
                  </Badge>
                </div>

                <Separator />

                <div className="space-y-3">
                  <h4 className="font-medium text-sm">Individual Workers:</h4>
                  {workerStatus?.workers && Object.entries(workerStatus.workers).map(([name, status]) => (
                    <div key={name} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                      <div className="flex items-center gap-2">
                        {getStatusIcon(status.worker_running, status.thread_alive)}
                        <span className="font-medium capitalize">{name}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        {getStatusBadge(status.worker_running, status.thread_alive)}
                        {status.thread_name && (
                          <span className="text-xs text-secondary">({status.thread_name})</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Queue Statistics Card */}
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
                <Clock className="h-5 w-5" />
                Processing Queue
              </CardTitle>
              <CardDescription>
                Current data processing status
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {workerStatus?.raw_data_stats && Object.keys(workerStatus.raw_data_stats).length > 0 ? (
                  Object.entries(workerStatus.raw_data_stats).map(([key, stats]) => {
                    const [status, dataType] = key.split('_', 2)
                    return (
                      <div key={key} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                        <div className="flex items-center gap-2">
                          {getDataStatusIcon(status)}
                          <div>
                            <span className="font-medium capitalize">{status}</span>
                            <span className="text-secondary ml-1">({dataType.replace('_', ' ')})</span>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="font-medium">{stats.count} records</div>
                          {stats.oldest && (
                            <div className="text-xs text-secondary">
                              Oldest: {new Date(stats.oldest).toLocaleString()}
                            </div>
                          )}
                        </div>
                      </div>
                    )
                  })
                ) : (
                  <div className="text-center py-4 text-secondary">
                    <CheckCircle className="h-8 w-8 mx-auto mb-2 text-green-500" />
                    No pending data to process
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Worker Controls */}
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
            <CardTitle>Worker Controls</CardTitle>
            <CardDescription>
              Start, stop, or restart ETL background workers for your tenant
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
                {actionLoading === 'start' ? 'Starting...' : 'Start Workers'}
              </Button>

              <Button
                variant="outline"
                onClick={() => performWorkerAction('stop')}
                disabled={actionLoading === 'stop'}
                className="flex items-center gap-2"
              >
                <Square className="h-4 w-4" />
                {actionLoading === 'stop' ? 'Stopping...' : 'Stop Workers'}
              </Button>

              <Button
                variant="outline"
                onClick={() => performWorkerAction('restart')}
                disabled={actionLoading === 'restart'}
                className="flex items-center gap-2"
              >
                <RotateCcw className="h-4 w-4" />
                {actionLoading === 'restart' ? 'Restarting...' : 'Restart Workers'}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Recent Worker Logs */}
        {workerLogs && (
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
              <CardTitle>Recent Worker Logs</CardTitle>
              <CardDescription>
                Last {workerLogs.logs.length} log entries from worker log files (Total: {workerLogs.total_lines} lines)
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="bg-gray-900 text-green-400 p-4 rounded-lg font-mono text-sm max-h-96 overflow-y-auto">
                {workerLogs.logs.map((log, index) => (
                  <div key={index} className="mb-1">
                    {log}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
          </div>
        )}

        {/* Configuration Tab Content */}
        {activeTab === 'configuration' && (
          <div className="space-y-6">
        {/* Worker Scale Configuration */}
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
            <CardTitle>Worker Scale Configuration</CardTitle>
            <CardDescription>
              Configure the number of workers (1-10 per type) based on your data volume. Changes require worker restart.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-6">
              {/* Current Configuration */}
              {workerConfig && (
                <div className="p-4 bg-gray-50 rounded-lg">
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-secondary">Transform Workers:</span>
                      <div className="font-semibold text-lg mt-1">{workerConfig.transform_workers}</div>
                    </div>
                    <div>
                      <span className="text-secondary">Vectorization Workers:</span>
                      <div className="font-semibold text-lg mt-1">{workerConfig.vectorization_workers}</div>
                    </div>
                  </div>
                </div>
              )}

              {/* Worker Count Selectors */}
              <div className="space-y-4">
                <h4 className="font-medium">Configure Worker Counts (1-10):</h4>

                <div className="grid grid-cols-2 gap-6">
                  {/* Transform Workers */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Transform Workers</label>
                    <select
                      value={transformWorkers}
                      onChange={(e) => setTransformWorkers(Number(e.target.value))}
                      disabled={scaleLoading}
                      className="w-full p-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(num => (
                        <option key={num} value={num}>{num} worker{num > 1 ? 's' : ''}</option>
                      ))}
                    </select>
                    <p className="text-xs text-secondary">Process custom fields, projects, issues, PRs</p>
                  </div>

                  {/* Vectorization Workers */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Vectorization Workers</label>
                    <select
                      value={vectorizationWorkers}
                      onChange={(e) => setVectorizationWorkers(Number(e.target.value))}
                      disabled={scaleLoading}
                      className="w-full p-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(num => (
                        <option key={num} value={num}>{num} worker{num > 1 ? 's' : ''}</option>
                      ))}
                    </select>
                    <p className="text-xs text-secondary">Generate embeddings and store in Qdrant</p>
                  </div>
                </div>

                {/* Apply Button */}
                <Button
                  onClick={() => setWorkerScale(transformWorkers, vectorizationWorkers)}
                  disabled={scaleLoading || (transformWorkers === workerConfig?.transform_workers && vectorizationWorkers === workerConfig?.vectorization_workers)}
                  className="w-full"
                >
                  {scaleLoading ? 'Applying...' : 'Apply Worker Configuration'}
                </Button>
              </div>

              {/* Performance Impact Information */}
              <div className="space-y-3">
                <h4 className="font-medium text-sm">Performance Impact:</h4>
                <div className="grid grid-cols-4 gap-3 text-xs">
                  <div className="p-3 bg-blue-50 rounded border border-blue-200">
                    <div className="font-semibold mb-1">Throughput</div>
                    <div className="text-secondary">~{(transformWorkers + vectorizationWorkers) * 50} msg/hour</div>
                  </div>
                  <div className="p-3 bg-purple-50 rounded border border-purple-200">
                    <div className="font-semibold mb-1">Memory</div>
                    <div className="text-secondary">~{(transformWorkers + vectorizationWorkers) * 50}MB</div>
                  </div>
                  <div className="p-3 bg-green-50 rounded border border-green-200">
                    <div className="font-semibold mb-1">CPU Cores</div>
                    <div className="text-secondary">{Math.ceil((transformWorkers + vectorizationWorkers) / 3)}-{Math.ceil((transformWorkers + vectorizationWorkers) / 2)}</div>
                  </div>
                  <div className="p-3 bg-orange-50 rounded border border-orange-200">
                    <div className="font-semibold mb-1">DB Connections</div>
                    <div className="text-secondary">{(transformWorkers + vectorizationWorkers) * 2}</div>
                  </div>
                </div>
              </div>

              {/* Important Notes */}
              <Alert className="border-yellow-200 bg-yellow-50">
                <AlertCircle className="h-4 w-4 text-yellow-600" />
                <AlertDescription className="text-yellow-800 space-y-2">
                  <div><strong>Important Notes:</strong></div>
                  <ul className="list-disc list-inside space-y-1 text-xs">
                    <li><strong>Restart Required:</strong> Worker count changes only apply after restart</li>
                    <li><strong>Resource Usage:</strong> More workers = more memory/CPU usage</li>
                    <li><strong>Database Connections:</strong> Each worker needs DB connection pool</li>
                    <li><strong>Queue Depth:</strong> Monitor queue depth to determine optimal scale</li>
                    <li><strong>Recommended for Full Load:</strong> Set to 8-10 workers before Jira/GitHub sync, then reduce to 1-2 after</li>
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
    </div>
  )
}
