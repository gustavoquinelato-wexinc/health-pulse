import axios from 'axios'
import { createContext, ReactNode, useContext, useEffect, useState } from 'react'
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

interface UnifiedColorData {
  light: ColorSchema
  dark: ColorSchema
  on_colors: {
    light: ColorSchema
    dark: ColorSchema
  }
  gradients: {
    light: ColorSchema
    dark: ColorSchema
  }
}

interface ThemeContextType {
  theme: Theme
  toggleTheme: () => void
  saveThemeMode: () => Promise<boolean>
  colorSchemaMode: ColorSchemaMode
  setColorSchemaMode: (mode: ColorSchemaMode) => void
  colorSchema: ColorSchema
  unifiedColorData: UnifiedColorData | null
}

const defaultLightColorSchema: ColorSchema = {
  color1: '#2862EB',
  color2: '#763DED',
  color3: '#059669',
  color4: '#0EA5E9',
  color5: '#F59E0B',
}

const defaultDarkColorSchema: ColorSchema = {
  color1: '#1C4AA5',
  color2: '#5229A6',
  color3: '#047857',
  color4: '#0284C7',
  color5: '#D97706',
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

// Helper function to get current active colors based on theme
const getCurrentActiveColors = (
  unifiedData: UnifiedColorData,
  theme: Theme
): ColorSchema => {
  return theme === 'light' ? unifiedData.light : unifiedData.dark
}

// API functions for theme mode persistence
// Commented out - not currently used but kept for future reference
// const loadThemeModeFromAPI = async (): Promise<Theme | null> => {
//   try {
//     const response = await axios.get('/api/v1/user/theme-mode')
//     if (response.data.success) {
//       return response.data.mode as Theme
//     }
//   } catch (error) {
//     // Silently handle theme loading errors
//   }
//   return null
// }

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
  const [theme, setTheme] = useState<Theme>(() => {
    const initialTheme = (window as any).__INITIAL_THEME__
    if (initialTheme) {
      return initialTheme as Theme
    }

    let savedTheme = localStorage.getItem('pulse_theme') as Theme
    if (!savedTheme) {
      const token = localStorage.getItem('pulse_token')
      savedTheme = token ? 'dark' : 'light'
    }
    return savedTheme
  })

  const [colorSchemaMode, setColorSchemaMode] = useState<ColorSchemaMode>(() => {
    return (localStorage.getItem('pulse_color_schema_mode') as ColorSchemaMode) || 'default'
  })

  const [unifiedColorData, setUnifiedColorData] = useState<UnifiedColorData | null>(null)

  // Function to apply colors to CSS variables
  const applyCSSVariables = (colors: ColorSchema, forceOverride = false) => {
    const root = document.documentElement
    const priority = forceOverride ? 'important' : ''

    root.style.setProperty('--color-1', colors.color1, priority)
    root.style.setProperty('--color-2', colors.color2, priority)
    root.style.setProperty('--color-3', colors.color3, priority)
    root.style.setProperty('--color-4', colors.color4, priority)
    root.style.setProperty('--color-5', colors.color5, priority)

    // Helper function to convert hex to RGB values
    const hexToRgb = (hex: string) => {
      try {
        const h = hex.replace('#', '')
        const r = parseInt(h.slice(0, 2), 16)
        const g = parseInt(h.slice(2, 4), 16)
        const b = parseInt(h.slice(4, 6), 16)
        return `${r}, ${g}, ${b}`
      } catch {
        return '0, 0, 0'
      }
    }

    // Set RGB versions for rgba() usage
    root.style.setProperty('--color-1-rgb', hexToRgb(colors.color1), priority)
    root.style.setProperty('--color-2-rgb', hexToRgb(colors.color2), priority)
    root.style.setProperty('--color-3-rgb', hexToRgb(colors.color3), priority)
    root.style.setProperty('--color-4-rgb', hexToRgb(colors.color4), priority)
    root.style.setProperty('--color-5-rgb', hexToRgb(colors.color5), priority)

    // Calculate and apply on-colors
    const calculateOnColor = (hex: string) => {
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

    root.style.setProperty('--on-color-1', calculateOnColor(colors.color1), priority)
    root.style.setProperty('--on-color-2', calculateOnColor(colors.color2), priority)
    root.style.setProperty('--on-color-3', calculateOnColor(colors.color3), priority)
    root.style.setProperty('--on-color-4', calculateOnColor(colors.color4), priority)
    root.style.setProperty('--on-color-5', calculateOnColor(colors.color5), priority)

    // Set gradient combinations
    root.style.setProperty('--gradient-1-2', `linear-gradient(135deg, ${colors.color1} 0%, ${colors.color2} 100%)`, priority)
    root.style.setProperty('--gradient-2-3', `linear-gradient(135deg, ${colors.color2} 0%, ${colors.color3} 100%)`, priority)
    root.style.setProperty('--gradient-3-4', `linear-gradient(135deg, ${colors.color3} 0%, ${colors.color4} 100%)`, priority)
    root.style.setProperty('--gradient-4-5', `linear-gradient(135deg, ${colors.color4} 0%, ${colors.color5} 100%)`, priority)
    root.style.setProperty('--gradient-5-1', `linear-gradient(135deg, ${colors.color5} 0%, ${colors.color1} 100%)`, priority)

    // Calculate gradient on-colors
    const pairOn = (a: string, b: string) => {
      const onA = calculateOnColor(a), onB = calculateOnColor(b)
      if (onA === onB) return onA

      try {
        const getLuminance = (hex: string): number => {
          const h = hex.replace('#', '')
          const r = parseInt(h.slice(0, 2), 16) / 255
          const g = parseInt(h.slice(2, 4), 16) / 255
          const b = parseInt(h.slice(4, 6), 16) / 255
          const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4))
          return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
        }

        const luminanceA = getLuminance(a)
        const luminanceB = getLuminance(b)
        const averageLuminance = (luminanceA + luminanceB) / 2
        return averageLuminance < 0.5 ? '#FFFFFF' : '#000000'
      } catch {
        return '#FFFFFF'
      }
    }

    root.style.setProperty('--on-gradient-1-2', pairOn(colors.color1, colors.color2), priority)
    root.style.setProperty('--on-gradient-2-3', pairOn(colors.color2, colors.color3), priority)
    root.style.setProperty('--on-gradient-3-4', pairOn(colors.color3, colors.color4), priority)
    root.style.setProperty('--on-gradient-4-5', pairOn(colors.color4, colors.color5), priority)
    root.style.setProperty('--on-gradient-5-1', pairOn(colors.color5, colors.color1), priority)
  }

  const [colorSchemaState, setColorSchemaState] = useState<ColorSchema>(() => {
    return theme === 'light' ? defaultLightColorSchema : defaultDarkColorSchema
  })

  // Custom setColorSchema that also updates CSS variables
  const setColorSchema = (colors: ColorSchema, forceOverride = false) => {
    setColorSchemaState(colors)
    applyCSSVariables(colors, forceOverride)
  }

  const colorSchema = colorSchemaState

  // Apply CSS variables whenever colorSchema changes
  useEffect(() => {
    applyCSSVariables(colorSchema)
  }, [colorSchema])

  // Load unified color data from user profile when available
  useEffect(() => {
    if (isLoading) return
    if (!user || !user.colorSchemaData) return

    setColorSchemaMode(user.colorSchemaData.mode)
    localStorage.setItem('pulse_color_schema_mode', user.colorSchemaData.mode)

    const anyData: any = user.colorSchemaData as any
    if (anyData.unified_colors) {
      setUnifiedColorData(anyData.unified_colors)

      const currentColors = getCurrentActiveColors(anyData.unified_colors, theme)
      setColorSchema(currentColors)

      localStorage.setItem('pulse_unified_colors', JSON.stringify(anyData.unified_colors))
    } else {
      const fallbackColors = theme === 'light' ? defaultLightColorSchema : defaultDarkColorSchema
      setColorSchema(fallbackColors, true)
    }
  }, [user?.colorSchemaData, isLoading])

  // Handle theme changes
  useEffect(() => {
    if (unifiedColorData) {
      const currentColors = getCurrentActiveColors(unifiedColorData, theme)
      setColorSchema(currentColors)
    }
  }, [theme, unifiedColorData])

  // Apply theme to document
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('pulse_theme', theme)
    document.documentElement.offsetHeight
  }, [theme])

  // Apply color schema mode to document
  useEffect(() => {
    document.documentElement.setAttribute('data-color-schema', colorSchemaMode)
    localStorage.setItem('pulse_color_schema_mode', colorSchemaMode)
  }, [colorSchemaMode])

  // Listen for theme changes from other frontends
  useEffect(() => {
    const handleThemeChange = (event: CustomEvent) => {
      const newTheme = event.detail.theme as Theme
      if (newTheme !== theme) {
        setTheme(newTheme)

        if (unifiedColorData) {
          const newColors = getCurrentActiveColors(unifiedColorData, newTheme)
          setColorSchema(newColors)
        }
      }
    }

    window.addEventListener('themeChanged', handleThemeChange as EventListener)
    return () => window.removeEventListener('themeChanged', handleThemeChange as EventListener)
  }, [theme, unifiedColorData])

  // Listen for color schema changes from other frontends (e.g., frontend-app)
  useEffect(() => {
    const handleColorSchemaChange = (event: CustomEvent) => {
      const newUnifiedColors = event.detail.unifiedColors
      if (newUnifiedColors) {
        console.log('🎨 [ETL Frontend] Received color schema change from another frontend')
        setUnifiedColorData(newUnifiedColors)
        const currentColors = getCurrentActiveColors(newUnifiedColors, theme)
        setColorSchema(currentColors)
        localStorage.setItem('pulse_unified_colors', JSON.stringify(newUnifiedColors))
      }
    }

    window.addEventListener('colorSchemaChanged', handleColorSchemaChange as EventListener)
    return () => window.removeEventListener('colorSchemaChanged', handleColorSchemaChange as EventListener)
  }, [theme])

  const toggleTheme = async () => {
    const newTheme = theme === 'light' ? 'dark' : 'light'

    // Dispatch event to prevent immediate sync in AuthContext
    window.dispatchEvent(new CustomEvent('themeToggled'))

    setTheme(newTheme)

    if (unifiedColorData) {
      const newColors = getCurrentActiveColors(unifiedColorData, newTheme)
      setColorSchema(newColors)
    }

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

  const value: ThemeContextType = {
    theme,
    toggleTheme,
    saveThemeMode,
    colorSchemaMode,
    setColorSchemaMode,
    colorSchema,
    unifiedColorData
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
