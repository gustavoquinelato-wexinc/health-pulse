import axios from 'axios'
import { createContext, ReactNode, useContext, useEffect, useState } from 'react'
import { colorDataService, type ColorData } from '../services/colorDataService'
import { getColorSchemaMode } from '../utils/colorSchemaService'

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

        // Get current theme (will be used by ThemeContext)
        const currentTheme = localStorage.getItem('pulse_theme') || 'light'

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

  // Check for existing token on app start
  useEffect(() => {
    const token = localStorage.getItem('pulse_token')
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`
      validateToken()
    } else {
      setIsLoading(false)
    }
  }, [])

  const validateToken = async () => {
    try {
      const response = await axios.post('/api/v1/auth/validate')

      if (response.data.valid && response.data.user) {
        const { user } = response.data

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

        // Load color schema after user is set
        loadColorSchema().then(colorSchemaData => {
          if (colorSchemaData) {
            setUser(prev => prev ? { ...prev, colorSchemaData } : prev)
          }
        })
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
          colorSchemaData
        }

        setUser(formattedUser)
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

  const logout = async () => {
    setUser(null)

    try {
      const token = localStorage.getItem('pulse_token')
      if (token) {
        await axios.post('/api/v1/auth/logout', {}, {
          headers: { 'Authorization': `Bearer ${token}` }
        })
      }
    } catch (error) {
      // Ignore logout errors
    }

    localStorage.removeItem('pulse_token')
    delete axios.defaults.headers.common['Authorization']
    window.location.replace('/login')
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
