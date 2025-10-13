import axios from 'axios'
import { createContext, ReactNode, useContext, useEffect, useState } from 'react'
import { colorDataService, type ColorData } from '../services/colorDataService'
import { getColorSchemaMode } from '../utils/colorSchemaService'
import { etlWebSocketService } from '../services/websocketService'
import { sessionWebSocketService } from '../services/sessionWebSocketService'

interface ColorSchema {
  color1: string
  color2: string
  color3: string
  color4: string
  color5: string
}

interface ColorSchemaData {
  mode: 'default' | 'custom'
  colors: ColorSchema
  default_colors?: ColorSchema
  custom_colors?: ColorSchema
  on_colors?: Record<string, string>
  on_gradients?: Record<string, string>
  unified_colors?: {
    light: ColorSchema
    dark: ColorSchema
  }
  enhanced_data?: {
    font_contrast_threshold?: number
    colors_defined_in_mode?: string
    adaptive_colors?: Record<string, string>
    cache_info?: {
      cached: boolean
      source: string
    }
  }
}

interface User {
  id: string
  email: string
  role: string
  is_admin: boolean
  name?: string
  first_name?: string
  last_name?: string
  tenant_id: number
  use_accessible_colors?: boolean
  colorSchemaData?: ColorSchemaData
}

interface AuthContextType {
  user: User | null
  login: (email: string, password: string) => Promise<boolean>
  logout: () => void
  isLoading: boolean
  isAuthenticated: boolean
  isAdmin: boolean
  updateAccessibilityPreference: (useAccessibleColors: boolean) => Promise<boolean>
  refreshUserColors: () => Promise<void>
  refreshToken: () => Promise<boolean>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

// Configure axios defaults - Use backend service URL
axios.defaults.baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001'

interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // Load complete color data from API and cache it
  const loadColorSchema = async (): Promise<ColorSchemaData | null> => {
    try {
      const response = await axios.get('/api/v1/admin/color-schema/unified')

      if (response.data.success && response.data.color_data) {
        const colorData: ColorData[] = response.data.color_data

        // Cache complete color data for instant access
        colorDataService.saveToCache(colorData)

        // Get current theme from localStorage/database
        const colorSchemaMode = await getColorSchemaMode()

        // CRITICAL FIX: Filter by color_schema_mode to get the correct colors
        const lightRegular = colorData.find((c: any) =>
          c.theme_mode === 'light' &&
          c.accessibility_level === 'regular' &&
          c.color_schema_mode === colorSchemaMode
        )
        const darkRegular = colorData.find((c: any) =>
          c.theme_mode === 'dark' &&
          c.accessibility_level === 'regular' &&
          c.color_schema_mode === colorSchemaMode
        )

        // If custom colors not found, fallback to default colors
        if (!lightRegular || !darkRegular) {
          const lightDefault = colorData.find((c: any) =>
            c.theme_mode === 'light' &&
            c.accessibility_level === 'regular' &&
            c.color_schema_mode === 'default'
          )
          const darkDefault = colorData.find((c: any) =>
            c.theme_mode === 'dark' &&
            c.accessibility_level === 'regular' &&
            c.color_schema_mode === 'default'
          )

          if (lightDefault && darkDefault) {
            return {
              mode: 'default', // Override mode to match actual colors used
              colors: {
                color1: lightDefault.color1,
                color2: lightDefault.color2,
                color3: lightDefault.color3,
                color4: lightDefault.color4,
                color5: lightDefault.color5
              },
              unified_colors: {
                light: {
                  color1: lightDefault.color1,
                  color2: lightDefault.color2,
                  color3: lightDefault.color3,
                  color4: lightDefault.color4,
                  color5: lightDefault.color5
                },
                dark: {
                  color1: darkDefault.color1,
                  color2: darkDefault.color2,
                  color3: darkDefault.color3,
                  color4: darkDefault.color4,
                  color5: darkDefault.color5
                }
              },
              enhanced_data: {
                cache_info: {
                  cached: false,
                  source: 'unified_api_fallback'
                }
              }
            } as ColorSchemaData
          }
        }

        if (lightRegular && darkRegular) {
          // Convert array format to structured format expected by ThemeContext
          const unifiedColors = {
            light: {
              color1: lightRegular.color1,
              color2: lightRegular.color2,
              color3: lightRegular.color3,
              color4: lightRegular.color4,
              color5: lightRegular.color5
            },
            dark: {
              color1: darkRegular.color1,
              color2: darkRegular.color2,
              color3: darkRegular.color3,
              color4: darkRegular.color4,
              color5: darkRegular.color5
            }
          }

          return {
            mode: colorSchemaMode, // Use centralized mode (no fallback needed here)
            colors: unifiedColors.light, // Default to light for legacy compatibility
            unified_colors: unifiedColors,
            enhanced_data: {
              cache_info: {
                cached: false,
                source: 'unified_api'
              }
            }
          } as ColorSchemaData
        }
      }
    } catch (error: any) {
      console.error('AuthContext: Failed to load color schema:', error)
    }
    return null
  }

