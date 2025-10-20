/**
 * ETL WebSocket Service for real-time worker-specific job progress monitoring
 *
 * Handles:
 * - Worker-specific status updates (extraction, transform, embedding)
 * - Real-time progress tracking with dedicated channels per worker
 * - Multi-user synchronization across same tenant
 * - Connection management per worker type and job
 */

export interface WorkerStatusUpdate {
  type: 'worker_status'
  worker_type: 'extraction' | 'transform' | 'embedding'
  status: 'running' | 'finished' | 'failed'
  step: string
  tenant_id: number
  job_id: number
  timestamp: string
  error_message?: string
}

export interface StepStatus {
  order: number
  display_name: string
  extraction: 'idle' | 'running' | 'finished' | 'failed'
  transform: 'idle' | 'running' | 'finished' | 'failed'
  embedding: 'idle' | 'running' | 'finished' | 'failed'
}

export interface JobProgress {
  extraction: WorkerStatus
  transform: WorkerStatus
  embedding: WorkerStatus
  isActive: boolean
  steps?: {
    [stepName: string]: StepStatus
  }
}

export interface ConnectionStatus {
  connected: boolean
  lastConnected?: Date
  reconnectAttempts: number
}

export interface WorkerStatus {
  status: 'idle' | 'running' | 'finished' | 'failed'
  step?: string
  timestamp?: string
  error_message?: string
}

interface JobEventHandlers {
  onWorkerStatus?: (data: WorkerStatusUpdate) => void
  onJobProgress?: (data: JobProgress) => void
}

interface WebSocketMessage {
  type: string
  worker_type: string
  status: string
  step: string
  tenant_id: number
  job_id: number
  timestamp: string
  error_message?: string
}

class ETLWebSocketService {
  private connections: Map<string, WebSocket> = new Map() // Key: "worker_type_tenant_id_job_id"
  private jobProgress: Map<string, JobProgress> = new Map() // Key: "tenant_id_job_id"
  private eventHandlers: Map<string, JobEventHandlers> = new Map() // Key: "tenant_id_job_id"
  private connectionStatus: Map<string, ConnectionStatus> = new Map() // Key: "tenant_id_job_id"
  private fallbackIntervals: Map<string, NodeJS.Timeout> = new Map() // Key: "tenant_id_job_id"
  private token: string | null = null
  private initializationVersion: number = 0
  private reconnectAttempts: Map<string, number> = new Map()
  private maxReconnectAttempts = 5
  private reconnectDelay = 3000
  private isInitialized = false

  /**
   * Initialize the ETL WebSocket service with authentication token
   */
  async initializeService(token: string): Promise<void> {
    this.token = token
    this.initializationVersion++

    // Clear any existing connections first
    this.disconnectAll()

    // Set initialized flag AFTER clearing connections
    this.isInitialized = true
  }

  /**
   * Get the current initialization version (used to detect service restarts)
   */
  getInitializationVersion(): number {
    return this.initializationVersion
  }

  /**
   * Check if the service is ready to accept connections
   */
  isReady(): boolean {
    return this.isInitialized && this.token !== null
  }

  /**
   * Fetch current worker status from database (hybrid approach fallback)
   */
  private async fetchWorkerStatusFromAPI(tenantId: number, jobId: number): Promise<JobProgress | null> {
    try {
      if (!this.token) {
        console.warn('[ETL-WS] No token available for API fallback')
        return null
      }

      const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001'
      const internalSecret = import.meta.env.VITE_ETL_INTERNAL_SECRET || 'dev-internal-secret-change'

      const response = await fetch(`${apiBaseUrl}/app/etl/jobs/${jobId}/worker-status?tenant_id=${tenantId}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${this.token}`,
          'X-Internal-Auth': internalSecret,
          'Content-Type': 'application/json'
        }
      })

      if (!response.ok) {
        console.warn(`[ETL-WS] API fallback failed: ${response.status} ${response.statusText}`)
        return null
      }

      const data = await response.json()

