import axios from 'axios'
import { createContext, ReactNode, useContext, useEffect, useState } from 'react'

interface User {
  id: string
  email: string
  name: string
  role: string
  is_admin: boolean
  tenant_id: number
  colorSchemaData?: any
}

interface CentralizedAuthContextType {
  user: User | null
  login: () => void
  logout: () => void
  isLoading: boolean
  isAuthenticated: boolean
  isAdmin: boolean
}

const CentralizedAuthContext = createContext<CentralizedAuthContextType | undefined>(undefined)

// Configure axios defaults
axios.defaults.baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001'

interface AuthProviderProps {
  children: ReactNode
}

export function CentralizedAuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const isAuthenticated = !!user
  const isAdmin = user?.is_admin || false

  // Configuration
  const AUTH_SERVICE_URL = import.meta.env.VITE_AUTH_SERVICE_URL || 'http://localhost:4000'
  const FRONTEND_CALLBACK_URI = `${window.location.origin}/auth/callback`
  const SERVICE_ID = 'frontend'

  const login = () => {
    // No redirect to auth service - frontend handles its own login
    // This will be handled by the login page component
    window.location.href = '/login'
  }

  const logout = async () => {
    try {
      // Call backend to logout from all services
      const token = localStorage.getItem('pulse_token')
      if (token) {
        try {
          await axios.post('/api/v1/auth/centralized/logout-all-services', {}, {
            headers: { 'Authorization': `Bearer ${token}` }
          })
        } catch (error) {
          console.warn('Failed to logout from all services:', error)
        }
      }
    } catch (error) {
      console.warn('Error during logout:', error)
    } finally {
      // Clear local storage and state
      localStorage.removeItem('pulse_token')
      localStorage.removeItem('auth_state')
      delete axios.defaults.headers.common['Authorization']
      setUser(null)

      // Redirect to centralized auth service logout
      window.location.href = `${AUTH_SERVICE_URL}/logout?redirect_uri=${window.location.origin}`
    }
  }

  const handleAuthCallback = async (code: string, state: string) => {
    try {
      setIsLoading(true)

      // Verify state parameter (CSRF protection)
      const storedState = localStorage.getItem('auth_state')
      if (!storedState || storedState !== state) {
        throw new Error('Invalid state parameter - possible CSRF attack')
      }

      // Exchange authorization code for access token
      const response = await axios.post('/api/v1/auth/centralized/exchange-code', {
        code,
        service_id: SERVICE_ID,
        redirect_uri: FRONTEND_CALLBACK_URI
      })

      const { access_token, user: userData } = response.data

      // Store token and set up axios
      localStorage.setItem('pulse_token', access_token)
      axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`

      // Format user data
      const formattedUser: User = {
        id: userData.id.toString(),
        email: userData.email,
        name: userData.first_name && userData.last_name
          ? `${userData.first_name} ${userData.last_name}`
          : userData.first_name || userData.last_name || userData.email.split('@')[0],
        role: userData.role,
        is_admin: userData.is_admin,
        tenant_id: userData.tenant_id
      }

      setUser(formattedUser)

      // Clean up
      localStorage.removeItem('auth_state')

      console.log('✅ Centralized authentication successful:', formattedUser.email)

    } catch (error) {
      console.error('❌ Auth callback failed:', error)
      localStorage.removeItem('pulse_token')
      localStorage.removeItem('auth_state')
      delete axios.defaults.headers.common['Authorization']
      setUser(null)
      throw error
    } finally {
      setIsLoading(false)
    }
  }

  const validateExistingToken = async () => {
    try {
      const token = localStorage.getItem('pulse_token')
      if (!token) {
        setIsLoading(false)
        return
      }

      // Set axios header
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`

      // Validate token with backend
      const response = await axios.post('/api/v1/auth/validate')

      if (response.data.valid && response.data.user) {
        const userData = response.data.user
        const formattedUser: User = {
          id: userData.id.toString(),
          email: userData.email,
          name: userData.first_name && userData.last_name
            ? `${userData.first_name} ${userData.last_name}`
            : userData.first_name || userData.last_name || userData.email.split('@')[0],
          role: userData.role,
          is_admin: userData.is_admin,
          tenant_id: userData.tenant_id
        }

        setUser(formattedUser)
        console.log('✅ Existing token validated:', formattedUser.email)
      } else {
        // Token invalid, clear it
        localStorage.removeItem('pulse_token')
        delete axios.defaults.headers.common['Authorization']
      }
    } catch (error) {
      console.warn('Token validation failed:', error)
      localStorage.removeItem('pulse_token')
      delete axios.defaults.headers.common['Authorization']
    } finally {
      setIsLoading(false)
    }
  }

  // Check for existing token on app start
  useEffect(() => {
    validateExistingToken()
  }, [])

  // Expose handleAuthCallback for the callback route
  useEffect(() => {
    (window as any).handleAuthCallback = handleAuthCallback
    return () => {
      delete (window as any).handleAuthCallback
    }
  }, [])

  const value: CentralizedAuthContextType = {
    user,
    login,
    logout,
    isLoading,
    isAuthenticated,
    isAdmin
  }

  return (
    <CentralizedAuthContext.Provider value={value}>
      {children}
    </CentralizedAuthContext.Provider>
  )
}

export function useCentralizedAuth() {
  const context = useContext(CentralizedAuthContext)
  if (context === undefined) {
    throw new Error('useCentralizedAuth must be used within a CentralizedAuthProvider')
  }
  return context
}

// Utility function
function generateRandomState(): string {
  return Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15)
}
