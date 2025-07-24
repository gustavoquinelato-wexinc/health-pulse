import axios from 'axios'
import { createContext, ReactNode, useContext, useEffect, useState } from 'react'

interface User {
  id: string
  email: string
  role: string
  name?: string
}

interface AuthContextType {
  user: User | null
  login: (email: string, password: string) => Promise<boolean>
  logout: () => void
  isLoading: boolean
  isAuthenticated: boolean
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
      const response = await axios.get('/api/v1/auth/validate')

      if (response.data.valid && response.data.user) {
        const { user } = response.data

        // Format user data to match frontend interface
        const formattedUser = {
          id: user.id.toString(),
          email: user.email,
          name: user.first_name && user.last_name
            ? `${user.first_name} ${user.last_name}`
            : user.first_name || user.last_name || user.email.split('@')[0],
          role: user.role
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

        // Format user data to match frontend interface
        const formattedUser = {
          id: user.id.toString(),
          email: user.email,
          name: user.first_name && user.last_name
            ? `${user.first_name} ${user.last_name}`
            : user.first_name || user.last_name || user.email.split('@')[0],
          role: user.role
        }

        // Set user data
        setUser(formattedUser)

        return true
      } else {
        console.error('Login failed: Invalid response format')
        return false
      }
    } catch (error) {
      console.error('Login failed:', error)
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
    }
  }

  const value: AuthContextType = {
    user,
    login,
    logout,
    isLoading,
    isAuthenticated: !!user
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
