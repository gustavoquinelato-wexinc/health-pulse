/**
 * WebSocket service for real-time ETL job progress tracking
 */

interface ProgressUpdate {
  type: 'progress'
  job: string
  percentage: number | null
  step: string
  timestamp: string
}

interface StatusUpdate {
  type: 'status'
  job: string
  status: string
  message?: string
  timestamp: string
}

interface CompletionUpdate {
  type: 'completion'
  job: string
  success: boolean
  summary: any
  timestamp: string
}

type WebSocketMessage = ProgressUpdate | StatusUpdate | CompletionUpdate

interface JobProgressListener {
  onProgress?: (data: ProgressUpdate) => void
  onStatus?: (data: StatusUpdate) => void
  onCompletion?: (data: CompletionUpdate) => void
}

class ETLWebSocketService {
  private connections: Map<string, WebSocket> = new Map()
  private listeners: Map<string, JobProgressListener[]> = new Map()
  private reconnectAttempts: Map<string, number> = new Map()
  private maxReconnectAttempts = 5
  private reconnectDelay = 3000
  private isInitialized = false // Guard against double initialization in React.StrictMode
  private authToken: string | null = null // Store auth token for WebSocket connections

  /**
   * Initialize WebSocket service after user login with authentication token
   * This should be called from AuthContext after successful login
   */
  async initializeService(token: string) {
    // Guard against double initialization (React.StrictMode in dev causes this)
    if (this.isInitialized) {
      // Silently skip - no need to log on every render
      return
    }
    this.isInitialized = true
    this.authToken = token

    // Wait for backend to be available with retry logic
    const backendReady = await this.waitForBackend()
    if (!backendReady) {
      console.error('❌ ETL WebSocket Service: Backend not available after retries')
      return
    }

    // Discover and connect to active jobs
    await this.discoverAndConnectActiveJobs()
  }

  /**
   * Update auth token for future WebSocket connections
   *
   * NOTE: We do NOT reconnect existing WebSocket connections when token refreshes because:
   * 1. WebSocket authentication happens only at connection time (handshake)
   * 2. Once connected, the WebSocket remains valid regardless of token expiry
   * 3. Reconnecting causes unnecessary disruption and triggers status updates
   * 4. New connections (when jobs start) will use the updated token
   *
   * Existing connections will only reconnect if:
   * - Connection drops (network issue, server restart, etc.)
   * - User explicitly disconnects/reconnects
   * - User logs out
   */
  async updateToken(newToken: string) {
    // Silently update token - no need to log on every refresh
    this.authToken = newToken
  }

  /**
   * Disconnect all WebSocket connections (called on logout)
   */
  disconnectAll() {
    console.log('🔌 ETL WebSocket Service: Disconnecting all connections')
    this.connections.forEach((ws, jobName) => {
      try {
        ws.close()
      } catch (error) {
        console.error(`Failed to close WebSocket for ${jobName}:`, error)
      }
    })
    this.connections.clear()
    this.listeners.clear()
    this.reconnectAttempts.clear()
    this.isInitialized = false
    this.authToken = null
  }

