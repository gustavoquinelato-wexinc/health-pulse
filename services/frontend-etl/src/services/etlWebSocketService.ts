/**
 * ETL WebSocket Service for real-time job progress monitoring
 * 
 * Handles:
 * - Job progress updates (percentage, current step)
 * - Job status changes (RUNNING, COMPLETED, FAILED)
 * - Job completion notifications
 * - Connection management per job
 */

export interface ProgressUpdate {
  percentage: number
  step: string
  timestamp: string
}

export interface StatusUpdate {
  status: string
  timestamp: string
}

export interface CompletionUpdate {
  status: string
  message: string
  timestamp: string
}

interface JobEventHandlers {
  onProgress?: (data: ProgressUpdate) => void
  onStatus?: (data: StatusUpdate) => void
  onCompletion?: (data: CompletionUpdate) => void
}

interface WebSocketMessage {
  type: string
  job: string
  [key: string]: any
}

class ETLWebSocketService {
  private connections: Map<string, WebSocket> = new Map()
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
   * Connect to a specific job's WebSocket for real-time updates
   */
  connectToJob(jobName: string, handlers: JobEventHandlers): () => void {
    if (!this.isInitialized || !this.token) {
      console.warn(`[ETL-WS] Service not initialized, cannot connect to ${jobName}`)
      return () => {}
    }

    // Check if already connected to prevent duplicate connections (React StrictMode)
    const existingWs = this.connections.get(jobName)
    if (existingWs && existingWs.readyState === WebSocket.OPEN) {
      // Already connected, return cleanup function for existing connection
      return () => this.disconnectJob(jobName)
    }

    // Close existing connection if any
    this.disconnectJob(jobName)

    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const backendHost = import.meta.env.VITE_API_BASE_URL?.replace(/^https?:\/\//, '') || 'localhost:3001'
      const wsUrl = `${protocol}//${backendHost}/ws/progress/${encodeURIComponent(jobName)}?token=${encodeURIComponent(this.token)}`

      const ws = new WebSocket(wsUrl)
      this.connections.set(jobName, ws)

      ws.onopen = () => {
        // Connection successful - reset reconnect attempts
        this.reconnectAttempts.set(jobName, 0)
      }

      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data)
          this.handleMessage(message, handlers)
        } catch (error) {
          console.error(`[ETL-WS] Failed to parse message for ${jobName}:`, error)
        }
      }

      ws.onclose = (event) => {
        this.connections.delete(jobName)

        // Only attempt to reconnect if not manually disconnected (code 1000 = normal closure)
        const attempts = this.reconnectAttempts.get(jobName) || 0
        if (event.code !== 1000 && attempts < this.maxReconnectAttempts && this.isInitialized) {
          this.reconnectAttempts.set(jobName, attempts + 1)
          setTimeout(() => {
            if (this.isInitialized) {
              this.connectToJob(jobName, handlers)
            }
          }, this.reconnectDelay * (attempts + 1))
        }
      }

      ws.onerror = (error) => {
        // Only log errors that aren't from React StrictMode cleanup
        if (ws.readyState !== WebSocket.CLOSED) {
          console.error(`[ETL-WS] WebSocket error for ${jobName}:`, error)
        }
      }

      // Return cleanup function
      return () => this.disconnectJob(jobName)

    } catch (error) {
      console.error(`[ETL-WS] Failed to connect to ${jobName}:`, error)
      return () => {}
    }
  }

  /**
   * Handle incoming WebSocket messages
   */
  private handleMessage(message: WebSocketMessage, handlers: JobEventHandlers) {
    switch (message.type) {
      case 'progress':
        handlers.onProgress?.({
          percentage: message.percentage,
          step: message.step,
          timestamp: message.timestamp
        })
        break

      case 'status':
        handlers.onStatus?.({
          status: message.status,
          timestamp: message.timestamp
        })
        break

      case 'completion':
        handlers.onCompletion?.({
          status: message.success ? 'COMPLETED' : 'FAILED',
          message: message.summary ? JSON.stringify(message.summary) : '',
          timestamp: message.timestamp
        })
        break

      case 'pong':
        // Ping response - connection is alive
        break

      default:
        console.warn(`[ETL-WS] Unknown message type: ${message.type}`)
    }
  }

  /**
   * Disconnect from a specific job
   */
  private disconnectJob(jobName: string) {
    const ws = this.connections.get(jobName)
    if (ws) {
      try {
        // Only close if the WebSocket is open
        if (ws.readyState === WebSocket.OPEN) {
          ws.close(1000, 'Manual disconnect')
        }
        // For other states (CONNECTING, CLOSING, CLOSED), just remove from connections
      } catch (error) {
        // Ignore errors during cleanup (React StrictMode can cause this)
      }
      this.connections.delete(jobName)
    }
  }

  /**
   * Handle job activation/deactivation
   */
  handleJobToggle(jobName: string, active: boolean) {
    if (!active) {
      // Job deactivated, disconnect WebSocket
      this.disconnectJob(jobName)
    }
    // If activated, connection will be established when JobCard component mounts
  }

  /**
   * Disconnect all WebSocket connections
   */
  disconnectAll() {
    for (const [jobName, ws] of this.connections) {
      try {
        // Only close if the WebSocket is open
        if (ws.readyState === WebSocket.OPEN) {
          ws.close(1000, 'Service shutdown')
        }
        // For other states (CONNECTING, CLOSING, CLOSED), just remove from connections
      } catch (error) {
        // Ignore errors during cleanup (React StrictMode can cause this)
      }
    }
    this.connections.clear()
    this.reconnectAttempts.clear()
    // Don't set isInitialized = false here, as this is called during reinitialization
  }

  /**
   * Shutdown the service completely (used on logout)
   */
  shutdown() {
    this.disconnectAll()
    this.isInitialized = false
    this.token = null
  }

  /**
   * Update authentication token
   */
  async updateToken(newToken: string) {
    this.token = newToken
    // Note: We don't reconnect existing WebSockets as they remain valid
    // New connections will use the updated token
  }

  /**
   * Check if connected to a specific job
   */
  isConnectedToJob(jobName: string): boolean {
    const ws = this.connections.get(jobName)
    return ws?.readyState === WebSocket.OPEN
  }

  /**
   * Get connection status for all jobs
   */
  getConnectionStatus(): Record<string, boolean> {
    const status: Record<string, boolean> = {}
    for (const [jobName, ws] of this.connections) {
      status[jobName] = ws.readyState === WebSocket.OPEN
    }
    return status
  }
}

// Export singleton instance
export const etlWebSocketService = new ETLWebSocketService()
