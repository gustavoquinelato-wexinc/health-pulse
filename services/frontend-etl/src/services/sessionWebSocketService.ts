/**
 * Session WebSocket Service for real-time session synchronization
 * 
 * Handles:
 * - Logout events (instant logout across all tabs/devices)
 * - Login events (sync new sessions)
 * - Color schema changes (real-time theme updates)
 * - Dark/Light mode changes (instant mode sync)
 */

interface SessionWebSocketMessage {
  type: string
  event: string
  timestamp: string
  [key: string]: any
}

interface SessionEventHandlers {
  onLogout?: () => void
  onLogin?: (email: string) => void
  onColorSchemaChange?: (colors: any) => void
  onThemeModeChange?: (mode: string) => void
}

class SessionWebSocketService {
  private ws: WebSocket | null = null
  private token: string | null = null
  private handlers: SessionEventHandlers = {}
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 3000
  private isConnecting = false
  private shouldReconnect = true
  private pingInterval: NodeJS.Timeout | null = null

  /**
   * Connect to session WebSocket with authentication token
   */
  connect(token: string, handlers: SessionEventHandlers) {
    if (this.isConnecting || this.ws?.readyState === WebSocket.OPEN) {
      return
    }

    this.token = token
    this.handlers = handlers
    this.shouldReconnect = true
    this.isConnecting = true

    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const backendHost = import.meta.env.VITE_API_BASE_URL?.replace(/^https?:\/\//, '') || 'localhost:3001'
      const wsUrl = `${protocol}//${backendHost}/ws/session?token=${encodeURIComponent(token)}`

      this.ws = new WebSocket(wsUrl)

      this.ws.onopen = () => {
        this.isConnecting = false
        this.reconnectAttempts = 0

        // Start ping interval to keep connection alive
        this.startPingInterval()
      }

      this.ws.onmessage = (event) => {
        try {
          const message: SessionWebSocketMessage = JSON.parse(event.data)
          this.handleMessage(message)
        } catch (error) {
          console.error('[SessionWS] Failed to parse message:', error)
        }
      }

      this.ws.onerror = (error) => {
        console.error('[SessionWS] WebSocket error:', error)
        this.isConnecting = false
      }

      this.ws.onclose = (event) => {
        this.isConnecting = false
        this.stopPingInterval()

        // Suppress warnings for React StrictMode double-mount (code 1006 in development)
        const isStrictModeClose = event.code === 1006 && this.ws?.readyState === WebSocket.CLOSED
        if (!isStrictModeClose && event.code !== 1000 && event.code !== 1001) {
          console.warn(`⚠️ Session WebSocket closed (code: ${event.code})`)
        }

        // Attempt to reconnect if not manually disconnected
        if (this.shouldReconnect && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts++
          setTimeout(() => {
            if (this.token && this.shouldReconnect) {
              this.connect(this.token, this.handlers)
            }
          }, this.reconnectDelay * this.reconnectAttempts)
        }
      }
    } catch (error) {
      console.error('[SessionWS] Failed to create WebSocket connection:', error)
      this.isConnecting = false
    }
  }

  /**
   * Handle incoming WebSocket messages
   */
  private handleMessage(message: SessionWebSocketMessage) {
    switch (message.type) {
      case 'SESSION_INVALIDATED':
        // User logged out from another device/tab
        this.handlers.onLogout?.()
        break

      case 'SESSION_CREATED':
        // User logged in from another device (rare, but possible)
        this.handlers.onLogin?.(message.user_email)
        break

      case 'COLOR_SCHEMA_UPDATED':
        // Color schema changed by admin
        this.handlers.onColorSchemaChange?.(message.colors)
        break

      case 'THEME_MODE_UPDATED':
        // Theme mode (dark/light) changed
        this.handlers.onThemeModeChange?.(message.theme_mode)
        break

      case 'pong':
        // Ping response - connection is alive
        break

      default:
        console.warn('[SessionWS] Unknown message type:', message.type)
    }
  }

  /**
   * Start ping interval to keep connection alive
   */
  private startPingInterval() {
    this.stopPingInterval()
    this.pingInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, 30000) // Ping every 30 seconds
  }

  /**
   * Stop ping interval
   */
  private stopPingInterval() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval)
      this.pingInterval = null
    }
  }

  /**
   * Disconnect from session WebSocket
   */
  disconnect() {
    this.shouldReconnect = false
    this.stopPingInterval()

    if (this.ws) {
      try {
        this.ws.close()
      } catch (error) {
        // Silently handle close errors
      }
      this.ws = null
    }

    this.token = null
    this.handlers = {}
    this.reconnectAttempts = 0
    this.isConnecting = false
  }

  /**
   * Check if WebSocket is connected
   */
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }

  /**
   * Update event handlers
   */
  updateHandlers(handlers: SessionEventHandlers) {
    this.handlers = { ...this.handlers, ...handlers }
  }

  /**
   * Update authentication token
   * This is called when the token is refreshed to keep the stored token in sync
   * Note: We don't reconnect the WebSocket because:
   * 1. WebSocket authentication happens only at connection time (handshake)
   * 2. Once connected, the WebSocket remains valid regardless of token expiry
   * 3. The stored token is only used for reconnection attempts
   */
  updateToken(newToken: string) {
    this.token = newToken
  }
}

// Export singleton instance
export const sessionWebSocketService = new SessionWebSocketService()

