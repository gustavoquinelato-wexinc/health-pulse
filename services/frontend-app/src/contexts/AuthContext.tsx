import axios from 'axios'
import { createContext, ReactNode, useContext, useEffect, useState } from 'react'
import notificationService from '../services/notificationService'
import websocketService from '../services/websocketService'
import clientLogger from '../utils/clientLogger'

// Axios configuration is handled below - no duplicate configuration needed

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
  // Unified colors structure for ThemeContext
  unified_colors?: {
    light: ColorSchema
    dark: ColorSchema
  }
  // Enhanced data from new color system
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
  client_id: number  // ✅ CRITICAL: Add client_id for multi-client isolation
  use_accessible_colors?: boolean  // User accessibility preference
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
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

// Configure axios defaults - Use direct backend URL since CORS is properly configured
axios.defaults.baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001'
// Note: withCredentials is set per-request basis to avoid CORS issues

// Global axios response interceptor for handling authentication errors
let isInterceptorSetup = false

interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [sessionCheckInterval, setSessionCheckInterval] = useState<number | null>(null)

  // Load color schema from API (client-specific, no global caching)
  const loadColorSchema = async (): Promise<ColorSchemaData | null> => {
    try {
      const response = await axios.get('/api/v1/admin/color-schema/unified')

      if (response.data.success && response.data.color_data) {
        // Convert unified API response to ColorSchemaData format
        const colorData = response.data.color_data
        const lightRegular = colorData.find((c: any) => c.theme_mode === 'light' && c.accessibility_level === 'regular')
        const darkRegular = colorData.find((c: any) => c.theme_mode === 'dark' && c.accessibility_level === 'regular')

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
            mode: response.data.color_schema_mode,
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
    try {
      const response = await axios.get('/api/v1/user/colors')

      if (response.data.success) {
        const userColors = response.data.colors

        // Transform user colors to ColorSchemaData format
        return {
          mode: userColors.resolved_mode || userColors.color_schema_mode || 'custom',
          colors: {
            color1: userColors.color1,
            color2: userColors.color2,
            color3: userColors.color3,
            color4: userColors.color4,
            color5: userColors.color5
          },
          on_colors: {
            color1: userColors.on_color1,
            color2: userColors.on_color2,
            color3: userColors.on_color3,
            color4: userColors.on_color4,
            color5: userColors.on_color5
          },
          on_gradients: {
            '1-2': userColors.on_gradient_1_2,
            '2-3': userColors.on_gradient_2_3,
            '3-4': userColors.on_gradient_3_4,
            '4-5': userColors.on_gradient_4_5,
            '5-1': userColors.on_gradient_5_1
          },
          enhanced_data: {
            font_contrast_threshold: userColors.font_contrast_threshold,
            colors_defined_in_mode: userColors.colors_defined_in_mode,
            adaptive_colors: {
              color1: userColors.adaptive_color1,
              color2: userColors.adaptive_color2,
              color3: userColors.adaptive_color3,
              color4: userColors.adaptive_color4,
              color5: userColors.adaptive_color5
            },
            cache_info: {
              cached: true,
              source: 'user_specific_resolution'
            }
          }
        } as ColorSchemaData
      }
    } catch (error: any) {
      console.error('AuthContext: Failed to load user colors:', error)
    }
    return null
  }

  // Start periodic session validation
  const startSessionValidation = () => {
    // Clear any existing interval
    if (sessionCheckInterval) {
      clearInterval(sessionCheckInterval)
    }

    // Check session every 10 minutes (less aggressive to prevent false logouts)
    const interval = setInterval(async () => {
      if (user) {
        console.log('AuthContext: Performing periodic session validation...')
        const token = localStorage.getItem('pulse_token')
        if (token) {
          try {
            // Explicitly set Authorization header for validation
            const response = await axios.post('/api/v1/auth/validate', {}, {
              headers: {
                'Authorization': `Bearer ${token}`
              }
            })
            if (!response.data.success) {
              console.warn('AuthContext: Session expired during periodic check')
              logout()
            } else {
              console.log('AuthContext: Session validation successful')
            }
          } catch (error: any) {
            console.warn('AuthContext: Session validation failed during periodic check:', error)
            // Don't logout on network errors - only on 401
            if (error.response?.status === 401) {
              logout()
            }
          }
        } else {
          console.warn('AuthContext: No token found during periodic check')
          logout()
        }
      }
    }, 10 * 60 * 1000) // 10 minutes

    setSessionCheckInterval(interval)
    // Session validation started
  }

  // Setup axios interceptor for automatic 401 handling
  const setupAxiosInterceptor = () => {
    if (isInterceptorSetup) return

    axios.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          console.warn('AuthContext: 401 Unauthorized - logging out user')
          logout()
        }
        return Promise.reject(error)
      }
    )

    isInterceptorSetup = true
    // Axios interceptor configured
  }

  // Stop periodic session validation
  const stopSessionValidation = () => {
    if (sessionCheckInterval) {
      clearInterval(sessionCheckInterval)
      setSessionCheckInterval(null)
    }
  }



  // Check for existing token on app start
  useEffect(() => {
    // First check for token in URL parameters (from ETL service)
    const urlParams = new URLSearchParams(window.location.search)
    const urlToken = urlParams.get('token')

    if (urlToken) {
      // Store token from URL parameter
      localStorage.setItem('pulse_token', urlToken)
      // Clean up URL by removing token parameter
      const newUrl = new URL(window.location.href)
      newUrl.searchParams.delete('token')
      window.history.replaceState({}, document.title, newUrl.toString())

      // Set axios default header
      axios.defaults.headers.common['Authorization'] = `Bearer ${urlToken}`

      // Validate the token from URL
      validateToken()
      return
    }

    // Check localStorage for existing token
    const token = localStorage.getItem('pulse_token')
    if (token) {
      // Set axios default header
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`

      // Validate token with backend
      validateToken()
    } else {
      // No localStorage token, but check if there's an existing session in Backend Service
      checkExistingSession()
    }

    // Cross-service authentication is handled via postMessage and cookies
  }, [])

  // Cleanup effect to stop session validation on unmount
  useEffect(() => {
    return () => {
      stopSessionValidation()
    }
  }, [])

  // TEMPORARILY DISABLED: Check session when window regains focus
  // This was causing aggressive logouts - will re-enable after debugging
  /*
  useEffect(() => {
    const handleWindowFocus = async () => {
      if (user) {
        console.log('AuthContext: Window focused - checking session validity...')
        const token = localStorage.getItem('pulse_token')
        if (token) {
          try {
            const response = await axios.post('/auth/validate', {}, {
              headers: { 'Authorization': `Bearer ${token}` }
            })
            if (!response.data.success) {
              console.warn('AuthContext: Session invalid on window focus - logging out')
              logout()
            }
          } catch (error) {
            console.warn('AuthContext: Session check failed on window focus:', error)
            if (error.response?.status === 401) {
              logout()
            }
          }
        } else {
          console.warn('AuthContext: No token found on window focus - logging out')
          logout()
        }
      }
    }
 
    window.addEventListener('focus', handleWindowFocus)
    return () => {
      window.removeEventListener('focus', handleWindowFocus)
    }
  }, [user])
  */



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

        // Try to get token from cookies (set by ETL service)
        const cookieToken = document.cookie
          .split('; ')
          .find(row => row.startsWith('pulse_token='))
          ?.split('=')[1]

        if (cookieToken) {
          localStorage.setItem('pulse_token', cookieToken)
          axios.defaults.headers.common['Authorization'] = `Bearer ${cookieToken}`
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
          client_id: user.client_id,
          colorSchemaData: undefined
        }

        setUser(formattedUser)

        // Update client logger context with new user info
        clientLogger.updateClientContext()

        // Load color schema - prefer user-specific colors if available
        const loadColors = async () => {
          try {
            // Try user-specific colors first (includes accessibility preferences)
            let colorSchemaData = await loadUserColors()

            // Fallback to unified admin color schema if user colors not available
            if (!colorSchemaData) {
              colorSchemaData = await loadColorSchema()
            }

            if (colorSchemaData) {
              setUser(prev => prev ? { ...prev, colorSchemaData } : prev)
              console.log('✅ Colors loaded:', colorSchemaData.enhanced_data?.cache_info?.source || 'legacy')
            } else {
              // Final fallback: Set default color schema if all APIs fail
              const defaultColors = {
                color1: '#2862EB',
                color2: '#763DED',
                color3: '#059669',
                color4: '#0EA5E9',
                color5: '#F59E0B'
              }
              const fallbackColorSchema: ColorSchemaData = {
                mode: 'default',
                colors: defaultColors,
                unified_colors: {
                  light: defaultColors,
                  dark: defaultColors
                }
              }
              setUser(prev => prev ? { ...prev, colorSchemaData: fallbackColorSchema } : prev)
              console.warn('⚠️ Using fallback colors - API unavailable')
            }
          } catch (error) {
            console.error('❌ Error loading colors:', error)
            // Set fallback colors even on error
            const defaultColors = {
              color1: '#2862EB',
              color2: '#763DED',
              color3: '#059669',
              color4: '#0EA5E9',
              color5: '#F59E0B'
            }
            const fallbackColorSchema: ColorSchemaData = {
              mode: 'default',
              colors: defaultColors,
              unified_colors: {
                light: defaultColors,
                dark: defaultColors
              }
            }
            setUser(prev => prev ? { ...prev, colorSchemaData: fallbackColorSchema } : prev)
          }
        }

        loadColors()
      }
    } catch (error) {
      // No existing session found, this is normal
      console.debug('No existing session found:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const validateToken = async () => {
    try {
      // Make API call to validate token with backend
      const response = await axios.post('/api/v1/auth/validate')

      if (response.data.valid && response.data.user) {
        const { user } = response.data

        // Load theme from database during token validation (for cross-service redirects)
        let userThemeMode = localStorage.getItem('pulse_theme') || 'light'
        try {
          const themeResponse = await axios.get('/api/v1/user/theme-mode')
          if (themeResponse.data.success && themeResponse.data.mode !== userThemeMode) {
            userThemeMode = themeResponse.data.mode


            // Update all storage layers
            localStorage.setItem('pulse_theme', userThemeMode)
            document.documentElement.setAttribute('data-theme', userThemeMode)
              ; (window as any).__INITIAL_THEME__ = userThemeMode
          }
        } catch (error) {
          console.warn('Failed to sync theme during validation:', error)
        }

        // Format user data to match frontend interface
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
          client_id: user.client_id,  // ✅ CRITICAL: Include client_id for multi-client isolation
          colorSchemaData: undefined  // Will be loaded separately
        }

        setUser(formattedUser)

        // Update client logger context with new user info
        clientLogger.updateClientContext()

        // Setup axios interceptor and start periodic session validation
        setupAxiosInterceptor()
        startSessionValidation()

        // Load color schema after user is set (non-blocking)
        loadColorSchema().then(colorSchemaData => {
          if (colorSchemaData) {
            setUser(prev => prev ? { ...prev, colorSchemaData } : prev)
          } else {
            // Fallback: Set default color schema if API fails
            const defaultColors = {
              color1: '#2862EB',  // Default Blue
              color2: '#763DED',  // Default Purple
              color3: '#059669',  // Default Green
              color4: '#0EA5E9',  // Default Light Blue
              color5: '#F59E0B'   // Default Orange
            }
            const fallbackColorSchema: ColorSchemaData = {
              mode: 'default',
              colors: defaultColors,
              unified_colors: {
                light: defaultColors,
                dark: defaultColors
              }
            }
            setUser(prev => prev ? { ...prev, colorSchemaData: fallbackColorSchema } : prev)
          }
        }).catch(error => {
          // Set fallback colors even on error
          const defaultColors = {
            color1: '#2862EB',
            color2: '#763DED',
            color3: '#059669',
            color4: '#0EA5E9',
            color5: '#F59E0B'
          }
          const fallbackColorSchema: ColorSchemaData = {
            mode: 'default',
            colors: defaultColors,
            unified_colors: {
              light: defaultColors,
              dark: defaultColors
            }
          }
          setUser(prev => prev ? { ...prev, colorSchemaData: fallbackColorSchema } : prev)
        })
      } else {
        // Invalid response format, clear token
        localStorage.removeItem('pulse_token')
        delete axios.defaults.headers.common['Authorization']
      }
    } catch (error) {
      // Token is invalid or expired, clear all authentication data
      clearAllAuthenticationData()
    } finally {
      setIsLoading(false)
    }
  }

  const login = async (email: string, password: string): Promise<boolean> => {
    try {
      setIsLoading(true)

      // Make real authentication request to backend service
      const response = await axios.post('/auth/login', {
        email: email.toLowerCase().trim(),
        password: password
      })

      if (response.data.success && response.data.token) {
        const { token, user } = response.data

        // Store token in localStorage
        localStorage.setItem('pulse_token', token)

        // Set axios default header for future requests
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
              ; (window as any).__INITIAL_THEME__ = userThemeMode
          }
        } catch (error) {
          console.warn('Failed to load theme from database, using default:', error)
        }

        // Load color schema before setting user to avoid flash
        // Try user-specific colors first, then fallback to admin colors
        let colorSchemaData = await loadUserColors()
        if (!colorSchemaData) {
          colorSchemaData = await loadColorSchema()
        }
        if (!colorSchemaData) {
          const defaultColors = {
            color1: '#2862EB',  // Default Blue
            color2: '#763DED',  // Default Purple
            color3: '#059669',  // Default Green
            color4: '#0EA5E9',  // Default Light Blue
            color5: '#F59E0B'   // Default Orange
          }
          colorSchemaData = {
            mode: 'default',
            colors: defaultColors,
            unified_colors: {
              light: defaultColors,
              dark: defaultColors
            }
          }
        }

        // Format user data to match frontend interface (with color schema)
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
          client_id: user.client_id,  // ✅ CRITICAL: Include client_id for multi-client isolation
          colorSchemaData
        }

        // Set user data (already contains color schema)
        setUser(formattedUser)

        // Update client logger context with new user info
        clientLogger.updateClientContext()

        // Setup axios interceptor and start periodic session validation
        setupAxiosInterceptor()
        startSessionValidation()

        // Cross-service cookie setup is now handled by Backend Service
        // No direct Frontend → ETL communication needed

        // Set up cross-service cookie for ETL service
        setupCrossServiceCookie(token)

        return true
      } else {
        return false
      }
    } catch (error) {
      clientLogger.error('Login failed', {
        type: 'authentication_error',
        error: error instanceof Error ? error.message : String(error)
      })
      // Clear any stored data on error
      localStorage.removeItem('pulse_token')
      delete axios.defaults.headers.common['Authorization']
      return false
    } finally {
      setIsLoading(false)
    }
  }

  const setupCrossServiceCookie = (token: string) => {
    try {
      // Set cookie for cross-service authentication with ETL service
      // For localhost development, we need to set cookies for each specific port
      // since .localhost domain doesn't work reliably in all browsers

      // Set cookie for current domain (no domain specified = current host only)
      document.cookie = `pulse_token=${token}; path=/; max-age=86400; SameSite=lax`

      // Also try to set with .localhost domain for browsers that support it
      try {
        document.cookie = `pulse_token=${token}; path=/; domain=.localhost; max-age=86400; SameSite=lax`
      } catch (domainError) {
        // Ignore domain-specific errors - some browsers don't support .localhost
      }

      // Log removed - cross-service cookie setup is routine operation
    } catch (error) {
      clientLogger.error('Failed to set cross-service cookie', {
        type: 'cross_service_cookie_error',
        error: error instanceof Error ? error.message : String(error)
      })
    }
  }

  const clearAllAuthenticationData = () => {
    try {
      // Clear localStorage completely
      localStorage.clear()

      // Clear sessionStorage
      sessionStorage.clear()

      // Clear all cookies (with error handling)
      try {
        document.cookie.split(";").forEach(cookie => {
          const eqPos = cookie.indexOf("=")
          const name = eqPos > -1 ? cookie.substring(0, eqPos).trim() : cookie.trim()
          if (name) {
            // Clear for current domain
            document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/`
            // Clear for parent domain
            document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/;domain=localhost`
            // Clear for all subdomains
            document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/;domain=.localhost`
          }
        })
      } catch (error) {
        // Silently handle cookie clearing errors
      }

      // Clear axios headers
      if (axios.defaults.headers.common) {
        delete axios.defaults.headers.common['Authorization']
      }

      // Authentication data cleared successfully
    } catch (error) {
      // Silently handle any authentication data clearing errors
    }
  }

  const logout = async () => {
    // Immediately stop session validation to prevent any interference
    stopSessionValidation()

    // Clear state first to prevent any React updates during cleanup
    setUser(null)

    // Update client logger context to reflect logout
    clientLogger.updateClientContext()

    try {
      // Try to invalidate session on the backend (await to ensure DB is updated before redirect)
      let token = localStorage.getItem('pulse_token')
      if (!token) {
        // Fallback to cookie if needed
        token = document.cookie.split('; ').find(r => r.startsWith('pulse_token='))?.split('=')[1] || ''
      }
      if (token) {
        try {
          await axios.post('/api/v1/auth/logout', {}, {
            headers: { 'Authorization': `Bearer ${token}` }
          })
        } catch (e) {
          // Ignore backend failures, continue cleanup
        }

        // ETL service logout (best-effort, do not block)
        const etlServiceUrl = import.meta.env.VITE_ETL_SERVICE_URL || 'http://localhost:8000'
        fetch(`${etlServiceUrl}/api/logout`, {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' }
        }).catch(() => { })
      }
    } catch (error) {
      // Silently handle any logout API errors
    }

    // Clear authentication data immediately
    try {
      clearAllAuthenticationData()
    } catch (error) {
      // Silently handle any auth data clearing errors
    }

    // Clear browser cache asynchronously (don't block redirect)
    if ('caches' in window) {
      caches.keys().then(names => {
        names.forEach(name => {
          if (name.includes('auth') || name.includes('api')) {
            caches.delete(name).catch(() => { })
          }
        })
      }).catch(() => { })
    }

    // Unregister service workers asynchronously (don't block redirect)
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.getRegistrations().then(registrations => {
        registrations.forEach(registration => {
          registration.unregister().catch(() => { })
        })
      }).catch(() => { })
    }

    // Redirect immediately to prevent any React state update issues
    window.location.replace('/login')
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

        console.log('✅ Accessibility preference updated:', useAccessibleColors)
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

  const value: AuthContextType = {
    user,
    login,
    logout,
    isLoading,
    isAuthenticated: !!user,
    isAdmin: !!user && user.is_admin,
    updateAccessibilityPreference,
    refreshUserColors
  }



  // Listen for cross-service authentication messages
  useEffect(() => {
    const handleCrossServiceAuth = async (event: MessageEvent) => {
      // Only accept messages from trusted origins
      const trustedOrigins = ['http://localhost:8000']; // ETL service
      if (!trustedOrigins.includes(event.origin)) {
        return;
      }

      if (event.data.type === 'AUTH_SUCCESS' && event.data.token) {
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
              ; (window as any).__INITIAL_THEME__ = userThemeMode
          }
        } catch (error) {
          console.warn('Failed to load theme during cross-service auth:', error)
        }

        // Set user data if provided
        if (event.data.user) {
          setUser(event.data.user);
          setIsLoading(false);
        } else {
          // Validate the token to get user data
          validateToken();
        }
      }
    };

    window.addEventListener('message', handleCrossServiceAuth);
    return () => {
      window.removeEventListener('message', handleCrossServiceAuth);
    };
  }, []);

  // Set up WebSocket for real-time color updates
  useEffect(() => {
    if (!user) return



    const unsubscribe = websocketService.onColorUpdate(async (colors) => {
      console.log('🎨 Received real-time color update:', colors)

      try {
        // Refresh user colors to get the latest data
        await refreshUserColors()


        // Show notification to user
        notificationService.colorUpdate('Your color scheme has been updated by an administrator')
      } catch (error) {
        console.error('❌ Failed to refresh colors from WebSocket update:', error)
        notificationService.error('Color Update Failed', 'Failed to apply real-time color changes')
      }
    })

    return unsubscribe
  }, [user])

  // Expose clear function globally for debugging
  useEffect(() => {
    (window as any).clearAuthData = clearAllAuthenticationData;
    return () => {
      delete (window as any).clearAuthData;
    };
  }, []);

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