  /**
   * Wait for backend service to be available with retry logic
   */
  private async waitForBackend(maxRetries: number = 10, delay: number = 2000): Promise<boolean> {
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      const available = await this.checkBackendHealth()
      if (available) {
        return true
      }

      if (attempt < maxRetries) {
        await new Promise(resolve => setTimeout(resolve, delay))
      }
    }
    console.error('❌ ETL WebSocket Service: Backend health check failed after all retries')
    return false
  }

  /**
   * Discover and connect only to active ETL jobs
   * Uses authenticated API call to fetch active jobs for the user's tenant
   */
  private async discoverAndConnectActiveJobs() {
    try {
      if (!this.authToken) {
        console.error('❌ ETL WebSocket Service: No auth token available')
        return
      }

      // Fetch active jobs using authenticated API call (tenant_id extracted from token)
      const response = await fetch('http://localhost:3001/api/v1/websocket/status?active_jobs=true', {
        headers: {
          'Authorization': `Bearer ${this.authToken}`
        }
      })

      if (!response.ok) {
        console.error(`❌ ETL WebSocket Service: Failed to fetch active jobs - HTTP ${response.status}`)
        return
      }

      const data = await response.json()
      const activeJobs = data.active_jobs || []

      // Only connect to active jobs
      this.initializeActiveJobs(activeJobs)

    } catch (error) {
      console.error('❌ ETL WebSocket Service: Error discovering active jobs:', error)
    }
  }

  /**
   * Check if backend service is available for WebSocket connections
   */
  private async checkBackendHealth(): Promise<boolean> {
    try {
      const response = await fetch('http://localhost:3001/api/v1/websocket/status')
      return response.ok
    } catch (error) {
      return false
    }
  }

  /**
   * Initialize WebSocket connections for all active jobs
   */
  initializeActiveJobs(jobs: Array<{ job_name: string; active: boolean }>) {
    const activeJobs = jobs.filter(job => job.active)
    if (activeJobs.length === 0) {
      return
    }

    // Establish connections for all active jobs with minimal listeners
    activeJobs.forEach(job => {
      if (!this.connections.has(job.job_name)) {
        this.connectToJob(job.job_name, {
          // Minimal listener just to establish connection
          onProgress: () => {},
          onStatus: () => {},
          onCompletion: () => {}
        })
      }
    })
  }

  /**
   * Dynamically manage WebSocket connection when job is toggled on/off
   */
  handleJobToggle(jobName: string, isActive: boolean) {
    if (isActive) {
      // Job activated - establish WebSocket connection
      if (!this.connections.has(jobName)) {
        this.connectToJob(jobName, {
          onProgress: () => {},
          onStatus: () => {},
          onCompletion: () => {}
        })
      }
    } else {
      // Job deactivated - terminate WebSocket connection
      if (this.connections.has(jobName)) {
        this.closeConnection(jobName)
        this.listeners.delete(jobName)
      }
    }
  }

  /**
   * Connect to WebSocket for a specific job
   */
  connectToJob(jobName: string, listener: JobProgressListener): () => void {
    // Add listener
    if (!this.listeners.has(jobName)) {
      this.listeners.set(jobName, [])
    }
    this.listeners.get(jobName)!.push(listener)

    // Create connection if it doesn't exist
    if (!this.connections.has(jobName)) {
      this.createConnection(jobName)
    }

    // Return cleanup function
    return () => {
      this.removeListener(jobName, listener)
    }
  }

  private createConnection(jobName: string) {
    try {
      if (!this.authToken) {
        console.error(`❌ Cannot create WebSocket connection for ${jobName}: No auth token`)
        return
      }

      // Authenticated WebSocket connection - token required
      // Tenant ID is extracted from the JWT token on the backend
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//localhost:3001/ws/progress/${jobName}?token=${encodeURIComponent(this.authToken)}`

      const ws = new WebSocket(wsUrl)
      this.connections.set(jobName, ws)

      ws.onopen = () => {
        this.reconnectAttempts.set(jobName, 0)
      }

      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data)
          this.handleMessage(jobName, message)
        } catch (error) {
          console.error(`❌ Error parsing WebSocket message for ${jobName}:`, error)
        }
      }

      ws.onclose = (event) => {
        this.connections.delete(jobName)

        // Attempt to reconnect if not intentionally closed
        if (event.code !== 1000 && this.shouldReconnect(jobName)) {
          this.scheduleReconnect(jobName)
        }
      }

      ws.onerror = (error) => {
        console.error(`❌ WebSocket error for job: ${jobName}`, error)
      }

    } catch (error) {
      console.error(`❌ Failed to create WebSocket connection for ${jobName}:`, error)
    }
  }

  private handleMessage(jobName: string, message: WebSocketMessage) {
    const listeners = this.listeners.get(jobName) || []
    


    listeners.forEach(listener => {
      try {
        switch (message.type) {
          case 'progress':
            listener.onProgress?.(message)
            break
          case 'status':
            listener.onStatus?.(message)
            break
          case 'completion':
            listener.onCompletion?.(message)
            break
        }
      } catch (error) {
        console.error(`❌ Error handling WebSocket message:`, error)
      }
    })
  }

  private removeListener(jobName: string, listener: JobProgressListener) {
    const listeners = this.listeners.get(jobName)
    if (listeners) {
      const index = listeners.indexOf(listener)
      if (index > -1) {
        listeners.splice(index, 1)
      }

      // Close connection if no more listeners
      if (listeners.length === 0) {
        this.closeConnection(jobName)
        this.listeners.delete(jobName)
      }
    }
  }

  private closeConnection(jobName: string) {
    const ws = this.connections.get(jobName)
    if (ws) {
      ws.close(1000, 'No more listeners')
      this.connections.delete(jobName)
    }
  }

  private shouldReconnect(jobName: string): boolean {
    const attempts = this.reconnectAttempts.get(jobName) || 0
    return attempts < this.maxReconnectAttempts && this.listeners.has(jobName)
  }

  private scheduleReconnect(jobName: string) {
    const attempts = this.reconnectAttempts.get(jobName) || 0
    this.reconnectAttempts.set(jobName, attempts + 1)

    const delay = this.reconnectDelay * Math.pow(2, attempts) // Exponential backoff
    

    
    setTimeout(() => {
      if (this.listeners.has(jobName) && !this.connections.has(jobName)) {
        this.createConnection(jobName)
      }
    }, delay)
  }
}

// Export singleton instance
export const etlWebSocketService = new ETLWebSocketService()

// Export types for use in components
export type { ProgressUpdate, StatusUpdate, CompletionUpdate, JobProgressListener }