  // Load user-specific colors based on accessibility preference
  const loadUserColors = async (): Promise<ColorSchemaData | null> => {
    // IMPORTANT: The /api/v1/user/colors endpoint only returns single-theme colors
    // For proper light/dark theme support, we should use the unified API instead
    // This function is kept for backward compatibility but should delegate to loadColorSchema
    return await loadColorSchema()
  }

  // Preload color data immediately on app start (before authentication)
  useEffect(() => {
    const preloadColorData = async () => {
      try {
        // Try to load color data immediately if we have a token
        const token = localStorage.getItem('pulse_token')
        if (token) {
          // Set up axios header temporarily for color data request
          const tempHeaders = { 'Authorization': `Bearer ${token}` }

          try {
            const response = await axios.get('/api/v1/admin/color-schema/unified', { headers: tempHeaders })
            if (response.data.success && response.data.color_data) {
              // Cache complete color data immediately for instant access
              colorDataService.saveToCache(response.data.color_data)
            }
          } catch (error) {
            console.warn('🎨 Failed to preload color data:', error)
          }
        }
      } catch (error) {
        console.warn('🎨 Error during color data preload:', error)
      }
    }

    // Preload color data first (non-blocking)
    preloadColorData()

    // Then proceed with authentication
    const token = localStorage.getItem('pulse_token')
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`
      validateToken()
    } else {
      // No localStorage token, but check if there's an existing session in Backend Service
      checkExistingSession()
    }

    // Cross-service authentication is handled via postMessage and cookies
  }, [])

  // Temporarily disabled window focus listener to prevent theme toggle interference
  // TODO: Re-enable with better debouncing if cross-frontend sync is needed
  /*
  useEffect(() => {
    let lastThemeToggle = 0

    const handleWindowFocus = async () => {
      if (user) {
        // Prevent immediate sync after theme toggle (debounce for 5 seconds)
        const now = Date.now()
        if (now - lastThemeToggle < 5000) {
          return
        }

        try {
          const themeResponse = await axios.get('/api/v1/user/theme-mode')
          if (themeResponse.data.success) {
            const dbThemeMode = themeResponse.data.mode
            const currentThemeMode = localStorage.getItem('pulse_theme') || 'light'

            if (dbThemeMode !== currentThemeMode) {
              // Theme changed in another frontend, sync it
              localStorage.setItem('pulse_theme', dbThemeMode)
              document.documentElement.setAttribute('data-theme', dbThemeMode)
              ;(window as any).__INITIAL_THEME__ = dbThemeMode

              // Trigger a re-render by updating a dummy state or dispatching an event
              window.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme: dbThemeMode } }))
            }
          }
        } catch (error) {
          // Silently handle theme sync errors
        }
      }
    }

    // Listen for theme toggle events to update debounce timestamp
    const handleThemeToggle = () => {
      lastThemeToggle = Date.now()
    }

    window.addEventListener('focus', handleWindowFocus)
    window.addEventListener('themeToggled', handleThemeToggle)
    return () => {
      window.removeEventListener('focus', handleWindowFocus)
      window.removeEventListener('themeToggled', handleThemeToggle)
    }
  }, [user])
  */

  // Listen for logout events from same-origin tabs via localStorage
  // Note: This is a backup mechanism. Session WebSocket is the primary sync method.
  // localStorage events only work for same-origin tabs (e.g., multiple tabs on port 3333)
  useEffect(() => {
    const handleStorageChange = (event: StorageEvent) => {
      if (event.key === 'pulse_logout_event') {
        // Another tab on same origin logged out, logout this one too
        etlWebSocketService.disconnectAll()
        sessionWebSocketService.disconnect()
        setUser(null)
        localStorage.clear()
        sessionStorage.clear()
        delete axios.defaults.headers.common['Authorization']
        window.location.replace('/login')
      }
    }

    window.addEventListener('storage', handleStorageChange)
    return () => window.removeEventListener('storage', handleStorageChange)
  }, [])

  // Listen for cross-service authentication from old ETL service
  // Note: This is for backward compatibility with old etl-service (port 8000)
  // New authentication flow uses Session WebSocket
  useEffect(() => {
    const handleMessage = async (event: MessageEvent) => {
      // Only accept AUTH_SUCCESS messages from trusted origins
      const trustedOrigins = ['http://localhost:8000']; // Old ETL service

      if (event.data.type === 'AUTH_SUCCESS' && event.data.token) {
        if (!trustedOrigins.includes(event.origin)) {
          return; // Only accept AUTH_SUCCESS from trusted origins
        }

        // Store the token
        localStorage.setItem('pulse_token', event.data.token);
        axios.defaults.headers.common['Authorization'] = `Bearer ${event.data.token}`;

        // Load theme from database for cross-service authentication
        try {
          const themeResponse = await axios.get('/api/v1/user/theme-mode', {
            headers: { 'Authorization': `Bearer ${event.data.token}` }
          })
          if (themeResponse.data.success) {
            const userThemeMode = themeResponse.data.mode

            // Broadcast to all storage layers
            localStorage.setItem('pulse_theme', userThemeMode)
            document.documentElement.setAttribute('data-theme', userThemeMode)
            ;(window as any).__INITIAL_THEME__ = userThemeMode
          }
        } catch (error) {
          console.warn('Failed to load theme during cross-service auth:', error)
        }

        // Set user data if provided
        if (event.data.user) {
          const formattedUser = {
            id: event.data.user.id.toString(),
            email: event.data.user.email,
            name: event.data.user.first_name && event.data.user.last_name
              ? `${event.data.user.first_name} ${event.data.user.last_name}`
              : event.data.user.first_name || event.data.user.last_name || event.data.user.email.split('@')[0],
            first_name: event.data.user.first_name,
            last_name: event.data.user.last_name,
            role: event.data.user.role,
            is_admin: event.data.user.is_admin,
            tenant_id: event.data.user.tenant_id,
            colorSchemaData: undefined
          }

          setUser(formattedUser);

          // Load color schema immediately and cache it
          try {
            const colorSchemaData = await loadColorSchema()
            if (colorSchemaData) {
              setUser(prev => prev ? { ...prev, colorSchemaData } : prev)
            }
          } catch (error) {
            console.warn('Failed to load color schema during cross-service auth:', error)
          }

          // Initialize WebSocket services
          try {
            await etlWebSocketService.initializeService(event.data.token)
            // WebSocket service initialized - only log errors
          } catch (error) {
            console.error('❌ Failed to initialize WebSocket service:', error)
          }

          // Connect to session WebSocket
          sessionWebSocketService.connect(event.data.token, {
            onLogout: () => logout(),
            onThemeModeChange: (mode: string) => {
              localStorage.setItem('pulse_theme', mode)
              document.documentElement.setAttribute('data-theme', mode)
              ;(window as any).__INITIAL_THEME__ = mode
            },
            onColorSchemaChange: (colors: any) => refreshUserColors()
          })

          setIsLoading(false);
        } else {
          // Validate the token to get user data
          validateToken();
        }
      }
      // Note: LOGOUT_EVENT via postMessage removed - now handled by Session WebSocket
    }

    window.addEventListener('message', handleMessage)
    return () => window.removeEventListener('message', handleMessage)
  }, [])

  // Periodic token refresh and session validation
  useEffect(() => {
    if (!user) return

    const interval = setInterval(async () => {
      try {
        const token = localStorage.getItem('pulse_token')
        if (!token) {
          // Token was removed, logout
          console.warn('⚠️ Token removed from localStorage, logging out')
          setUser(null)
          window.location.replace('/login')
          return
        }

        // Check if token is close to expiry and refresh proactively
        try {
          const payload = JSON.parse(atob(token.split('.')[1]))
          const expiryTime = payload.exp * 1000 // Convert to milliseconds
          const currentTime = Date.now()
          const timeUntilExpiry = expiryTime - currentTime

          // Refresh token if it expires in less than 5 minutes (300 seconds)
          // This gives us plenty of buffer time before actual expiry
          if (timeUntilExpiry < 300000) {
            // Silently refresh - only log errors
            const refreshed = await refreshToken()
            if (!refreshed) {
              console.warn('❌ Token refresh failed, logging out')
              setUser(null)
              localStorage.clear()
              sessionStorage.clear()
              delete axios.defaults.headers.common['Authorization']
              etlWebSocketService.disconnectAll()
              window.location.replace('/login')
              return
            }
            // Token refreshed successfully - no need to log
          }
        } catch (tokenParseError) {
          console.warn('Failed to parse token for expiry check:', tokenParseError)
          // Don't logout on parse error - token might still be valid
        }

        // Periodic validation check (less aggressive - only logout on 401)
        try {
          const response = await axios.post('/api/v1/auth/validate', {}, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('pulse_token')}` }
          })

          if (!response.data.valid) {
            // Session invalid, logout
            console.warn('⚠️ Session validation failed, logging out')
            setUser(null)
            localStorage.clear()
            sessionStorage.clear()
            delete axios.defaults.headers.common['Authorization']
            etlWebSocketService.disconnectAll()
            window.location.replace('/login')
          }
        } catch (validationError: any) {
          // Only logout on 401 Unauthorized - ignore network errors
          if (validationError?.response?.status === 401) {
            console.warn('⚠️ Session unauthorized (401), logging out')
            setUser(null)
            localStorage.clear()
            sessionStorage.clear()
            delete axios.defaults.headers.common['Authorization']
            etlWebSocketService.disconnectAll()
            window.location.replace('/login')
          } else {
            // Network error or other issue - don't logout, just log warning
            console.warn('⚠️ Session validation error (non-401), keeping session:', validationError?.message)
          }
        }
      } catch (error) {
        // Unexpected error in interval - log but don't logout
        console.error('❌ Error in session validation interval:', error)
      }
    }, 60000) // Check every 60 seconds (1 minute)

    return () => clearInterval(interval)
  }, [user])

  const checkExistingSession = async () => {
    try {
      setIsLoading(true)

      // Check if there's an existing session in Backend Service (via cookies)
      // Don't send Authorization header since we don't have a token
      const response = await axios.post('/api/v1/auth/validate', {}, {
        headers: {
          // Remove Authorization header for this request
          'Authorization': undefined
        },
        // Include cookies in the request
        withCredentials: true
      })

      if (response.data.valid && response.data.user) {
        // Found existing session! The token should already be in cookies
        const { user } = response.data

        // Try to get token from cookies (set by ETL service or other frontends)
        const cookieToken = document.cookie
          .split('; ')
          .find(row => row.startsWith('pulse_token='))
          ?.split('=')[1]

        if (cookieToken) {
          localStorage.setItem('pulse_token', cookieToken)
          axios.defaults.headers.common['Authorization'] = `Bearer ${cookieToken}`
        }

        // Load theme from database during cross-service session detection
        let userThemeMode = localStorage.getItem('pulse_theme') || 'light'
        try {
          const themeResponse = await axios.get('/api/v1/user/theme-mode')
          if (themeResponse.data.success && themeResponse.data.mode !== userThemeMode) {
            userThemeMode = themeResponse.data.mode

            // Update all storage layers to sync with database
            localStorage.setItem('pulse_theme', userThemeMode)
            document.documentElement.setAttribute('data-theme', userThemeMode)
            ;(window as any).__INITIAL_THEME__ = userThemeMode
          }
        } catch (error) {
          console.warn('Failed to sync theme during cross-service session detection:', error)
        }

        const formattedUser = {
          id: user.id.toString(),
          email: user.email,
          name: user.first_name && user.last_name
            ? `${user.first_name} ${user.last_name}`
            : user.first_name || user.last_name || user.email.split('@')[0],
          first_name: user.first_name,
          last_name: user.last_name,
          role: user.role,
          is_admin: user.is_admin,
          tenant_id: user.tenant_id,
          colorSchemaData: undefined
        }

        setUser(formattedUser)

        // Load color schema immediately and cache it
        try {
          const colorSchemaData = await loadColorSchema()
          if (colorSchemaData) {
            setUser(prev => prev ? { ...prev, colorSchemaData } : prev)
          }
        } catch (error) {
          console.warn('Failed to load color schema during session check:', error)
        }

        // Initialize WebSocket services after successful session detection
        const token = localStorage.getItem('pulse_token')
        if (token) {
          try {
            await etlWebSocketService.initializeService(token)
          } catch (error) {
            console.error('❌ Failed to initialize WebSocket service:', error)
          }

          // Connect to session WebSocket
          sessionWebSocketService.connect(token, {
            onLogout: () => logout(),
            onThemeModeChange: (mode: string) => {
              localStorage.setItem('pulse_theme', mode)
              document.documentElement.setAttribute('data-theme', mode)
              ;(window as any).__INITIAL_THEME__ = mode
            },
            onColorSchemaChange: (colors: any) => refreshUserColors()
          })
        }

        // IMPORTANT: Set loading to false after successful session detection
        setIsLoading(false)
      } else {
        // No existing session found
        setIsLoading(false)
      }
    } catch (error) {
      // No existing session or error occurred
      setIsLoading(false)
    }
  }

  const validateToken = async () => {
    try {
      const response = await axios.post('/api/v1/auth/validate')

      if (response.data.valid && response.data.user) {
        const { user } = response.data

        // Load theme from database during token validation (for cross-service sync)
        let userThemeMode = localStorage.getItem('pulse_theme') || 'light'
        try {
          const themeResponse = await axios.get('/api/v1/user/theme-mode')
          if (themeResponse.data.success && themeResponse.data.mode !== userThemeMode) {
            userThemeMode = themeResponse.data.mode

            // Update all storage layers to sync with database
            localStorage.setItem('pulse_theme', userThemeMode)
            document.documentElement.setAttribute('data-theme', userThemeMode)
            ;(window as any).__INITIAL_THEME__ = userThemeMode
          }
        } catch (error) {
          console.warn('Failed to sync theme during validation:', error)
        }

        const formattedUser = {
          id: user.id.toString(),
          email: user.email,
          name: user.first_name && user.last_name
            ? `${user.first_name} ${user.last_name}`
            : user.first_name || user.last_name || user.email.split('@')[0],
          first_name: user.first_name,
          last_name: user.last_name,
          role: user.role,
          is_admin: user.is_admin,
          tenant_id: user.tenant_id,
          colorSchemaData: undefined
        }

        setUser(formattedUser)

        // Load color schema immediately and cache it
        try {
          const colorSchemaData = await loadColorSchema()
          if (colorSchemaData) {
            setUser(prev => prev ? { ...prev, colorSchemaData } : prev)
          }
        } catch (error) {
          console.warn('Failed to load color schema during token validation:', error)
        }

        // Initialize WebSocket service with existing token (user already logged in)
        const token = localStorage.getItem('pulse_token')
        if (token) {
          try {
            await etlWebSocketService.initializeService(token)
            // WebSocket service initialized - only log errors
          } catch (error) {
            console.error('❌ Failed to initialize WebSocket service:', error)
          }

          // Connect to session WebSocket for real-time sync
          sessionWebSocketService.connect(token, {
            onLogout: () => {
              console.log('[SessionWS] Logout event received - logging out')
              logout()
            },
            onThemeModeChange: (mode: string) => {
              console.log('[SessionWS] Theme mode changed to:', mode)
              // Update theme immediately
              localStorage.setItem('pulse_theme', mode)
              document.documentElement.setAttribute('data-theme', mode)
              ;(window as any).__INITIAL_THEME__ = mode
            },
            onColorSchemaChange: (colors: any) => {
              console.log('[SessionWS] Color schema changed')
              // Refresh color schema
              refreshUserColors()
            }
          })
        }
      } else {
        localStorage.removeItem('pulse_token')
        delete axios.defaults.headers.common['Authorization']
      }
    } catch (error) {
      localStorage.removeItem('pulse_token')
      delete axios.defaults.headers.common['Authorization']
    } finally {
      setIsLoading(false)
    }
  }

  const login = async (email: string, password: string): Promise<boolean> => {
    try {
      setIsLoading(true)

      const response = await axios.post('/auth/login', {
        email: email.toLowerCase().trim(),
        password: password
      })

      if (response.data.success && response.data.token) {
        const { token, user } = response.data

        localStorage.setItem('pulse_token', token)
        axios.defaults.headers.common['Authorization'] = `Bearer ${token}`

        // Load theme mode from database FIRST to prevent flash
        let userThemeMode = 'light' // Default fallback
        try {
          const themeResponse = await axios.get('/api/v1/user/theme-mode', {
            headers: { 'Authorization': `Bearer ${token}` }
          })
          if (themeResponse.data.success) {
            userThemeMode = themeResponse.data.mode

            // Immediately broadcast to all storage layers
            localStorage.setItem('pulse_theme', userThemeMode)
            document.documentElement.setAttribute('data-theme', userThemeMode)
            ;(window as any).__INITIAL_THEME__ = userThemeMode
          }
        } catch (error) {
          console.warn('Failed to load theme from database, using default:', error)
        }

        // Load color schema before setting user
        let colorSchemaData = await loadColorSchema()

        const formattedUser = {
          id: user.id.toString(),
          email: user.email,
          name: user.first_name && user.last_name
            ? `${user.first_name} ${user.last_name}`
            : user.first_name || user.last_name || user.email.split('@')[0],
          first_name: user.first_name,
          last_name: user.last_name,
          role: user.role,
          is_admin: user.is_admin,
          tenant_id: user.tenant_id,
          colorSchemaData: colorSchemaData ?? undefined
        }

        setUser(formattedUser)

        // Set up cross-service cookie for other frontends
        setupCrossServiceCookie(token)

        // Initialize WebSocket service with authenticated token
        // This connects to all active ETL jobs for real-time progress updates
        try {
          await etlWebSocketService.initializeService(token)
          // WebSocket service initialized - only log errors
        } catch (error) {
          console.error('❌ Failed to initialize WebSocket service:', error)
        }

        return true
      } else {
        return false
      }
    } catch (error) {
      localStorage.removeItem('pulse_token')
      delete axios.defaults.headers.common['Authorization']
      return false
    } finally {
      setIsLoading(false)
    }
  }

  const setupCrossServiceCookie = (token: string) => {
    try {
      // Set cookie for cross-service authentication with other frontends
      // For localhost development, we need to set cookies for each specific port
      // since .localhost domain doesn't work reliably in all browsers

      // Set cookie for current domain (no domain specified = current host only)
      document.cookie = `pulse_token=${token}; path=/; max-age=86400; SameSite=lax`

      // Try to set domain-wide cookie for localhost development
      try {
        document.cookie = `pulse_token=${token}; path=/; domain=.localhost; max-age=86400; SameSite=lax`
      } catch (domainError) {
        // Ignore domain-specific errors - some browsers don't support .localhost
      }

      // Cross-service cookie setup completed
    } catch (error) {
      console.error('Failed to set cross-service cookie:', error)
    }
  }

  // Update user accessibility preference
  const updateAccessibilityPreference = async (useAccessibleColors: boolean): Promise<boolean> => {
    try {
      const response = await axios.post('/api/v1/user/accessibility-preference', {
        use_accessible_colors: useAccessibleColors
      })

      if (response.data.success) {
        // Update user state
        setUser(prev => prev ? { ...prev, use_accessible_colors: useAccessibleColors } : prev)

        // Refresh colors to apply new accessibility preference
        await refreshUserColors()

        // Accessibility preference updated - only log errors
        return true
      }
    } catch (error) {
      console.error('❌ Failed to update accessibility preference:', error)
    }
    return false
  }

  // Refresh user colors (useful after preference changes)
  const refreshUserColors = async (): Promise<void> => {
    try {
      // For admin users, prioritize admin colors (unified API) since they might have just saved changes
      // For regular users, try user-specific colors first
      let colorSchemaData: ColorSchemaData | null = null

      if (user?.is_admin) {
        // Admin users: Try admin colors first (they might have just saved changes)
        colorSchemaData = await loadColorSchema()

        // Fallback to user-specific colors if admin colors fail
        if (!colorSchemaData) {
          colorSchemaData = await loadUserColors()
        }
      } else {
        // Regular users: Try user-specific colors first
        colorSchemaData = await loadUserColors()

        // Fallback to admin colors if user colors fail
        if (!colorSchemaData) {
          colorSchemaData = await loadColorSchema()
        }
      }

      if (colorSchemaData) {
        // Force a new object reference to ensure React detects the change
        setUser(prev => prev ? {
          ...prev,
          colorSchemaData: {
            ...colorSchemaData,
            _refreshTimestamp: Date.now() // Force dependency change
          }
        } : prev)
      }
    } catch (error) {
      console.error('❌ Failed to refresh user colors:', error)
    }
  }

  const logout = async () => {
    setUser(null)

    // Disconnect all WebSocket connections
    try {
      etlWebSocketService.disconnectAll()
      sessionWebSocketService.disconnect()
      // WebSocket services disconnected - only log errors
    } catch (error) {
      console.error('❌ Failed to disconnect WebSocket services:', error)
    }

    try {
      const token = localStorage.getItem('pulse_token')
      if (token) {
        // Logout from backend service
        // The backend will broadcast logout to all other devices via WebSocket
        await axios.post('/api/v1/auth/logout', {}, {
          headers: { 'Authorization': `Bearer ${token}` }
        })
      }
    } catch (error) {
      // Ignore logout errors
    }

    // Clear authentication data
    localStorage.clear()
    sessionStorage.clear()
    delete axios.defaults.headers.common['Authorization']

    // Broadcast logout to other tabs/windows on same origin (backup mechanism)
    // Note: Session WebSocket is the primary sync mechanism, but localStorage
    // events still work as a fallback for same-origin tabs
    localStorage.setItem('pulse_logout_event', Date.now().toString())
    localStorage.removeItem('pulse_logout_event')

    window.location.replace('/login')
  }

  // Refresh JWT token
  const refreshToken = async (): Promise<boolean> => {
    try {
      const currentToken = localStorage.getItem('pulse_token')
      if (!currentToken) {
        console.warn('No token to refresh')
        return false
      }

      const response = await axios.post('/api/v1/auth/refresh', {}, {
        headers: { 'Authorization': `Bearer ${currentToken}` }
      })

      if (response.data.success && response.data.token) {
        const newToken = response.data.token
        localStorage.setItem('pulse_token', newToken)
        axios.defaults.headers.common['Authorization'] = `Bearer ${newToken}`

        // Update WebSocket service with new token (keeps existing connections alive)
        // Note: Existing WebSocket connections remain active - only new connections use the new token
        try {
          await etlWebSocketService.updateToken(newToken)
          // Silently updated - no need to log on every refresh
        } catch (wsError) {
          console.error('❌ Failed to update WebSocket token:', wsError)
          // Don't fail the refresh if WebSocket update fails
        }

        return true
      }
    } catch (error: any) {
      console.error('❌ Failed to refresh token:', error)

      // Only logout on 401 - other errors might be temporary
      if (error?.response?.status === 401) {
        console.warn('⚠️ Token refresh returned 401, logging out')
        logout()
      } else {
        console.warn('⚠️ Token refresh failed with non-401 error, will retry on next interval')
      }
    }
    return false
  }

  const value: AuthContextType = {
    user,
    login,
    logout,
    isLoading,
    isAuthenticated: !!user,
    isAdmin: !!user && user.is_admin,
    updateAccessibilityPreference,
    refreshUserColors,
    refreshToken
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
