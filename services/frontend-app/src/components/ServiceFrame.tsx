import { useCallback, useEffect, useRef, useState } from 'react'
import { useTheme } from '../contexts/ThemeContext'
import clientLogger from '../utils/clientLogger'

interface ServiceFrameProps {
  /** The path to embed from the ETL service (e.g., '/admin', '/dashboard') */
  servicePath: string
  /** Additional CSS classes for the iframe container */
  className?: string
  /** Minimum height for the iframe */
  minHeight?: string
  /** ETL service base URL - defaults to environment variable */
  serviceUrl?: string
}

interface ThemeMessage {
  type: 'THEME_UPDATE'
  payload: {
    theme: string
    colorSchema: {
      color1: string
      color2: string
      color3: string
      color4: string
      color5: string
    }
    colorSchemaMode: string
  }
}

/**
 * ServiceFrame Component
 * 
 * Embeds ETL service pages via iframe with:
 * - Automatic authentication token passing
 * - Real-time theme synchronization
 * - Responsive sizing and error handling
 */
export default function ServiceFrame({
  servicePath,
  className = '',
  minHeight = 'calc(100vh - 120px)',
  serviceUrl = import.meta.env.VITE_ETL_SERVICE_URL || 'http://localhost:8000'
}: ServiceFrameProps) {
  // Note: user authentication is handled by the iframe service
  const { theme, colorSchema, colorSchemaMode } = useTheme()
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [hasError, setHasError] = useState(false)

  // Get authentication token
  const getAuthToken = useCallback(() => {
    // Try localStorage first (primary storage)
    let token = localStorage.getItem('pulse_token')

    // Fallback to cookies if localStorage is empty
    if (!token) {
      const cookies = document.cookie.split(';')
      const tokenCookie = cookies.find(cookie =>
        cookie.trim().startsWith('pulse_token=')
      )
      if (tokenCookie) {
        token = tokenCookie.split('=')[1]
      }
    }

    return token
  }, [])

  // Inject theme variables into iframe
  const injectThemeIntoIframe = useCallback(() => {
    const iframe = iframeRef.current
    if (!iframe?.contentDocument) return

    try {
      const iframeDoc = iframe.contentDocument
      const iframeRoot = iframeDoc.documentElement

      // Apply theme mode attributes
      iframeRoot.setAttribute('data-theme', theme)
      iframeRoot.setAttribute('data-color-schema', colorSchemaMode)

      // Define theme variables to inject
      const themeVars = {
        // 5-Color Schema
        '--color-1': colorSchema.color1,
        '--color-2': colorSchema.color2,
        '--color-3': colorSchema.color3,
        '--color-4': colorSchema.color4,
        '--color-5': colorSchema.color5,

        // Theme-specific variables
        '--bg-primary': theme === 'dark' ? '#0f172a' : '#ffffff',
        '--bg-secondary': theme === 'dark' ? '#1e293b' : '#f8fafc',
        '--bg-tertiary': theme === 'dark' ? '#334155' : '#f1f5f9',
        '--text-primary': theme === 'dark' ? '#f8fafc' : '#0f172a',
        '--text-secondary': theme === 'dark' ? '#cbd5e1' : '#475569',
        '--text-muted': theme === 'dark' ? '#94a3b8' : '#64748b',
        '--border-color': theme === 'dark' ? '#475569' : '#e2e8f0'
      }

      // Apply all variables to iframe root
      Object.entries(themeVars).forEach(([property, value]) => {
        iframeRoot.style.setProperty(property, value)
      })

      clientLogger.info('Theme injected into ETL iframe', {
        type: 'theme_injection',
        theme,
        colorSchemaMode
      })
    } catch (error) {
      console.warn('Failed to inject theme into iframe:', error)
    }
  }, [theme, colorSchema, colorSchemaMode])

  // Send theme update via postMessage
  const sendThemeMessage = useCallback(() => {
    const iframe = iframeRef.current
    if (!iframe?.contentWindow) return

    const message: ThemeMessage = {
      type: 'THEME_UPDATE',
      payload: {
        theme,
        colorSchema,
        colorSchemaMode
      }
    }

    try {
      iframe.contentWindow.postMessage(message, '*')
      clientLogger.info('Theme message sent to ETL iframe', {
        type: 'theme_message'
      })
    } catch (error) {
      clientLogger.warn('Failed to send theme message', {
        type: 'theme_message_error',
        error: error instanceof Error ? error.message : String(error)
      })
    }
  }, [theme, colorSchema, colorSchemaMode])

  // Handle iframe load event
  const handleIframeLoad = useCallback(() => {
    setIsLoading(false)
    setHasError(false)

    // Wait a bit for iframe to fully initialize
    setTimeout(() => {
      injectThemeIntoIframe()
      sendThemeMessage()
    }, 100)
  }, [injectThemeIntoIframe, sendThemeMessage])

  // Handle iframe error
  const handleIframeError = useCallback(() => {
    setIsLoading(false)
    setHasError(true)
    console.error('Failed to load ETL service iframe')
  }, [])

  // Build iframe URL with authentication and theme parameters
  const buildIframeUrl = useCallback(() => {
    const token = getAuthToken()
    const baseUrl = `${serviceUrl}${servicePath}`

    const params = new URLSearchParams({
      embedded: 'true',
      theme: theme,
      colorMode: colorSchemaMode
    })

    // Add token if available
    if (token) {
      params.set('token', token)
    }

    return `${baseUrl}?${params.toString()}`
  }, [servicePath, serviceUrl, theme, colorSchemaMode, getAuthToken])

  // Update iframe when theme changes
  useEffect(() => {
    if (!isLoading && !hasError) {
      // Small delay to ensure iframe is ready
      const timer = setTimeout(() => {
        injectThemeIntoIframe()
        sendThemeMessage()
      }, 50)

      return () => clearTimeout(timer)
    }
  }, [theme, colorSchema, colorSchemaMode, isLoading, hasError, injectThemeIntoIframe, sendThemeMessage])

  // Show loading state
  if (isLoading) {
    return (
      <div className={`flex items-center justify-center ${className}`} style={{ minHeight }}>
        <div className="text-center space-y-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="text-secondary">Loading ETL Management...</p>
        </div>
      </div>
    )
  }

  // Show error state
  if (hasError) {
    return (
      <div className={`flex items-center justify-center ${className}`} style={{ minHeight }}>
        <div className="text-center space-y-4 p-8">
          <div className="text-red-500 text-4xl">⚠️</div>
          <h3 className="text-lg font-semibold text-primary">Unable to Load ETL Management</h3>
          <p className="text-secondary">
            The ETL service appears to be unavailable. Please check your connection and try again.
          </p>
          <button
            onClick={() => {
              setHasError(false)
              setIsLoading(true)
              // Force iframe reload
              if (iframeRef.current) {
                iframeRef.current.src = buildIframeUrl()
              }
            }}
            className="btn btn-primary px-6 py-2"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className={`relative ${className}`}>
      <iframe
        ref={iframeRef}
        src={buildIframeUrl()}
        className="w-full border-0 bg-primary"
        style={{ minHeight }}
        onLoad={handleIframeLoad}
        onError={handleIframeError}
        title={`ETL Management - ${servicePath}`}
        sandbox="allow-same-origin allow-scripts allow-forms allow-popups allow-modals"
      />
    </div>
  )
}
