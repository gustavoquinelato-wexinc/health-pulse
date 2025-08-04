import axios from 'axios'
import { createContext, ReactNode, useContext, useEffect, useState } from 'react'
import clientLogger from '../utils/clientLogger'

// Configure axios defaults - Force Backend Service URL in development
if (import.meta.env.DEV) {
  axios.defaults.baseURL = 'http://localhost:3001'
} else {
  axios.defaults.baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001'
}

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
}

interface User {
  id: string
  email: string
  role: string
  name?: string
  client_id: number  // ✅ CRITICAL: Add client_id for multi-client isolation
  colorSchemaData?: ColorSchemaData
}

interface AuthContextType {
  user: User | null
  login: (email: string, password: string) => Promise<boolean>
  logout: () => void
  isLoading: boolean
  isAuthenticated: boolean
  isAdmin: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

// Configure axios defaults
// In development, use relative URLs so Vite proxy can handle routing
// In production, use the full API URL
const API_BASE_URL = import.meta.env.DEV ? '' : (import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001')
axios.defaults.baseURL = API_BASE_URL
axios.defaults.withCredentials = true  // Include cookies in all requests

// Global axios response interceptor for handling authentication errors
let isInterceptorSetup = false

interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [colorSchemaLoaded, setColorSchemaLoaded] = useState(false)
  const [sessionCheckInterval, setSessionCheckInterval] = useState<NodeJS.Timeout | null>(null)

  // Load color schema from API (with caching)
  const loadColorSchema = async (): Promise<ColorSchemaData | null> => {
    if (colorSchemaLoaded) {
      console.log('AuthContext: Color schema already loaded, skipping...')
      return null
    }

    try {
      const response = await axios.get('/api/v1/admin/color-schema')
      if (response.data.success) {
        setColorSchemaLoaded(true)
        return {
          mode: response.data.mode,
          colors: response.data.colors
        }
      }
    } catch (error) {
      console.error('AuthContext: Failed to load color schema:', error)
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
            const response = await axios.post('/auth/validate', {}, {
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
          } catch (error) {
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
      console.log('AuthContext: Stopped periodic session validation')
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
      const response = await axios.post('/auth/validate', {}, {
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
          role: user.role,
          client_id: user.client_id,
          colorSchemaData: undefined
        }

        setUser(formattedUser)

        // Load color schema
        loadColorSchema().catch(error => {
          console.warn('Failed to load color schema during session check:', error)
        })
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
      const response = await axios.post('/auth/validate')

      if (response.data.valid && response.data.user) {
        const { user } = response.data

        // Format user data to match frontend interface
        const formattedUser = {
          id: user.id.toString(),
          email: user.email,
          name: user.first_name && user.last_name
            ? `${user.first_name} ${user.last_name}`
            : user.first_name || user.last_name || user.email.split('@')[0],
          role: user.role,
          client_id: user.client_id,  // ✅ CRITICAL: Include client_id for multi-client isolation
          colorSchemaData: undefined  // Will be loaded separately
        }

        setUser(formattedUser)

        // Setup axios interceptor and start periodic session validation
        setupAxiosInterceptor()
        startSessionValidation()

        // Load color schema after user is set (non-blocking)
        loadColorSchema().then(colorSchemaData => {
          if (colorSchemaData) {
            setUser(prev => prev ? { ...prev, colorSchemaData } : prev)
          }
        }).catch(error => {
          console.warn('Failed to load color schema during validation:', error)
        })
      } else {
        // Invalid response format, clear token
        localStorage.removeItem('pulse_token')
        delete axios.defaults.headers.common['Authorization']
      }
    } catch (error) {
      // Token is invalid or expired, clear it (this is normal when not logged in)
      localStorage.removeItem('pulse_token')
      delete axios.defaults.headers.common['Authorization']
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

        // Format user data to match frontend interface
        const formattedUser = {
          id: user.id.toString(),
          email: user.email,
          name: user.first_name && user.last_name
            ? `${user.first_name} ${user.last_name}`
            : user.first_name || user.last_name || user.email.split('@')[0],
          role: user.role,
          client_id: user.client_id,  // ✅ CRITICAL: Include client_id for multi-client isolation
          colorSchemaData: undefined  // Will be loaded separately after login
        }

        // Set user data first
        setUser(formattedUser)

        // Setup axios interceptor and start periodic session validation
        setupAxiosInterceptor()
        startSessionValidation()

        // Cross-service cookie setup is now handled by Backend Service
        // No direct Frontend → ETL communication needed

        // Load color schema after user is set (non-blocking)
        loadColorSchema().then(colorSchemaData => {
          if (colorSchemaData) {
            setUser(prev => prev ? { ...prev, colorSchemaData } : prev)
          }
        }).catch(error => {
          console.warn('Failed to load color schema after login:', error)
        })

        return true
      } else {
        console.error('Login failed: Invalid response format')
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

  const logout = async () => {
    try {
      // Try to invalidate session on the backend
      const token = localStorage.getItem('pulse_token')
      if (token) {
        try {
          await axios.post('/auth/logout')
          console.log('Session invalidated on backend')
        } catch (error) {
          console.warn('Failed to invalidate session on backend:', error)
          // Continue with local logout even if backend call fails
        }
      }
    } catch (error) {
      console.warn('Error during logout:', error)
    } finally {
      // Stop periodic session validation
      stopSessionValidation()

      // Always clear local storage and state
      localStorage.removeItem('pulse_token')
      delete axios.defaults.headers.common['Authorization']
      setUser(null)
      setColorSchemaLoaded(false) // Reset color schema cache
    }
  }

  const value: AuthContextType = {
    user,
    login,
    logout,
    isLoading,
    isAuthenticated: !!user,
    isAdmin: !!user && user.role === 'admin'
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
