import axios from 'axios'
import { createContext, ReactNode, useContext, useEffect, useState } from 'react'
import clientLogger from '../utils/clientLogger'
import { useAuth } from './AuthContext'

type Theme = 'light' | 'dark'
type ColorSchemaMode = 'default' | 'custom'

interface ColorSchema {
  color1: string
  color2: string
  color3: string
  color4: string
  color5: string
}

interface ThemeContextType {
  theme: Theme
  toggleTheme: () => void
  saveThemeMode: () => Promise<boolean>
  colorSchemaMode: ColorSchemaMode
  setColorSchemaMode: (mode: ColorSchemaMode) => void
  saveColorSchemaMode: (mode: ColorSchemaMode) => Promise<boolean>
  colorSchema: ColorSchema
  updateColorSchema: (colors: Partial<ColorSchema>) => void
  saveColorSchema: () => Promise<boolean>
  resetToDefault: () => void
}

const defaultColorSchema: ColorSchema = {
  color1: '#2862EB',  // Blue - Primary (updated and switched)
  color2: '#763DED',  // Purple - Secondary (updated)
  color3: '#059669',  // Emerald - Success
  color4: '#0EA5E9',  // Sky Blue - Info
  color5: '#F59E0B',  // Amber - Warning
}

// Note: Custom colors are now loaded from database via AuthContext
// No hardcoded custom colors needed

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

// API functions for color schema persistence



const saveColorSchemaToAPI = async (colors: ColorSchema): Promise<boolean> => {
  try {
    const response = await axios.post('/api/v1/admin/color-schema', colors)
    return response.data.success
  } catch (error) {
    clientLogger.error('Failed to save color schema to API', {
      type: 'api_error',
      error: error instanceof Error ? error.message : String(error)
    })
    return false
  }
}

const saveColorSchemaModeToAPI = async (mode: ColorSchemaMode): Promise<boolean> => {
  try {
    const response = await axios.post('/api/v1/admin/color-schema/mode', { mode })
    return response.data.success
  } catch (error) {
    console.error('Failed to save color schema mode to API:', error)
    return false
  }
}

// API functions for theme mode persistence (user-specific)
const loadThemeModeFromAPI = async (): Promise<Theme | null> => {
  try {
    const response = await axios.get('/api/v1/user/theme-mode')

    if (response.data.success) {
      return response.data.mode as Theme
    }
  } catch (error) {
    // Silently handle theme loading errors - not critical for app functionality
  }
  return null
}

const saveThemeModeToAPI = async (mode: Theme): Promise<boolean> => {
  try {
    const response = await axios.post('/api/v1/user/theme-mode', { mode })
    return response.data.success
  } catch (error) {
    console.error('Failed to save theme mode to API:', error)
    return false
  }
}

interface ThemeProviderProps {
  children: ReactNode
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  const { user, isLoading } = useAuth()
  const [theme, setTheme] = useState<Theme>('light')
  const [colorSchemaMode, setColorSchemaMode] = useState<ColorSchemaMode>('default')
  const [colorSchema, setColorSchema] = useState<ColorSchema>(defaultColorSchema)

  // Initialize theme and color schema from localStorage
  useEffect(() => {
    const savedTheme = localStorage.getItem('pulse_theme') as Theme
    const savedSchemaMode = localStorage.getItem('pulse_color_schema_mode') as ColorSchemaMode
    const savedColors = localStorage.getItem('pulse_colors')

    if (savedTheme) {
      setTheme(savedTheme)
    } else {
      setTheme('light')
    }

    if (savedSchemaMode) {
      setColorSchemaMode(savedSchemaMode)
    } else {
      setColorSchemaMode('default')
    }

    // Load colors from localStorage as fallback
    if (savedColors) {
      try {
        const parsedColors = JSON.parse(savedColors)
        setColorSchema({ ...defaultColorSchema, ...parsedColors })
      } catch (error) {
        console.error('Failed to parse saved colors:', error)
      }
    }
  }, [])