      // Convert API response to JobProgress format
      // Aggregate worker status across all steps
      const extractionStatuses = Object.values(data.steps).map(step => step.extraction)
      const transformStatuses = Object.values(data.steps).map(step => step.transform)
      const embeddingStatuses = Object.values(data.steps).map(step => step.embedding)

      // Determine overall worker status and current step (running > finished > failed > idle)
      const getOverallStatusAndStep = (statuses: string[], workerType: 'extraction' | 'transform' | 'embedding') => {
        // Find the step that's currently running for this worker
        const runningStep = Object.entries(data.steps).find(([stepName, stepData]) =>
          stepData[workerType] === 'running'
        )

        if (runningStep) {
          return {
            status: 'running',
            step: runningStep[0] // Step name like 'jira_projects_and_issue_types'
          }
        }

        if (statuses.includes('finished')) return { status: 'finished', step: '' }
        if (statuses.includes('failed')) return { status: 'failed', step: '' }
        return { status: 'idle', step: '' }
      }

      const extractionInfo = getOverallStatusAndStep(extractionStatuses, 'extraction')
      const transformInfo = getOverallStatusAndStep(transformStatuses, 'transform')
      const embeddingInfo = getOverallStatusAndStep(embeddingStatuses, 'embedding')

      // Convert steps data to StepStatus format
      const stepsData: { [stepName: string]: StepStatus } = {}
      Object.entries(data.steps).forEach(([stepName, stepData]: [string, any]) => {
        stepsData[stepName] = {
          order: stepData.order || 0,
          display_name: stepData.display_name || stepName,
          extraction: stepData.extraction || 'idle',
          transform: stepData.transform || 'idle',
          embedding: stepData.embedding || 'idle'
        }
      })

      const jobProgress: JobProgress = {
        extraction: {
          status: extractionInfo.status,
          step: extractionInfo.step,
          timestamp: new Date().toISOString()
        },
        transform: {
          status: transformInfo.status,
          step: transformInfo.step,
          timestamp: new Date().toISOString()
        },
        embedding: {
          status: embeddingInfo.status,
          step: embeddingInfo.step,
          timestamp: new Date().toISOString()
        },
        isActive: data.overall === 'RUNNING',
        steps: stepsData
      }

