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
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001'
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
      validateToken(token)
    } else {
      setIsLoading(false)
    }
  }, [])

  const validateToken = async (token: string) => {
    try {
      const response = await axios.get('/api/v1/auth/validate')
      if (response.data.valid && response.data.user) {
        setUser(response.data.user)
      } else {
        // Invalid token, clear it
        localStorage.removeItem('pulse_token')
        delete axios.defaults.headers.common['Authorization']
      }
    } catch (error) {
      console.error('Token validation failed:', error)
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
        email,
        password
      })

      if (response.data.success && response.data.token) {
        const { token, user: userData } = response.data

        // Store token
        localStorage.setItem('pulse_token', token)

        // Set axios default header
        axios.defaults.headers.common['Authorization'] = `Bearer ${token}`

        // Set user data
        setUser(userData)

        return true
      }

      return false
    } catch (error) {
      console.error('Login failed:', error)
      return false
    } finally {
      setIsLoading(false)
    }
  }

  const logout = () => {
    localStorage.removeItem('pulse_token')
    delete axios.defaults.headers.common['Authorization']
    setUser(null)
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