  // Load color schema from user profile when user changes (but not while loading)
  useEffect(() => {
    if (isLoading) {
      return
    }

    if (user && user.colorSchemaData) {
      setColorSchemaMode(user.colorSchemaData.mode)
      // Always store the custom colors from database, regardless of mode
      setColorSchema(user.colorSchemaData.colors)
    } else {
      setColorSchemaMode('default')
      // Keep default colors as fallback, but this should not happen in normal operation
      setColorSchema(defaultColorSchema)
    }
  }, [user, isLoading])

  // Load theme mode from API when user is loaded
  useEffect(() => {
    const loadThemeMode = async () => {
      if (isLoading || !user) {
        return
      }

      try {
        const savedTheme = await loadThemeModeFromAPI()
        if (savedTheme) {
          setTheme(savedTheme)
        }
      } catch (error) {
        console.error('Failed to load theme mode from API:', error)
      }
    }

    loadThemeMode()
  }, [user, isLoading])



  // Apply theme to document
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('pulse_theme', theme)
  }, [theme])

  // Apply color schema mode to document and update colors
  useEffect(() => {
    document.documentElement.setAttribute('data-color-schema', colorSchemaMode)
    localStorage.setItem('pulse_color_schema_mode', colorSchemaMode)

    // Note: Color schema values come from database via AuthContext
    // No need to override them here based on mode
  }, [colorSchemaMode])

  // Apply color schema to CSS custom properties
  useEffect(() => {
    const root = document.documentElement

    if (colorSchemaMode === 'custom') {
      // Apply custom colors via CSS custom properties
      root.style.setProperty('--color-1', colorSchema.color1)
      root.style.setProperty('--color-2', colorSchema.color2)
      root.style.setProperty('--color-3', colorSchema.color3)
      root.style.setProperty('--color-4', colorSchema.color4)
      root.style.setProperty('--color-5', colorSchema.color5)
      localStorage.setItem('pulse_colors', JSON.stringify(colorSchema))
    } else {
      // For default mode, remove custom properties to use CSS defaults
      root.style.removeProperty('--color-1')
      root.style.removeProperty('--color-2')
      root.style.removeProperty('--color-3')
      root.style.removeProperty('--color-4')
      root.style.removeProperty('--color-5')
    }
  }, [colorSchema, colorSchemaMode])

  const toggleTheme = async () => {
    const newTheme = theme === 'light' ? 'dark' : 'light'
    setTheme(newTheme)

    // Save to API
    try {
      await saveThemeModeToAPI(newTheme)
    } catch (error) {
      console.error('Failed to save theme mode:', error)
    }
  }

  const saveThemeMode = async (): Promise<boolean> => {
    try {
      const success = await saveThemeModeToAPI(theme)
      return success
    } catch (error) {
      console.error('Failed to save theme mode:', error)
      return false
    }
  }

  const updateColorSchema = (colors: Partial<ColorSchema>) => {
    setColorSchema(prev => ({ ...prev, ...colors }))
  }

  const saveColorSchemaMode = async (mode: ColorSchemaMode): Promise<boolean> => {
    const success = await saveColorSchemaModeToAPI(mode)
    if (success) {
      setColorSchemaMode(mode)
      localStorage.setItem('pulse_color_schema_mode', mode)
    }
    return success
  }

  const saveColorSchema = async (): Promise<boolean> => {
    const success = await saveColorSchemaToAPI(colorSchema)
    if (success) {
      // Also save to localStorage as backup
      localStorage.setItem('pulse_colors', JSON.stringify(colorSchema))
    }
    return success
  }

  const resetToDefault = () => {
    // Reset to the original database colors (handled by ColorSchemaPanel)
    // This function is mainly for UI consistency
  }

  const value: ThemeContextType = {
    theme,
    toggleTheme,
    saveThemeMode,
    colorSchemaMode,
    setColorSchemaMode,
    saveColorSchemaMode,
    colorSchema,
    updateColorSchema,
    saveColorSchema,
    resetToDefault
  }

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}
