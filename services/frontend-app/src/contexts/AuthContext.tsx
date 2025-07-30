import axios from 'axios'
import { createContext, ReactNode, useContext, useEffect, useState } from 'react'

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

interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [colorSchemaLoaded, setColorSchemaLoaded] = useState(false)

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

  // Check for existing token on app start
  useEffect(() => {
    const token = localStorage.getItem('pulse_token')
    if (token) {
      // Set axios default header
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`

      // Validate token with backend
      validateToken()
    } else {
      setIsLoading(false)
    }
  }, [])

  const validateToken = async () => {
    try {
      // Make API call to validate token with backend
      const response = await axios.post('/api/v1/auth/validate')

      if (response.data.valid && response.data.user) {
        const { user } = response.data

        // Load color schema for existing session
        const colorSchemaData = await loadColorSchema()

        // Format user data to match frontend interface
        const formattedUser = {
          id: user.id.toString(),
          email: user.email,
          name: user.first_name && user.last_name
            ? `${user.first_name} ${user.last_name}`
            : user.first_name || user.last_name || user.email.split('@')[0],
          role: user.role,
          client_id: user.client_id,  // ✅ CRITICAL: Include client_id for multi-client isolation
          colorSchemaData: colorSchemaData || undefined
        }

        setUser(formattedUser)
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

        // Load color schema after successful authentication
        const colorSchemaData = await loadColorSchema()

        // Format user data to match frontend interface
        const formattedUser = {
          id: user.id.toString(),
          email: user.email,
          name: user.first_name && user.last_name
            ? `${user.first_name} ${user.last_name}`
            : user.first_name || user.last_name || user.email.split('@')[0],
          role: user.role,
          client_id: user.client_id,  // ✅ CRITICAL: Include client_id for multi-client isolation
          colorSchemaData: colorSchemaData || undefined
        }

        // Set user data
        setUser(formattedUser)

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
