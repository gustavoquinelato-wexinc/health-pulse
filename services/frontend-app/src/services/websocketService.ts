/**
 * WebSocket service for real-time updates in the frontend
 * Handles color schema updates and other real-time notifications
 */

interface WebSocketMessage {
  type: string
  [key: string]: any
}

interface ColorUpdateMessage extends WebSocketMessage {
  type: 'color_schema_updated'
  colors: Record<string, string>
  event_type: string
  timestamp: string
}

type MessageHandler = (message: WebSocketMessage) => void

class WebSocketService {
  private ws: WebSocket | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000
  private messageHandlers: Map<string, MessageHandler[]> = new Map()
  private isConnecting = false
  private shouldReconnect = true

  constructor() {
    this.connect()
  }

  private connect(): void {
    if (this.isConnecting || this.ws?.readyState === WebSocket.OPEN) {
      return
    }

    this.isConnecting = true

    try {
      // Connect to ETL service WebSocket for color updates
      // We'll use the orchestrator WebSocket endpoint since it's always available
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const etlHost = import.meta.env.VITE_ETL_SERVICE_URL?.replace(/^https?:\/\//, '') || 'localhost:8000'
      const wsUrl = `${protocol}//${etlHost}/ws/progress/orchestrator`



      this.ws = new WebSocket(wsUrl)

      this.ws.onopen = () => {

        this.isConnecting = false
        this.reconnectAttempts = 0

        // Send ping to keep connection alive
        this.sendPing()

        // Set up periodic ping
        setInterval(() => {
          if (this.ws?.readyState === WebSocket.OPEN) {
            this.sendPing()
          }
        }, 30000) // Ping every 30 seconds
      }

      this.ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data)
          this.handleMessage(message)
        } catch (error) {
          console.error('❌ Error parsing WebSocket message:', error)
        }
      }

      this.ws.onclose = (event) => {
        console.log('🔌 WebSocket connection closed:', event.code, event.reason)
        this.isConnecting = false
        this.ws = null

        // Attempt to reconnect if not intentionally closed
        if (this.shouldReconnect && event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.scheduleReconnect()
        }
      }

      this.ws.onerror = (error) => {
        console.error('❌ WebSocket error:', error)
        this.isConnecting = false
      }

    } catch (error) {
      console.error('❌ Failed to create WebSocket connection:', error)
      this.isConnecting = false
      this.scheduleReconnect()
    }
  }

  private scheduleReconnect(): void {
    this.reconnectAttempts++
    const delay = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1), 30000)

    console.log(`🔄 Scheduling WebSocket reconnect attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts} in ${delay}ms`)

    setTimeout(() => {
      if (this.shouldReconnect) {
        this.connect()
      }
    }, delay)
  }

  private sendPing(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'ping' }))
    }
  }

  private handleMessage(message: WebSocketMessage): void {
    // Handle pong responses
    if (message.type === 'pong') {
      return
    }

    console.log('📨 WebSocket message received:', message.type)

    // Notify registered handlers
    const handlers = this.messageHandlers.get(message.type) || []
    handlers.forEach(handler => {
      try {
        handler(message)
      } catch (error) {
        console.error(`❌ Error in WebSocket message handler for ${message.type}:`, error)
      }
    })

    // Also notify wildcard handlers
    const wildcardHandlers = this.messageHandlers.get('*') || []
    wildcardHandlers.forEach(handler => {
      try {
        handler(message)
      } catch (error) {
        console.error('❌ Error in WebSocket wildcard handler:', error)
      }
    })
  }

  /**
   * Subscribe to WebSocket messages of a specific type
   */
  public on(messageType: string, handler: MessageHandler): () => void {
    if (!this.messageHandlers.has(messageType)) {
      this.messageHandlers.set(messageType, [])
    }

    this.messageHandlers.get(messageType)!.push(handler)

    // Return unsubscribe function
    return () => {
      const handlers = this.messageHandlers.get(messageType)
      if (handlers) {
        const index = handlers.indexOf(handler)
        if (index > -1) {
          handlers.splice(index, 1)
        }
      }
    }
  }

  /**
   * Subscribe to color schema update messages
   */
  public onColorUpdate(handler: (colors: Record<string, string>) => void): () => void {
    return this.on('color_schema_updated', (message) => {
      const colorMessage = message as ColorUpdateMessage
      handler(colorMessage.colors)
    })
  }

  /**
   * Get connection status
   */
  public isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }

  /**
   * Disconnect WebSocket
   */
  public disconnect(): void {
    this.shouldReconnect = false
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect')
      this.ws = null
    }
  }

  /**
   * Reconnect WebSocket
   */
  public reconnect(): void {
    this.disconnect()
    this.shouldReconnect = true
    this.reconnectAttempts = 0
    setTimeout(() => this.connect(), 100)
  }
}

// Create singleton instance
const websocketService = new WebSocketService()

export default websocketService
export type { ColorUpdateMessage, WebSocketMessage }

