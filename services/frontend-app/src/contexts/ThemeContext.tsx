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
    // Backend expects { colors: { color1..5 } } as body
    const response = await axios.post('/api/v1/admin/color-schema', { colors })
    // Newer backend returns { message: ... } without a success flag; treat any 2xx as success
    return response.status >= 200 && response.status < 300
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
  const [theme, setTheme] = useState<Theme>(() => (localStorage.getItem('pulse_theme') as Theme) || 'light')
  const [colorSchemaMode, setColorSchemaMode] = useState<ColorSchemaMode>(() => (localStorage.getItem('pulse_color_schema_mode') as ColorSchemaMode) || 'default')
  const [colorSchema, setColorSchema] = useState<ColorSchema>(() => {
    const savedColors = localStorage.getItem('pulse_colors')
    if (savedColors) {
      try {
        const parsedColors = JSON.parse(savedColors)
        return { ...defaultColorSchema, ...parsedColors }
      } catch (error) {
        console.error('Failed to parse saved colors:', error)
      }
    }
    return defaultColorSchema
  })

  // Load color schema from user profile when it's actually available to avoid flash
  useEffect(() => {
    if (isLoading) return
    if (!user || !user.colorSchemaData) return

    // Apply mode
    setColorSchemaMode(user.colorSchemaData.mode)

    // Prefer explicit default/custom sets for UI components
    const anyData: any = user.colorSchemaData as any
    const chosen = (user.colorSchemaData.mode === 'custom' && anyData.custom_colors)
      ? anyData.custom_colors
      : (user.colorSchemaData.mode === 'default' && anyData.default_colors)
        ? anyData.default_colors
        : user.colorSchemaData.colors

    setColorSchema(chosen)
  }, [user?.colorSchemaData, isLoading])

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

  // Apply color schema to CSS custom properties (colors and on-colors)
  useEffect(() => {
    const root = document.documentElement

    // Always set active colors explicitly to avoid relying on CSS file defaults
    root.style.setProperty('--color-1', colorSchema.color1)
    root.style.setProperty('--color-2', colorSchema.color2)
    root.style.setProperty('--color-3', colorSchema.color3)
    root.style.setProperty('--color-4', colorSchema.color4)
    root.style.setProperty('--color-5', colorSchema.color5)

    // Compute on-colors from the active palette so UI updates immediately after changes
    const pickOn = (hex: string) => {
      try {
        const h = hex.replace('#', '')
        const r = parseInt(h.slice(0, 2), 16) / 255
        const g = parseInt(h.slice(2, 4), 16) / 255
        const b = parseInt(h.slice(4, 6), 16) / 255
        const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4))
        const L = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
        const contrast = (Lbg: number, Lfg: number) => (Math.max(Lbg, Lfg) + 0.05) / (Math.min(Lbg, Lfg) + 0.05)
        const cBlack = contrast(L, 0)
        const cWhite = contrast(L, 1)
        return cWhite >= cBlack ? '#FFFFFF' : '#000000'
      } catch {
        return '#000000'
      }
    }

    const on1 = pickOn(colorSchema.color1)
    const on2 = pickOn(colorSchema.color2)
    const on3 = pickOn(colorSchema.color3)
    const on4 = pickOn(colorSchema.color4)
    const on5 = pickOn(colorSchema.color5)

    // Solid on-colors (always resolved from current colors)
    root.style.setProperty('--on-color-1', on1)
    root.style.setProperty('--on-color-2', on2)
    root.style.setProperty('--on-color-3', on3)
    root.style.setProperty('--on-color-4', on4)
    root.style.setProperty('--on-color-5', on5)

    // Gradient on-colors (pairs 1-2, 2-3, 3-4, 4-5)
    const pairOn = (a: string, b: string) => {
      const onA = pickOn(a), onB = pickOn(b)
      // If both suggest the same color, use it; else prefer white
      return onA === onB ? onA : '#FFFFFF'
    }

    root.style.setProperty('--on-gradient-1-2', pairOn(colorSchema.color1, colorSchema.color2))
    root.style.setProperty('--on-gradient-2-3', pairOn(colorSchema.color2, colorSchema.color3))
    root.style.setProperty('--on-gradient-3-4', pairOn(colorSchema.color3, colorSchema.color4))
    root.style.setProperty('--on-gradient-4-5', pairOn(colorSchema.color4, colorSchema.color5))

    // Persist last used colors for quick boot
    localStorage.setItem('pulse_colors', JSON.stringify(colorSchema))
  }, [colorSchema, colorSchemaMode, user?.colorSchemaData])

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
      // Refresh from server to apply correct colors for the selected mode
      try {
        const res = await axios.get('/api/v1/admin/color-schema')
        if (res.data?.success) {
          setColorSchemaMode(res.data.mode)
          setColorSchema(res.data.colors)
          localStorage.setItem('pulse_colors', JSON.stringify(res.data.colors))
        }
      } catch (e) {
        console.warn('Failed to refresh color schema after mode change', e)
      }
    }
    return success
  }

  const saveColorSchema = async (): Promise<boolean> => {
    const success = await saveColorSchemaToAPI(colorSchema)
    if (success) {
      // Also save to localStorage as backup
      localStorage.setItem('pulse_colors', JSON.stringify(colorSchema))
      // Refresh from server to apply recomputed on-colors and any server-side validation
      try {
        const res = await axios.get('/api/v1/admin/color-schema')
        if (res.data?.success) {
          setColorSchemaMode(res.data.mode)
          setColorSchema(res.data.colors)
          localStorage.setItem('pulse_colors', JSON.stringify(res.data.colors))
        }
      } catch (e) {
        console.warn('Failed to refresh color schema after save', e)
      }
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
