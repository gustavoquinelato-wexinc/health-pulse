import axios from 'axios'
import { createContext, ReactNode, useContext, useEffect, useState } from 'react'
import clientLogger from '../utils/clientLogger'
import { useAuth } from './AuthContext'

type Theme = 'light' | 'dark'
type ColorSchemaMode = 'default' | 'custom'
type AccessibilityLevel = 'regular' | 'AA' | 'AAA'

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
  saveColorSchemaMode: (mode: ColorSchemaMode) => Promise<boolean>
  colorSchema: ColorSchema  // Current active colors (based on theme + mode + accessibility)
  unifiedColorData: UnifiedColorData | null  // All color data from unified table
  updateColorSchema: (lightColors: Partial<ColorSchema>, darkColors: Partial<ColorSchema>) => void
  saveColorSchema: () => Promise<boolean>
  resetToDefault: () => void
  accessibilityLevel: AccessibilityLevel
  setAccessibilityLevel: (level: AccessibilityLevel) => void
}

const defaultLightColorSchema: ColorSchema = {
  color1: '#2862EB',  // Blue - Primary
  color2: '#763DED',  // Purple - Secondary
  color3: '#059669',  // Emerald - Success
  color4: '#0EA5E9',  // Sky Blue - Info
  color5: '#F59E0B',  // Amber - Warning
}

const defaultDarkColorSchema: ColorSchema = {
  color1: '#1C4AA5',  // Darker Blue - Primary
  color2: '#5229A6',  // Darker Purple - Secondary
  color3: '#047857',  // Darker Emerald - Success
  color4: '#0284C7',  // Darker Sky Blue - Info
  color5: '#D97706',  // Darker Amber - Warning
}



const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

// Helper function to get current active colors based on theme
const getCurrentActiveColors = (
  unifiedData: UnifiedColorData,
  theme: Theme
): ColorSchema => {
  return theme === 'light' ? unifiedData.light : unifiedData.dark
}

