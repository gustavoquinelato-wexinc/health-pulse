import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Badge } from '../components/ui/badge'
import { Separator } from '../components/ui/separator'
import { Alert, AlertDescription } from '../components/ui/alert'
import Header from '../components/Header'
import CollapsedSidebar from '../components/CollapsedSidebar'
import { Play, Square, RotateCcw, Activity, Clock, CheckCircle, XCircle, AlertCircle } from 'lucide-react'

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

export default function QueueManagementPage() {
  const [workerStatus, setWorkerStatus] = useState<WorkerStatus | null>(null)
  const [workerLogs, setWorkerLogs] = useState<WorkerLogs | null>(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date())

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
      await Promise.all([fetchWorkerStatus(), fetchWorkerLogs()])
      setLoading(false)
    }

    loadData()

    // Auto-refresh every 10 seconds
    const interval = setInterval(() => {
      fetchWorkerStatus()
      fetchWorkerLogs()
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

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Worker Status Card */}
          <Card>
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
          <Card>
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
        <Card className="mb-8">
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

        {/* Current Tenant Worker Details */}
        {workerStatus?.tenants && Object.keys(workerStatus.tenants).length > 0 && (
          <Card className="mb-8">
            <CardHeader>
              <CardTitle>Your Tenant Workers</CardTitle>
              <CardDescription>
                Detailed status of workers for your tenant
              </CardDescription>
            </CardHeader>
            <CardContent>
              {Object.entries(workerStatus.tenants).map(([tenantId, tenantData]) => (
                <div key={tenantId} className="space-y-4">
                  <div className="flex justify-between items-center">
                    <h4 className="font-semibold">Tenant {tenantId}</h4>
                    <span className="text-sm text-secondary">
                      {tenantData.worker_count} worker(s)
                    </span>
                  </div>

                  {/* Individual Workers for this Tenant */}
                  <div className="space-y-3">
                    {Object.entries(tenantData.workers).map(([workerType, worker]) => (
                      <div key={workerType} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                        <div className="flex items-center gap-3">
                          <div className={`w-3 h-3 rounded-full ${worker.worker_running ? 'bg-green-500' : 'bg-red-500'}`} />
                          <span className="font-medium capitalize">{workerType} Worker</span>
                        </div>
                        <div className="flex items-center gap-4">
                          <span className={`text-sm ${worker.worker_running ? 'text-green-700' : 'text-red-700'}`}>
                            {worker.worker_running ? 'Running' : 'Stopped'}
                          </span>
                          {worker.thread_name && (
                            <span className="text-xs text-secondary">({worker.thread_name})</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {/* Worker Logs */}
        {workerLogs && (
          <Card>
            <CardHeader>
              <CardTitle>Recent Worker Logs</CardTitle>
              <CardDescription>
                Last {workerLogs.logs.length} log entries (Total: {workerLogs.total_lines} lines)
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
        </main>
      </div>
    </div>
  )
}