      console.log(`[ETL-WS] Fetched worker status from API for job ${jobId}:`, jobProgress)
      return jobProgress

    } catch (error) {
      console.error('[ETL-WS] Error fetching worker status from API:', error)
      return null
    }
  }

  /**
   * Connect to all worker channels for a specific job
   */
  connectToJob(tenantId: number, jobId: number, handlers: JobEventHandlers): () => void {
    if (!this.isInitialized || !this.token) {
      console.warn(`[ETL-WS] Service not initialized, cannot connect to job ${jobId}`)
      return () => {}
    }

    console.log(`[ETL-WS] Connecting to job ${jobId} for tenant ${tenantId}`)

    const jobKey = `${tenantId}_${jobId}`

    // Store event handlers for this job
    this.eventHandlers.set(jobKey, handlers)

    // Initialize connection status tracking
    this.connectionStatus.set(jobKey, {
      connected: false,
      reconnectAttempts: 0
    })

    // Initialize job progress tracking
    this.jobProgress.set(jobKey, {
      extraction: { status: 'idle' },
      transform: { status: 'idle' },
      embedding: { status: 'idle' },
      isActive: false
    })

    // Hybrid approach: First fetch current status from database
    this.fetchWorkerStatusFromAPI(tenantId, jobId).then(apiStatus => {
      if (apiStatus) {
        this.jobProgress.set(jobKey, apiStatus)
        handlers.onWorkerProgress?.(apiStatus)
        console.log(`[ETL-WS] Loaded initial status from database for job ${jobId}`)
      }
    }).catch(error => {
      console.warn(`[ETL-WS] Failed to load initial status from database: ${error}`)
    })

    // Connect to all 3 worker channels for real-time updates
    const workers: Array<'extraction' | 'transform' | 'embedding'> = ['extraction', 'transform', 'embedding']

    workers.forEach(workerType => {
      console.log(`[ETL-WS] Connecting to ${workerType} worker for job ${jobId}`)
      this.connectToWorkerChannel(workerType, tenantId, jobId)
    })

    // Start periodic fallback (only if WebSocket disconnected)
    this.startFallbackPolling(tenantId, jobId)

    // Return cleanup function
    return () => this.disconnectJob(tenantId, jobId)
  }

  /**
   * Connect to a specific worker channel for a job
   */
  private connectToWorkerChannel(workerType: 'extraction' | 'transform' | 'embedding', tenantId: number, jobId: number): void {
    const connectionKey = `${workerType}_${tenantId}_${jobId}`

    // Check if already connected
    const existingWs = this.connections.get(connectionKey)
    if (existingWs && existingWs.readyState === WebSocket.OPEN) {
      return
    }

    // Close existing connection if any
    this.disconnectWorkerChannel(connectionKey)

    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const backendHost = import.meta.env.VITE_API_BASE_URL?.replace(/^https?:\/\//, '') || 'localhost:3001'
      const wsUrl = `${protocol}//${backendHost}/ws/job/${workerType}/${tenantId}/${jobId}?token=${encodeURIComponent(this.token!)}`

      const ws = new WebSocket(wsUrl)
      this.connections.set(connectionKey, ws)

      ws.onopen = () => {
        console.log(`[ETL-WS] Connected to ${workerType} worker for job ${jobId}`)
        this.reconnectAttempts.set(connectionKey, 0)
        this.updateConnectionStatus(tenantId, jobId, true)
      }

      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data)
          this.handleWorkerMessage(message, tenantId, jobId)
        } catch (error) {
          console.error(`[ETL-WS] Error parsing message from ${workerType}:`, error)
        }
      }

      ws.onclose = (event) => {
        console.log(`[ETL-WS] ${workerType} worker connection closed for job ${jobId}`)
        this.connections.delete(connectionKey)
        this.updateConnectionStatus(tenantId, jobId, false)

        // Attempt reconnection if not a clean close
        if (event.code !== 1000 && this.isInitialized) {
          this.attemptReconnection(connectionKey, workerType, tenantId, jobId)
        }
      }

      ws.onerror = (error) => {
        console.error(`[ETL-WS] ${workerType} worker connection error for job ${jobId}:`, error)
      }

    } catch (error) {
      console.error(`[ETL-WS] Failed to connect to ${workerType} worker for job ${jobId}:`, error)
    }
  }

  /**
   * Handle incoming worker status messages
   */
  private handleWorkerMessage(message: WebSocketMessage, tenantId: number, jobId: number): void {
    console.log(`[ETL-WS] Received message for job ${jobId}:`, message)

    if (message.type !== 'worker_status') {
      return
    }

    const jobKey = `${tenantId}_${jobId}`
    const jobProgress = this.jobProgress.get(jobKey)
    const handlers = this.eventHandlers.get(jobKey)

    if (!jobProgress) {
      console.warn(`[ETL-WS] No job progress found for job ${jobId}`)
      return
    }

    // Update worker status
    const workerStatus: WorkerStatus = {
      status: message.status as 'running' | 'finished' | 'failed',
      step: message.step,
      timestamp: message.timestamp,
      error_message: message.error_message
    }

    // Update the specific worker status
    if (message.worker_type === 'extraction') {
      jobProgress.extraction = workerStatus
      console.log(`[ETL-WS] Updated extraction worker status:`, workerStatus)
    } else if (message.worker_type === 'transform') {
      jobProgress.transform = workerStatus
      console.log(`[ETL-WS] Updated transform worker status:`, workerStatus)
    } else if (message.worker_type === 'embedding') {
      jobProgress.embedding = workerStatus
      console.log(`[ETL-WS] Updated embedding worker status:`, workerStatus)
    }
    jobProgress.isActive = this.isJobActive(jobProgress)
    console.log(`[ETL-WS] Job progress after update:`, jobProgress)

    // Trigger event handlers
    if (handlers?.onWorkerStatus) {
      handlers.onWorkerStatus({
        type: 'worker_status',
        worker_type: message.worker_type as 'extraction' | 'transform' | 'embedding',
        status: message.status as 'running' | 'finished' | 'failed',
        step: message.step,
        tenant_id: tenantId,
        job_id: jobId,
        timestamp: message.timestamp,
        error_message: message.error_message
      })
    }

    if (handlers?.onJobProgress) {
      handlers.onJobProgress(jobProgress)
    }
  }

  /**
   * Check if any worker is currently active
   */
  private isJobActive(jobProgress: JobProgress): boolean {
    return jobProgress.extraction.status === 'running' ||
           jobProgress.transform.status === 'running' ||
           jobProgress.embedding.status === 'running'
  }

  /**
   * Attempt to reconnect to a worker channel
   */
  private attemptReconnection(connectionKey: string, workerType: 'extraction' | 'transform' | 'embedding', tenantId: number, jobId: number): void {
    const attempts = this.reconnectAttempts.get(connectionKey) || 0

    if (attempts < this.maxReconnectAttempts) {
      this.reconnectAttempts.set(connectionKey, attempts + 1)

      setTimeout(() => {
        if (this.isInitialized) {
          console.log(`[ETL-WS] Attempting to reconnect ${workerType} worker (attempt ${attempts + 1})`)
          this.connectToWorkerChannel(workerType, tenantId, jobId)
        }
      }, this.reconnectDelay * (attempts + 1))
    } else {
      console.error(`[ETL-WS] Max reconnection attempts reached for ${workerType} worker`)
    }
  }

  /**
   * Get current job progress
   */
  getJobProgress(tenantId: number, jobId: number): JobProgress | null {
    const jobKey = `${tenantId}_${jobId}`
    return this.jobProgress.get(jobKey) || null
  }

  /**
   * Check if a job is currently active (any worker running)
   */
  isJobRunning(tenantId: number, jobId: number): boolean {
    const progress = this.getJobProgress(tenantId, jobId)
    return progress ? progress.isActive : false
  }

  /**
   * Disconnect from a specific job (all worker channels)
   */
  private disconnectJob(tenantId: number, jobId: number): void {
    const jobKey = `${tenantId}_${jobId}`
    const workers: Array<'extraction' | 'transform' | 'embedding'> = ['extraction', 'transform', 'embedding']

    workers.forEach(workerType => {
      const connectionKey = `${workerType}_${tenantId}_${jobId}`
      this.disconnectWorkerChannel(connectionKey)
    })

    // Stop fallback polling
    this.stopFallbackPolling(tenantId, jobId)

    // Clean up job data
    this.jobProgress.delete(jobKey)
    this.eventHandlers.delete(jobKey)
    this.connectionStatus.delete(jobKey)
  }

  /**
   * Disconnect from a specific worker channel
   */
  private disconnectWorkerChannel(connectionKey: string): void {
    const ws = this.connections.get(connectionKey)
    if (ws) {
      try {
        if (ws.readyState === WebSocket.OPEN) {
          ws.close(1000, 'Manual disconnect')
        }
      } catch (error) {
        // Ignore errors during cleanup
      }
      this.connections.delete(connectionKey)
    }
  }

  /**
   * Disconnect all WebSocket connections
   */
  disconnectAll(): void {
    for (const [, ws] of this.connections) {
      try {
        if (ws.readyState === WebSocket.OPEN) {
          ws.close(1000, 'Service shutdown')
        }
      } catch (error) {
        // Ignore errors during cleanup
      }
    }
    this.connections.clear()
    this.reconnectAttempts.clear()
    this.jobProgress.clear()
    this.eventHandlers.clear()
  }

  /**
   * Shutdown the service completely (used on logout)
   */
  shutdown(): void {
    this.disconnectAll()
    this.isInitialized = false
    this.token = null
  }

  /**
   * Update authentication token and reconnect all active jobs
   */
  async updateToken(newToken: string): Promise<void> {
    this.token = newToken
    // Note: We don't reconnect existing WebSockets as they remain valid
    // New connections will use the updated token
  }

  /**
   * Check if connected to all worker channels for a job
   */
  isConnectedToJob(tenantId: number, jobId: number): boolean {
    const workers: Array<'extraction' | 'transform' | 'embedding'> = ['extraction', 'transform', 'embedding']

    return workers.every(workerType => {
      const connectionKey = `${workerType}_${tenantId}_${jobId}`
      const ws = this.connections.get(connectionKey)
      return ws?.readyState === WebSocket.OPEN
    })
  }

  /**
   * Get connection status for all worker channels
   */
  getConnectionStatus(): Record<string, boolean> {
    const status: Record<string, boolean> = {}
    for (const [connectionKey, ws] of this.connections) {
      status[connectionKey] = ws.readyState === WebSocket.OPEN
    }
    return status
  }

  /**
   * Start periodic fallback polling for a job (hybrid approach)
   */
  private startFallbackPolling(tenantId: number, jobId: number): void {
    const jobKey = `${tenantId}_${jobId}`

    // Clear any existing interval
    const existingInterval = this.fallbackIntervals.get(jobKey)
    if (existingInterval) {
      clearInterval(existingInterval)
    }

    // Start new interval (check every 30 seconds)
    const interval = setInterval(async () => {
      const connectionStatus = this.connectionStatus.get(jobKey)

      // Only fetch from API if WebSocket is disconnected
      if (!connectionStatus?.connected) {
        console.log(`[ETL-WS] WebSocket disconnected for job ${jobId}, using API fallback`)

        const apiStatus = await this.fetchWorkerStatusFromAPI(tenantId, jobId)
        if (apiStatus) {
          this.jobProgress.set(jobKey, apiStatus)

          // Notify handlers
          const handlers = this.eventHandlers.get(jobKey)
          if (handlers?.onWorkerProgress) {
            handlers.onWorkerProgress(apiStatus)
          }

          console.log(`[ETL-WS] Updated job ${jobId} status via API fallback`)
        }
      }
    }, 30000) // 30 seconds

    this.fallbackIntervals.set(jobKey, interval)
    console.log(`[ETL-WS] Started fallback polling for job ${jobId}`)
  }

  /**
   * Stop fallback polling for a job
   */
  private stopFallbackPolling(tenantId: number, jobId: number): void {
    const jobKey = `${tenantId}_${jobId}`
    const interval = this.fallbackIntervals.get(jobKey)

    if (interval) {
      clearInterval(interval)
      this.fallbackIntervals.delete(jobKey)
      console.log(`[ETL-WS] Stopped fallback polling for job ${jobId}`)
    }
  }

  /**
   * Update connection status for a job
   */
  private updateConnectionStatus(tenantId: number, jobId: number, connected: boolean): void {
    const jobKey = `${tenantId}_${jobId}`
    const currentStatus = this.connectionStatus.get(jobKey)

    this.connectionStatus.set(jobKey, {
      connected,
      lastConnected: connected ? new Date() : currentStatus?.lastConnected,
      reconnectAttempts: connected ? 0 : (currentStatus?.reconnectAttempts || 0) + 1
    })

    console.log(`[ETL-WS] Connection status for job ${jobId}: ${connected ? 'connected' : 'disconnected'}`)
  }

  /**
   * Handle job activation/deactivation (legacy compatibility)
   */
  handleJobToggle(jobName: string, active: boolean): void {
    // This method is kept for backward compatibility
    // In the new implementation, connections are managed per job ID
    console.log(`[ETL-WS] Job toggle: ${jobName} -> ${active ? 'active' : 'inactive'}`)
  }
}

// Export singleton instance
export const etlWebSocketService = new ETLWebSocketService()