// API functions for color schema persistence
const saveUnifiedColorSchemaToAPI = async (lightColors: ColorSchema, darkColors: ColorSchema): Promise<boolean> => {
  try {
    // Backend expects unified structure: { light_colors: {...}, dark_colors: {...} }
    const payload = {
      light_colors: lightColors,
      dark_colors: darkColors
    }
    const response = await axios.post('/api/v1/admin/color-schema/unified', payload)
    return response.status >= 200 && response.status < 300
  } catch (error) {
    clientLogger.error('Failed to save unified color schema to API', {
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
  const [theme, setTheme] = useState<Theme>(() => {
    // First check if HTML script set an initial theme
    const initialTheme = (window as any).__INITIAL_THEME__
    if (initialTheme) {
      return initialTheme as Theme
    }

    // Fallback to the same logic as HTML initialization
    let savedTheme = localStorage.getItem('pulse_theme') as Theme

    if (!savedTheme) {
      const token = localStorage.getItem('pulse_token')
      if (token) {
        // User is logged in but no theme cached - assume dark to match HTML
        savedTheme = 'dark'
      } else {
        // No user logged in, use light as default
        savedTheme = 'light'
      }
    }

    return savedTheme
  })
  const [colorSchemaMode, setColorSchemaMode] = useState<ColorSchemaMode>(() => (localStorage.getItem('pulse_color_schema_mode') as ColorSchemaMode) || 'default')
  const [accessibilityLevel, setAccessibilityLevel] = useState<AccessibilityLevel>(() => (localStorage.getItem('pulse_accessibility_level') as AccessibilityLevel) || 'regular')
  const [unifiedColorData, setUnifiedColorData] = useState<UnifiedColorData | null>(null)

  // Function to apply colors to CSS variables with force override
  const applyCSSVariables = (colors: ColorSchema, forceOverride = false) => {
    const root = document.documentElement

    // Use !important for force override to ensure it overrides index.html styles
    const priority = forceOverride ? 'important' : ''

    root.style.setProperty('--color-1', colors.color1, priority)
    root.style.setProperty('--color-2', colors.color2, priority)
    root.style.setProperty('--color-3', colors.color3, priority)
    root.style.setProperty('--color-4', colors.color4, priority)
    root.style.setProperty('--color-5', colors.color5, priority)

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


  }

  const [colorSchemaState, setColorSchemaState] = useState<ColorSchema>(() => {
    // Try to load cached colors first to prevent flash
    try {
      const cached = localStorage.getItem('pulse_colors')
      if (cached) {
        const parsedColors = JSON.parse(cached)
        return parsedColors
      }
    } catch (error) {
      console.warn('Failed to load cached colors:', error)
    }

    // Fallback to default colors based on current theme
    return theme === 'light' ? defaultLightColorSchema : defaultDarkColorSchema
  })

  // Custom setColorSchema that also updates CSS variables
  const setColorSchema = (colors: ColorSchema, forceOverride = false) => {
    setColorSchemaState(colors)
    applyCSSVariables(colors, forceOverride)
  }

  // Expose the current color schema
  const colorSchema = colorSchemaState

  // Function to clear color cache (useful for testing)
  const clearColorCache = () => {
    try {
      localStorage.removeItem('pulse_colors')
      console.log('🗑️ Color cache cleared')
    } catch (error) {
      console.warn('Failed to clear color cache:', error)
    }
  }

  // Apply CSS variables whenever colorSchema changes
  useEffect(() => {
    applyCSSVariables(colorSchema)
  }, [colorSchema])

  // Load unified color data from user profile when available
  useEffect(() => {
    if (isLoading) return
    if (!user || !user.colorSchemaData) return

    // Apply mode
    setColorSchemaMode(user.colorSchemaData.mode)

    // Load unified color data from the new structure
    const anyData: any = user.colorSchemaData as any
    if (anyData.unified_colors) {
      setUnifiedColorData(anyData.unified_colors)

      // Set current active colors based on theme, mode, and accessibility level
      const currentColors = getCurrentActiveColors(
        anyData.unified_colors,
        theme
      )

      // Simply set the colors from database - no mismatch detection needed
      setColorSchema(currentColors)
    } else {
      // No unified colors found - fallback to default colors to prevent crashes
      const fallbackColors = theme === 'light' ? defaultLightColorSchema : defaultDarkColorSchema
      setColorSchema(fallbackColors, true)
    }
  }, [user?.colorSchemaData, isLoading, theme, accessibilityLevel])

  // Handle theme changes - update active colors when theme switches
  useEffect(() => {
    if (unifiedColorData) {
      const currentColors = getCurrentActiveColors(unifiedColorData, theme)
      setColorSchema(currentColors)
    }
  }, [theme, unifiedColorData])

  // Theme is now loaded during authentication in AuthContext
  // This effect is only for manual theme changes or edge cases
  useEffect(() => {
    const syncThemeIfNeeded = async () => {
      if (isLoading || !user) {
        return
      }

      // Only sync if there's a significant mismatch (not just initialization)
      const currentDOMTheme = document.documentElement.getAttribute('data-theme')
      const currentStorageTheme = localStorage.getItem('pulse_theme')

      if (currentDOMTheme !== theme || currentStorageTheme !== theme) {


        try {
          const savedTheme = await loadThemeModeFromAPI()
          if (savedTheme && savedTheme !== theme) {

            setTheme(savedTheme)
          }
        } catch (error) {
          console.warn('Theme sync failed, using current state:', error)
        }
      }
    }

    // Only run this sync check after initial load is complete
    if (user && !isLoading) {
      // Delay to avoid conflicts with AuthContext theme loading
      setTimeout(syncThemeIfNeeded, 100)
    }
  }, [user, isLoading]) // Removed theme dependency to prevent loops



  // Apply theme to document
  useEffect(() => {
    // Apply theme immediately to prevent any flash
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('pulse_theme', theme)

    // Force a repaint to ensure the theme is applied immediately
    document.documentElement.offsetHeight
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

    // Determine if we should use adaptive colors based on theme mode mismatch
    const shouldUseAdaptiveColors = () => {
      if (!user?.colorSchemaData) return false

      const anyData: any = user.colorSchemaData as any
      const currentColors = (colorSchemaMode === 'custom' && anyData.custom_colors)
        ? anyData.custom_colors
        : (colorSchemaMode === 'default' && anyData.default_colors)
          ? anyData.default_colors
          : null

      if (!currentColors?.colors_defined_in_mode) return false

      // Use adaptive colors if current theme differs from colors_defined_in_mode
      return theme !== currentColors.colors_defined_in_mode
    }

    // Get the appropriate color set (regular or adaptive)
    const getActiveColors = () => {
      if (!shouldUseAdaptiveColors()) {
        return colorSchema
      }

      // Use adaptive colors from accessibility data
      const anyData: any = user?.colorSchemaData as any
      const adaptiveColors = anyData?.accessibility_colors_aa

      if (adaptiveColors) {
        return {
          color1: adaptiveColors.adaptive_color1 || colorSchema.color1,
          color2: adaptiveColors.adaptive_color2 || colorSchema.color2,
          color3: adaptiveColors.adaptive_color3 || colorSchema.color3,
          color4: adaptiveColors.adaptive_color4 || colorSchema.color4,
          color5: adaptiveColors.adaptive_color5 || colorSchema.color5,
        }
      }

      return colorSchema
    }

    const activeColors = getActiveColors()

    // Set active colors (regular or adaptive based on theme mode mismatch)
    root.style.setProperty('--color-1', activeColors.color1)
    root.style.setProperty('--color-2', activeColors.color2)
    root.style.setProperty('--color-3', activeColors.color3)
    root.style.setProperty('--color-4', activeColors.color4)
    root.style.setProperty('--color-5', activeColors.color5)

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

    const on1 = pickOn(activeColors.color1)
    const on2 = pickOn(activeColors.color2)
    const on3 = pickOn(activeColors.color3)
    const on4 = pickOn(activeColors.color4)
    const on5 = pickOn(activeColors.color5)

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

    root.style.setProperty('--on-gradient-1-2', pairOn(activeColors.color1, activeColors.color2))
    root.style.setProperty('--on-gradient-2-3', pairOn(activeColors.color2, activeColors.color3))
    root.style.setProperty('--on-gradient-3-4', pairOn(activeColors.color3, activeColors.color4))
    root.style.setProperty('--on-gradient-4-5', pairOn(activeColors.color4, activeColors.color5))
    root.style.setProperty('--on-gradient-5-1', pairOn(activeColors.color5, activeColors.color1))

    // Set gradient color combinations using active colors (regular or adaptive)
    root.style.setProperty('--gradient-1-2', `linear-gradient(135deg, ${activeColors.color1} 0%, ${activeColors.color2} 100%)`)
    root.style.setProperty('--gradient-2-3', `linear-gradient(135deg, ${activeColors.color2} 0%, ${activeColors.color3} 100%)`)
    root.style.setProperty('--gradient-3-4', `linear-gradient(135deg, ${activeColors.color3} 0%, ${activeColors.color4} 100%)`)
    root.style.setProperty('--gradient-4-5', `linear-gradient(135deg, ${activeColors.color4} 0%, ${activeColors.color5} 100%)`)
    root.style.setProperty('--gradient-5-1', `linear-gradient(135deg, ${activeColors.color5} 0%, ${activeColors.color1} 100%)`)

    // Persist last used colors for quick boot
    const colorDataWithTimestamp = { ...colorSchema, _timestamp: Date.now() }
    localStorage.setItem('pulse_colors', JSON.stringify(colorDataWithTimestamp))
  }, [colorSchema, colorSchemaMode, theme, user?.colorSchemaData])

  const toggleTheme = async () => {
    const newTheme = theme === 'light' ? 'dark' : 'light'
    setTheme(newTheme)

    // Use current unifiedColorData for theme toggle
    if (unifiedColorData) {
      const newColors = getCurrentActiveColors(unifiedColorData, newTheme)
      setColorSchema(newColors)
    }

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

  const updateColorSchema = (lightColors: Partial<ColorSchema>, darkColors: Partial<ColorSchema>) => {
    if (unifiedColorData) {
      const updatedUnifiedData: UnifiedColorData = {
        ...unifiedColorData,
        light: { ...unifiedColorData.light, ...lightColors },
        dark: { ...unifiedColorData.dark, ...darkColors }
      }
      setUnifiedColorData(updatedUnifiedData)

      // Update current active colors based on current theme
      const currentColors = getCurrentActiveColors(updatedUnifiedData, theme)
      setColorSchema(currentColors)

      // Update cache with the new colors
      try {
        const colorDataWithTimestamp = { ...currentColors, _timestamp: Date.now() }
        localStorage.setItem('pulse_colors', JSON.stringify(colorDataWithTimestamp))
      } catch (error) {
        console.warn('Failed to update color cache:', error)
      }
    }
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
          const colorDataWithTimestamp = { ...res.data.colors, _timestamp: Date.now() }
          localStorage.setItem('pulse_colors', JSON.stringify(colorDataWithTimestamp))
        }
      } catch (e) {
        console.warn('Failed to refresh color schema after mode change', e)
      }
    }
    return success
  }

  const saveColorSchema = async (): Promise<boolean> => {
    if (!unifiedColorData) return false

    const success = await saveUnifiedColorSchemaToAPI(unifiedColorData.light, unifiedColorData.dark)
    if (success) {
      // Also save to localStorage as backup
      localStorage.setItem('pulse_unified_colors', JSON.stringify(unifiedColorData))
      // Refresh from server to apply recomputed on-colors and any server-side validation
      try {
        const res = await axios.get('/api/v1/admin/color-schema/unified')
        if (res.data?.success && res.data.unified_colors) {
          setUnifiedColorData(res.data.unified_colors)
          const currentColors = getCurrentActiveColors(res.data.unified_colors, theme)
          setColorSchema(currentColors)
          localStorage.setItem('pulse_unified_colors', JSON.stringify(res.data.unified_colors))
        }
      } catch (e) {
        console.warn('Failed to refresh unified color schema after save', e)
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
    unifiedColorData,
    updateColorSchema,
    saveColorSchema,
    resetToDefault,
    accessibilityLevel,
    setAccessibilityLevel
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
