import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react'

type Theme = 'light' | 'dark'

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
  colorSchema: ColorSchema
  updateColorSchema: (colors: Partial<ColorSchema>) => void
  resetToDefault: () => void
}

const defaultColorSchema: ColorSchema = {
  color1: '#C8102E',  // Custom Red
  color2: '#253746',  // Custom Dark Blue
  color3: '#00C7B1',  // Custom Teal
  color4: '#A2DDF8',  // Custom Light Blue
  color5: '#FFBF3F',  // Custom Yellow
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

interface ThemeProviderProps {
  children: ReactNode
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  const [theme, setTheme] = useState<Theme>('light')
  const [colorSchema, setColorSchema] = useState<ColorSchema>(defaultColorSchema)

  // Initialize theme from localStorage or system preference
  useEffect(() => {
    const savedTheme = localStorage.getItem('pulse_theme') as Theme
    const savedColors = localStorage.getItem('pulse_colors')
    
    if (savedTheme) {
      setTheme(savedTheme)
    } else {
      // Check system preference
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
      setTheme(prefersDark ? 'dark' : 'light')
    }
    
    if (savedColors) {
      try {
        const parsedColors = JSON.parse(savedColors)
        setColorSchema({ ...defaultColorSchema, ...parsedColors })
      } catch (error) {
        console.error('Failed to parse saved colors:', error)
      }
    }
  }, [])

  // Apply theme to document
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('pulse_theme', theme)
  }, [theme])

  // Apply color schema to CSS custom properties
  useEffect(() => {
    const root = document.documentElement
    root.style.setProperty('--color-1', colorSchema.color1)
    root.style.setProperty('--color-2', colorSchema.color2)
    root.style.setProperty('--color-3', colorSchema.color3)
    root.style.setProperty('--color-4', colorSchema.color4)
    root.style.setProperty('--color-5', colorSchema.color5)
    
    localStorage.setItem('pulse_colors', JSON.stringify(colorSchema))
  }, [colorSchema])

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light')
  }

  const updateColorSchema = (colors: Partial<ColorSchema>) => {
    setColorSchema(prev => ({ ...prev, ...colors }))
  }

  const resetToDefault = () => {
    setColorSchema(defaultColorSchema)
  }

  const value: ThemeContextType = {
    theme,
    toggleTheme,
    colorSchema,
    updateColorSchema,
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
