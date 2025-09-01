import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'
import { colorDataService } from '../services/colorDataService'
import { getColorSchemaMode } from '../utils/colorSchemaService'

export default function ColorSchemaPanel() {
  const { theme, setColorSchemaMode, updateColorSchema } = useTheme()
  const { refreshUserColors } = useAuth()

  // State variables for unified architecture
  const [tempColorSchemaMode, setTempColorSchemaMode] = useState<'default' | 'custom' | null>(null)
  const [hasChanges, setHasChanges] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  // Side-by-side Light/Dark Mode Colors
  const [lightColors, setLightColors] = useState<any>({
    color1: '#C8102E', color2: '#253746', color3: '#00C7B1', color4: '#A2DDF8', color5: '#FFBF3F'
  })
  const [darkColors, setDarkColors] = useState<any>({
    color1: '#A00E26', color2: '#1E2B36', color3: '#00A394', color4: '#7BC3E8', color5: '#E6AC38'
  })

  // Instant preview colors for immediate UI feedback
  const [previewColor1, setPreviewColor1] = useState<string | null>(null)



  // Calculated variants from unified table - all accessibility levels
  const [lightVariants, setLightVariants] = useState<any>({})
  const [darkVariants, setDarkVariants] = useState<any>({})
  const [lightVariantsAA, setLightVariantsAA] = useState<any>({})
  const [darkVariantsAA, setDarkVariantsAA] = useState<any>({})
  const [lightVariantsAAA, setLightVariantsAAA] = useState<any>({})
  const [darkVariantsAAA, setDarkVariantsAAA] = useState<any>({})

  // Database state for comparison
  const [databaseLightColors, setDatabaseLightColors] = useState<any>({})
  const [databaseDarkColors, setDatabaseDarkColors] = useState<any>({})
  const [databaseMode, setDatabaseMode] = useState<string>('default')

  // Load unified color data from API
  useEffect(() => {
    const loadUnifiedColorData = async () => {
      try {
        setIsLoading(true)

        // Get current mode from localStorage to load correct colors
        const currentMode = localStorage.getItem('pulse_color_schema_mode') || 'default'
        const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001'}/api/v1/admin/color-schema/unified?mode=${currentMode}`, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('pulse_token') || ''}`
          }
        })

        if (response.ok) {
          const json = await response.json()

          if (json?.success) {
            // Use centralized service to get mode (handles fallbacks and localStorage sync)
            const mode = await getColorSchemaMode()
            setTempColorSchemaMode(mode)
            setDatabaseMode(mode)
            setColorSchemaMode(mode)

            // Load colors from localStorage complete color data directly
            const completeColorData = localStorage.getItem('pulse_complete_color_data')
            let lightRegular: any = null
            let darkRegular: any = null
            let lightAA: any = null
            let darkAA: any = null
            let lightAAA: any = null
            let darkAAA: any = null

            if (completeColorData) {
              try {
                const allColors = JSON.parse(completeColorData)
                lightRegular = allColors.find((c: any) => c.color_schema_mode === mode && c.theme_mode === 'light' && c.accessibility_level === 'regular')
                darkRegular = allColors.find((c: any) => c.color_schema_mode === mode && c.theme_mode === 'dark' && c.accessibility_level === 'regular')
                lightAA = allColors.find((c: any) => c.color_schema_mode === mode && c.theme_mode === 'light' && c.accessibility_level === 'AA')
                darkAA = allColors.find((c: any) => c.color_schema_mode === mode && c.theme_mode === 'dark' && c.accessibility_level === 'AA')
                lightAAA = allColors.find((c: any) => c.color_schema_mode === mode && c.theme_mode === 'light' && c.accessibility_level === 'AAA')
                darkAAA = allColors.find((c: any) => c.color_schema_mode === mode && c.theme_mode === 'dark' && c.accessibility_level === 'AAA')


              } catch (e) {
                console.warn('Failed to parse complete color data:', e)
              }
            }

            // Process color data (now from localStorage instead of API)
            if (lightRegular && darkRegular) {

              if (lightRegular) {
                const light = {
                  color1: lightRegular.color1, color2: lightRegular.color2, color3: lightRegular.color3,
                  color4: lightRegular.color4, color5: lightRegular.color5
                }
                setLightColors(light)
                setDatabaseLightColors(light)
                setLightVariants({
                  on_color1: (lightRegular as any).on_color1, on_color2: (lightRegular as any).on_color2, on_color3: (lightRegular as any).on_color3,
                  on_color4: (lightRegular as any).on_color4, on_color5: (lightRegular as any).on_color5,
                  on_gradient_1_2: (lightRegular as any).on_gradient_1_2, on_gradient_2_3: (lightRegular as any).on_gradient_2_3,
                  on_gradient_3_4: (lightRegular as any).on_gradient_3_4, on_gradient_4_5: (lightRegular as any).on_gradient_4_5,
                  on_gradient_5_1: (lightRegular as any).on_gradient_5_1
                })
              }

              if (darkRegular) {
                const dark = {
                  color1: darkRegular.color1, color2: darkRegular.color2, color3: darkRegular.color3,
                  color4: darkRegular.color4, color5: darkRegular.color5
                }
                setDarkColors(dark)
                setDatabaseDarkColors(dark)
                setDarkVariants({
                  on_color1: (darkRegular as any).on_color1, on_color2: (darkRegular as any).on_color2, on_color3: (darkRegular as any).on_color3,
                  on_color4: (darkRegular as any).on_color4, on_color5: (darkRegular as any).on_color5,
                  on_gradient_1_2: (darkRegular as any).on_gradient_1_2, on_gradient_2_3: (darkRegular as any).on_gradient_2_3,
                  on_gradient_3_4: (darkRegular as any).on_gradient_3_4, on_gradient_4_5: (darkRegular as any).on_gradient_4_5,
                  on_gradient_5_1: (darkRegular as any).on_gradient_5_1
                })
              }

              // Load AA accessibility level variants
              if (lightAA) {
                setLightVariantsAA({
                  on_color1: (lightAA as any).on_color1, on_color2: (lightAA as any).on_color2, on_color3: (lightAA as any).on_color3,
                  on_color4: (lightAA as any).on_color4, on_color5: (lightAA as any).on_color5,
                  on_gradient_1_2: (lightAA as any).on_gradient_1_2, on_gradient_2_3: (lightAA as any).on_gradient_2_3,
                  on_gradient_3_4: (lightAA as any).on_gradient_3_4, on_gradient_4_5: (lightAA as any).on_gradient_4_5,
                  on_gradient_5_1: (lightAA as any).on_gradient_5_1
                })
              }

              if (darkAA) {
                setDarkVariantsAA({
                  on_color1: (darkAA as any).on_color1, on_color2: (darkAA as any).on_color2, on_color3: (darkAA as any).on_color3,
                  on_color4: (darkAA as any).on_color4, on_color5: (darkAA as any).on_color5,
                  on_gradient_1_2: (darkAA as any).on_gradient_1_2, on_gradient_2_3: (darkAA as any).on_gradient_2_3,
                  on_gradient_3_4: (darkAA as any).on_gradient_3_4, on_gradient_4_5: (darkAA as any).on_gradient_4_5,
                  on_gradient_5_1: (darkAA as any).on_gradient_5_1
                })
              }

              // Load AAA accessibility level variants
              if (lightAAA) {
                setLightVariantsAAA({
                  on_color1: (lightAAA as any).on_color1, on_color2: (lightAAA as any).on_color2, on_color3: (lightAAA as any).on_color3,
                  on_color4: (lightAAA as any).on_color4, on_color5: (lightAAA as any).on_color5,
                  on_gradient_1_2: (lightAAA as any).on_gradient_1_2, on_gradient_2_3: (lightAAA as any).on_gradient_2_3,
                  on_gradient_3_4: (lightAAA as any).on_gradient_3_4, on_gradient_4_5: (lightAAA as any).on_gradient_4_5,
                  on_gradient_5_1: (lightAAA as any).on_gradient_5_1
                })
              }

              if (darkAAA) {
                setDarkVariantsAAA({
                  on_color1: (darkAAA as any).on_color1, on_color2: (darkAAA as any).on_color2, on_color3: (darkAAA as any).on_color3,
                  on_color4: (darkAAA as any).on_color4, on_color5: (darkAAA as any).on_color5,
                  on_gradient_1_2: (darkAAA as any).on_gradient_1_2, on_gradient_2_3: (darkAAA as any).on_gradient_2_3,
                  on_gradient_3_4: (darkAAA as any).on_gradient_3_4, on_gradient_4_5: (darkAAA as any).on_gradient_4_5,
                  on_gradient_5_1: (darkAAA as any).on_gradient_5_1
                })
              }

              // Don't update ThemeContext during initial load - let it use database colors
            }
          }
        }
      } catch (error) {
        console.error('❌ Error loading unified color data:', error)
      } finally {
        setIsLoading(false)
      }
    }

    loadUnifiedColorData()
  }, [])



  // Check for changes
  useEffect(() => {
    const lightChanged = JSON.stringify(lightColors) !== JSON.stringify(databaseLightColors)
    const darkChanged = JSON.stringify(darkColors) !== JSON.stringify(databaseDarkColors)
    const modeChanged = tempColorSchemaMode !== databaseMode
    setHasChanges(lightChanged || darkChanged || modeChanged)
  }, [lightColors, darkColors, tempColorSchemaMode, databaseLightColors, databaseDarkColors, databaseMode])

  // Don't auto-sync edit mode with hasChanges - it's too unstable during initialization
  // Only activate edit mode through explicit user actions





  // Handle mode change
  const handleModeChange = async (mode: 'default' | 'custom') => {
    // Update UI immediately for instant feedback
    setTempColorSchemaMode(mode)

    // Set preview color immediately with correct hardcoded values to prevent flicker
    const defaultColor1Light = '#2862EB' // Default blue
    const defaultColor1Dark = '#2862EB'   // Same for dark (from migration)
    const customColor1Light = '#C8102E'   // WEX red (light)
    const customColor1Dark = '#A00E26'    // WEX red (dark) - corrected to match actual database value

    const previewColor = mode === 'default'
      ? (theme === 'light' ? defaultColor1Light : defaultColor1Dark)
      : (theme === 'light' ? customColor1Light : customColor1Dark)

    setPreviewColor1(previewColor)

    // Don't update ThemeContext during mode change - let UI elements stay with database colors

    // Load colors for the selected mode from localStorage (complete color data)
    try {
      // Get all color combinations for the selected mode from localStorage
      const lightRegular = colorDataService.getColors(mode, 'light', 'regular')
      const darkRegular = colorDataService.getColors(mode, 'dark', 'regular')
      const lightAA = colorDataService.getColors(mode, 'light', 'AA')
      const darkAA = colorDataService.getColors(mode, 'dark', 'AA')
      const lightAAA = colorDataService.getColors(mode, 'light', 'AAA')
      const darkAAA = colorDataService.getColors(mode, 'dark', 'AAA')

      if (lightRegular && darkRegular) {

        if (lightRegular) {
          const light = {
            color1: lightRegular.color1, color2: lightRegular.color2, color3: lightRegular.color3,
            color4: lightRegular.color4, color5: lightRegular.color5
          }
          setLightColors(light)
          setLightVariants({
            on_color1: (lightRegular as any).on_color1, on_color2: (lightRegular as any).on_color2, on_color3: (lightRegular as any).on_color3,
            on_color4: (lightRegular as any).on_color4, on_color5: (lightRegular as any).on_color5,
            on_gradient_1_2: (lightRegular as any).on_gradient_1_2, on_gradient_2_3: (lightRegular as any).on_gradient_2_3,
            on_gradient_3_4: (lightRegular as any).on_gradient_3_4, on_gradient_4_5: (lightRegular as any).on_gradient_4_5,
            on_gradient_5_1: (lightRegular as any).on_gradient_5_1
          })
        }

        if (darkRegular) {
          const dark = {
            color1: darkRegular.color1, color2: darkRegular.color2, color3: darkRegular.color3,
            color4: darkRegular.color4, color5: darkRegular.color5
          }
          setDarkColors(dark)
          setDarkVariants({
            on_color1: (darkRegular as any).on_color1, on_color2: (darkRegular as any).on_color2, on_color3: (darkRegular as any).on_color3,
            on_color4: (darkRegular as any).on_color4, on_color5: (darkRegular as any).on_color5,
            on_gradient_1_2: (darkRegular as any).on_gradient_1_2, on_gradient_2_3: (darkRegular as any).on_gradient_2_3,
            on_gradient_3_4: (darkRegular as any).on_gradient_3_4, on_gradient_4_5: (darkRegular as any).on_gradient_4_5,
            on_gradient_5_1: (darkRegular as any).on_gradient_5_1
          })
        }

        // Update ThemeContext to show the mode change in UI elements
        if (lightRegular && darkRegular) {
          const lightColors = {
            color1: lightRegular.color1, color2: lightRegular.color2, color3: lightRegular.color3,
            color4: lightRegular.color4, color5: lightRegular.color5
          }
          const darkColors = {
            color1: darkRegular.color1, color2: darkRegular.color2, color3: darkRegular.color3,
            color4: darkRegular.color4, color5: darkRegular.color5
          }
          updateColorSchema(lightColors, darkColors)
        }

        // Load AA accessibility level variants
        if (lightAA) {
          setLightVariantsAA({
            on_color1: (lightAA as any).on_color1, on_color2: (lightAA as any).on_color2, on_color3: (lightAA as any).on_color3,
            on_color4: (lightAA as any).on_color4, on_color5: (lightAA as any).on_color5,
            on_gradient_1_2: (lightAA as any).on_gradient_1_2, on_gradient_2_3: (lightAA as any).on_gradient_2_3,
            on_gradient_3_4: (lightAA as any).on_gradient_3_4, on_gradient_4_5: (lightAA as any).on_gradient_4_5,
            on_gradient_5_1: (lightAA as any).on_gradient_5_1
          })
        }

        if (darkAA) {
          setDarkVariantsAA({
            on_color1: (darkAA as any).on_color1, on_color2: (darkAA as any).on_color2, on_color3: (darkAA as any).on_color3,
            on_color4: (darkAA as any).on_color4, on_color5: (darkAA as any).on_color5,
            on_gradient_1_2: (darkAA as any).on_gradient_1_2, on_gradient_2_3: (darkAA as any).on_gradient_2_3,
            on_gradient_3_4: (darkAA as any).on_gradient_3_4, on_gradient_4_5: (darkAA as any).on_gradient_4_5,
            on_gradient_5_1: (darkAA as any).on_gradient_5_1
          })
        }

        // Load AAA accessibility level variants
        if (lightAAA) {
          setLightVariantsAAA({
            on_color1: (lightAAA as any).on_color1, on_color2: (lightAAA as any).on_color2, on_color3: (lightAAA as any).on_color3,
            on_color4: (lightAAA as any).on_color4, on_color5: (lightAAA as any).on_color5,
            on_gradient_1_2: (lightAAA as any).on_gradient_1_2, on_gradient_2_3: (lightAAA as any).on_gradient_2_3,
            on_gradient_3_4: (lightAAA as any).on_gradient_3_4, on_gradient_4_5: (lightAAA as any).on_gradient_4_5,
            on_gradient_5_1: (lightAAA as any).on_gradient_5_1
          })
        }

        if (darkAAA) {
          setDarkVariantsAAA({
            on_color1: (darkAAA as any).on_color1, on_color2: (darkAAA as any).on_color2, on_color3: (darkAAA as any).on_color3,
            on_color4: (darkAAA as any).on_color4, on_color5: (darkAAA as any).on_color5,
            on_gradient_1_2: (darkAAA as any).on_gradient_1_2, on_gradient_2_3: (darkAAA as any).on_gradient_2_3,
            on_gradient_3_4: (darkAAA as any).on_gradient_3_4, on_gradient_4_5: (darkAAA as any).on_gradient_4_5,
            on_gradient_5_1: (darkAAA as any).on_gradient_5_1
          })
        }
      }

      // Clear preview color once real colors are loaded
      setPreviewColor1(null)
    } catch (error) {
      console.error('❌ Error loading colors for mode change:', error)
      // Clear preview color on error too
      setPreviewColor1(null)
    }
  }

  // Utility function to calculate on-color (text color) for a given background color
  const calculateOnColor = (hexColor: string): string => {
    try {
      // Remove # if present
      const hex = hexColor.replace('#', '')

      // Convert to RGB
      const r = parseInt(hex.slice(0, 2), 16) / 255
      const g = parseInt(hex.slice(2, 4), 16) / 255
      const b = parseInt(hex.slice(4, 6), 16) / 255

      // Calculate relative luminance using WCAG formula
      const linearize = (c: number) => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4))
      const L = 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)

      // Calculate contrast ratios with black and white
      const contrastWithBlack = (L + 0.05) / (0 + 0.05)
      const contrastWithWhite = (1 + 0.05) / (L + 0.05)

      // Return color with better contrast
      return contrastWithWhite >= contrastWithBlack ? '#FFFFFF' : '#000000'
    } catch (error) {
      console.warn('Error calculating on-color for', hexColor, error)
      return '#000000' // Default to black
    }
  }

  // Utility function to calculate on-color for gradients (pair of colors)
  const calculateGradientOnColor = (color1: string, color2: string): string => {
    const onColor1 = calculateOnColor(color1)
    const onColor2 = calculateOnColor(color2)

    // If both colors need the same text color, use it
    if (onColor1 === onColor2) {
      return onColor1
    }

    // If different, use average luminance method for better gradient text color
    try {
      // Calculate luminance for both colors
      const getLuminance = (hexColor: string): number => {
        const hex = hexColor.replace('#', '')
        const r = parseInt(hex.slice(0, 2), 16) / 255
        const g = parseInt(hex.slice(2, 4), 16) / 255
        const b = parseInt(hex.slice(4, 6), 16) / 255
        const linearize = (c: number) => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4))
        return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)
      }

      const luminance1 = getLuminance(color1)
      const luminance2 = getLuminance(color2)
      const averageLuminance = (luminance1 + luminance2) / 2

      // Use 0.5 threshold on average luminance
      return averageLuminance < 0.5 ? '#FFFFFF' : '#000000'
    } catch (error) {
      console.warn('Error calculating gradient on-color, falling back to white:', error)
      return '#FFFFFF' // Fallback to white for safety
    }
  }

  // Handle color change with real-time on-color calculation and immediate ThemeContext update
  const handleColorChange = (theme: 'light' | 'dark', colorKey: string, value: string) => {
    if (tempColorSchemaMode !== 'custom') return

    if (theme === 'light') {
      const newLightColors = { ...lightColors, [colorKey]: value }
      setLightColors(newLightColors)

      // Recalculate on-colors for light theme
      const newLightVariants = {
        on_color1: calculateOnColor(newLightColors.color1),
        on_color2: calculateOnColor(newLightColors.color2),
        on_color3: calculateOnColor(newLightColors.color3),
        on_color4: calculateOnColor(newLightColors.color4),
        on_color5: calculateOnColor(newLightColors.color5),
        on_gradient_1_2: calculateGradientOnColor(newLightColors.color1, newLightColors.color2),
        on_gradient_2_3: calculateGradientOnColor(newLightColors.color2, newLightColors.color3),
        on_gradient_3_4: calculateGradientOnColor(newLightColors.color3, newLightColors.color4),
        on_gradient_4_5: calculateGradientOnColor(newLightColors.color4, newLightColors.color5),
        on_gradient_5_1: calculateGradientOnColor(newLightColors.color5, newLightColors.color1)
      }
      setLightVariants(newLightVariants)

      // Don't update ThemeContext during color changes - only update local preview
    } else {
      const newDarkColors = { ...darkColors, [colorKey]: value }
      setDarkColors(newDarkColors)

      // Recalculate on-colors for dark theme
      const newDarkVariants = {
        on_color1: calculateOnColor(newDarkColors.color1),
        on_color2: calculateOnColor(newDarkColors.color2),
        on_color3: calculateOnColor(newDarkColors.color3),
        on_color4: calculateOnColor(newDarkColors.color4),
        on_color5: calculateOnColor(newDarkColors.color5),
        on_gradient_1_2: calculateGradientOnColor(newDarkColors.color1, newDarkColors.color2),
        on_gradient_2_3: calculateGradientOnColor(newDarkColors.color2, newDarkColors.color3),
        on_gradient_3_4: calculateGradientOnColor(newDarkColors.color3, newDarkColors.color4),
        on_gradient_4_5: calculateGradientOnColor(newDarkColors.color4, newDarkColors.color5),
        on_gradient_5_1: calculateGradientOnColor(newDarkColors.color5, newDarkColors.color1)
      }
      setDarkVariants(newDarkVariants)

      // Don't update ThemeContext during color changes - only update local preview
    }

    // Mark as having changes
    setHasChanges(true)
  }

  // Save changes
  const handleSave = async () => {
    if (!hasChanges) return

    try {
      setIsSaving(true)

      // Save mode if changed
      if (tempColorSchemaMode !== databaseMode) {
        const modeResponse = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001'}/api/v1/admin/color-schema/mode`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('pulse_token') || ''}`
          },
          body: JSON.stringify({ mode: tempColorSchemaMode })
        })

        if (!modeResponse.ok) {
          throw new Error('Failed to save color schema mode')
        }
      }

      // Save colors if in custom mode and colors changed
      if (tempColorSchemaMode === 'custom') {
        const colorResponse = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001'}/api/v1/admin/color-schema/unified`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('pulse_token') || ''}`
          },
          body: JSON.stringify({
            light_colors: lightColors,
            dark_colors: darkColors
          })
        })

        if (!colorResponse.ok) {
          throw new Error('Failed to save colors')
        }
      }

      // Update database state
      setDatabaseMode(tempColorSchemaMode || 'default')
      setDatabaseLightColors(lightColors)
      setDatabaseDarkColors(darkColors)
      setColorSchemaMode(tempColorSchemaMode || 'default')

      // Update ThemeContext with both light and dark colors
      updateColorSchema(lightColors, darkColors)

      // Refresh AuthContext colors to ensure consistency across the app
      await refreshUserColors()

      setHasChanges(false)
    } catch (error) {
      console.error('❌ Error saving color schema:', error)
    } finally {
      setIsSaving(false)
    }
  }

  // Reset changes
  const handleReset = () => {
    setTempColorSchemaMode(databaseMode as 'default' | 'custom')
    setLightColors(databaseLightColors)
    setDarkColors(databaseDarkColors)
    setHasChanges(false)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center space-y-4">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"></div>
          <p className="text-muted">Loading color schema...</p>
        </div>
      </div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="space-y-8"
    >
      {/* Action Buttons */}
      <div className="flex items-center justify-end space-x-3">
        <button
          onClick={handleReset}
          disabled={!hasChanges}
          className="px-4 py-2 text-sm border border-default rounded-lg hover:bg-muted transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Reset
        </button>
        <button
          onClick={handleSave}
          disabled={!hasChanges || isSaving}
          className="px-4 py-2 text-sm btn-crud-edit text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed disabled:bg-gray-400 disabled:text-gray-200 transform-none hover:transform-none"
        >
          {isSaving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>

      {/* Mode Selection */}
      <div className="card p-6">
        <h4 className="text-md font-medium text-primary mb-4">Schema Mode</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <label
            className={`flex items-center space-x-3 p-4 border rounded-lg cursor-pointer transition-all ${tempColorSchemaMode === 'default'
              ? 'border-white text-white shadow-lg'
              : 'border-default hover:bg-muted/50'
              }`}
            style={{
              backgroundColor: tempColorSchemaMode === 'default'
                ? (previewColor1 && tempColorSchemaMode === 'default'
                  ? previewColor1
                  : (theme === 'light' ? lightColors.color1 : darkColors.color1))
                : 'transparent'
            }}
          >
            <input
              type="radio"
              name="colorMode"
              value="default"
              checked={tempColorSchemaMode === 'default'}
              onChange={() => handleModeChange('default')}
              className={tempColorSchemaMode === 'default' ? 'text-white' : 'text-primary'}
            />
            <div>
              <div className={`font-medium ${tempColorSchemaMode === 'default' ? 'text-white' : 'text-primary'}`}>
                Default Colors
              </div>
              <div className={`text-sm ${tempColorSchemaMode === 'default' ? 'text-white/80' : 'text-muted'}`}>
                Use system default color palette
              </div>
            </div>
          </label>
          <label
            className={`flex items-center space-x-3 p-4 border rounded-lg cursor-pointer transition-all ${tempColorSchemaMode === 'custom'
              ? 'border-white text-white shadow-lg'
              : 'border-default hover:bg-muted/50'
              }`}
            style={{
              backgroundColor: tempColorSchemaMode === 'custom'
                ? (previewColor1 && tempColorSchemaMode === 'custom'
                  ? previewColor1
                  : (theme === 'light' ? lightColors.color1 : darkColors.color1))
                : 'transparent'
            }}
          >
            <input
              type="radio"
              name="colorMode"
              value="custom"
              checked={tempColorSchemaMode === 'custom'}
              onChange={() => handleModeChange('custom')}
              className={tempColorSchemaMode === 'custom' ? 'text-white' : 'text-primary'}
            />
            <div>
              <div className={`font-medium ${tempColorSchemaMode === 'custom' ? 'text-white' : 'text-primary'}`}>
                Custom Colors
              </div>
              <div className={`text-sm ${tempColorSchemaMode === 'custom' ? 'text-white/80' : 'text-muted'}`}>
                Customize your own color palette
              </div>
            </div>
          </label>
        </div>
      </div>

      {/* Color Editing with Internal Theme Cards */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-6">
          <h4 className="text-md font-medium text-primary">
            {tempColorSchemaMode === 'custom' ? 'Customize Colors' : 'Colors (Read-Only)'}
          </h4>
          <span className="text-xs text-muted">
            {tempColorSchemaMode === 'custom' ? 'Edit colors for both light and dark themes' : 'Switch to Custom mode to edit colors'}
          </span>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Light Theme Card */}
          <div className="card bg-white border border-gray-200 p-4 rounded-lg shadow-sm">
            <div className="flex items-center space-x-2 mb-4">
              <div className="w-4 h-4 bg-yellow-400 rounded-full"></div>
              <h5 className="text-sm font-semibold text-gray-900">Light Theme Colors</h5>
            </div>
            <div className="grid grid-cols-5 gap-3">
              {Object.entries(lightColors).map(([colorKey, colorValue]) => (
                <div key={`light-${colorKey}`} className="text-center space-y-2">
                  <div className="relative">
                    <div
                      className={`w-16 h-16 mx-auto rounded-lg shadow-md transition-all ${tempColorSchemaMode === 'custom' ? 'cursor-pointer hover:scale-105' : 'cursor-not-allowed'
                        }`}
                      style={{ backgroundColor: colorValue as string }}
                      onClick={() => tempColorSchemaMode === 'custom' && document.getElementById(`light-${colorKey}-picker`)?.click()}
                      title={tempColorSchemaMode === 'custom' ? `Click to edit ${colorKey}` : 'Switch to Custom mode to edit'}
                    />
                    {tempColorSchemaMode === 'custom' && (
                      <input
                        id={`light-${colorKey}-picker`}
                        type="color"
                        value={colorValue as string}
                        onChange={(e) => handleColorChange('light', colorKey, e.target.value)}
                        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                      />
                    )}
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-gray-900 capitalize">{colorKey}</p>
                    <p className="text-xs text-gray-600 font-mono">{colorValue as string}</p>
                    <input
                      type="text"
                      value={colorValue as string}
                      onChange={(e) => handleColorChange('light', colorKey, e.target.value)}
                      disabled={tempColorSchemaMode === 'default'}
                      className={`w-full text-xs text-center border rounded px-2 py-1 font-mono transition-all ${tempColorSchemaMode === 'default'
                        ? 'bg-gray-100 text-gray-500 cursor-not-allowed opacity-60'
                        : 'bg-white text-gray-900 hover:border-blue-500 focus:border-blue-500 focus:ring-1 focus:ring-blue-500/20 focus:outline-none'
                        }`}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Dark Theme Card */}
          <div className="card bg-gray-900 border border-gray-700 p-4 rounded-lg shadow-sm">
            <div className="flex items-center space-x-2 mb-4">
              <div className="w-4 h-4 bg-gray-600 rounded-full"></div>
              <h5 className="text-sm font-semibold text-white">Dark Theme Colors</h5>
            </div>
            <div className="grid grid-cols-5 gap-3">
              {Object.entries(darkColors).map(([colorKey, colorValue]) => (
                <div key={`dark-${colorKey}`} className="text-center space-y-2">
                  <div className="relative">
                    <div
                      className={`w-16 h-16 mx-auto rounded-lg shadow-md transition-all ${tempColorSchemaMode === 'custom' ? 'cursor-pointer hover:scale-105' : 'cursor-not-allowed'
                        }`}
                      style={{ backgroundColor: colorValue as string }}
                      onClick={() => tempColorSchemaMode === 'custom' && document.getElementById(`dark-${colorKey}-picker`)?.click()}
                      title={tempColorSchemaMode === 'custom' ? `Click to edit ${colorKey}` : 'Switch to Custom mode to edit'}
                    />
                    {tempColorSchemaMode === 'custom' && (
                      <input
                        id={`dark-${colorKey}-picker`}
                        type="color"
                        value={colorValue as string}
                        onChange={(e) => handleColorChange('dark', colorKey, e.target.value)}
                        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                      />
                    )}
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-white capitalize">{colorKey}</p>
                    <p className="text-xs text-gray-400 font-mono">{colorValue as string}</p>
                    <input
                      type="text"
                      value={colorValue as string}
                      onChange={(e) => handleColorChange('dark', colorKey, e.target.value)}
                      disabled={tempColorSchemaMode === 'default'}
                      className={`w-full text-xs text-center border rounded px-2 py-1 font-mono transition-all ${tempColorSchemaMode === 'default'
                        ? 'bg-gray-800 text-gray-500 cursor-not-allowed opacity-60 border-gray-700'
                        : 'bg-gray-800 text-white hover:border-blue-400 focus:border-blue-400 focus:ring-1 focus:ring-blue-400/20 focus:outline-none border-gray-600'
                        }`}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Calculated Color Variants - Regular Accessibility */}
      <div className="card p-6">
        <h4 className="text-md font-medium text-primary mb-4">Calculated Color Variants - Regular</h4>
        <p className="text-sm text-muted mb-6">
          These colors are automatically calculated from your base colors to ensure optimal contrast and accessibility.
        </p>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Light Theme Variants Card */}
          <div className="card bg-white border border-gray-200 p-4 rounded-lg shadow-sm">
            <h5 className="text-sm font-semibold text-gray-900 mb-4">Light Theme Variants</h5>

            {/* On Colors */}
            <div className="space-y-3 mb-4">
              <h6 className="text-xs font-medium text-gray-700">Text Colors (On Colors)</h6>
              <div className="grid grid-cols-5 gap-2">
                {[1, 2, 3, 4, 5].map((num) => (
                  <div key={`light-on-${num}`} className="text-center">
                    <div
                      className="w-12 h-12 mx-auto rounded shadow-sm flex items-center justify-center text-xs font-bold"
                      style={{
                        backgroundColor: lightColors[`color${num}`],
                        color: lightVariants[`on_color${num}`] || '#000000'
                      }}
                    >
                      Aa
                    </div>
                    <p className="text-xs text-gray-600 mt-1 font-mono">{lightVariants[`on_color${num}`] || 'N/A'}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Gradient Colors */}
            <div className="space-y-3">
              <h6 className="text-xs font-medium text-gray-700">Gradient Text Colors</h6>
              <div className="grid grid-cols-5 gap-2">
                {[
                  { key: 'on_gradient_1_2', from: 'color1', to: 'color2' },
                  { key: 'on_gradient_2_3', from: 'color2', to: 'color3' },
                  { key: 'on_gradient_3_4', from: 'color3', to: 'color4' },
                  { key: 'on_gradient_4_5', from: 'color4', to: 'color5' },
                  { key: 'on_gradient_5_1', from: 'color5', to: 'color1' }
                ].map((gradient) => (
                  <div key={`light-${gradient.key}`} className="text-center">
                    <div
                      className="w-12 h-12 mx-auto rounded shadow-sm flex items-center justify-center text-xs font-bold"
                      style={{
                        background: `linear-gradient(45deg, ${lightColors[gradient.from]}, ${lightColors[gradient.to]})`,
                        color: lightVariants[gradient.key] || '#000000'
                      }}
                    >
                      Aa
                    </div>
                    <p className="text-xs text-gray-600 mt-1 font-mono">{lightVariants[gradient.key] || 'N/A'}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Dark Theme Variants Card */}
          <div className="card bg-gray-900 border border-gray-700 p-4 rounded-lg shadow-sm">
            <h5 className="text-sm font-semibold text-white mb-4">Dark Theme Variants</h5>

            {/* On Colors */}
            <div className="space-y-3 mb-4">
              <h6 className="text-xs font-medium text-gray-300">Text Colors (On Colors)</h6>
              <div className="grid grid-cols-5 gap-2">
                {[1, 2, 3, 4, 5].map((num) => (
                  <div key={`dark-on-${num}`} className="text-center">
                    <div
                      className="w-12 h-12 mx-auto rounded shadow-sm flex items-center justify-center text-xs font-bold"
                      style={{
                        backgroundColor: darkColors[`color${num}`],
                        color: darkVariants[`on_color${num}`] || '#FFFFFF'
                      }}
                    >
                      Aa
                    </div>
                    <p className="text-xs text-gray-400 mt-1 font-mono">{darkVariants[`on_color${num}`] || 'N/A'}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Gradient Colors */}
            <div className="space-y-3">
              <h6 className="text-xs font-medium text-gray-300">Gradient Text Colors</h6>
              <div className="grid grid-cols-5 gap-2">
                {[
                  { key: 'on_gradient_1_2', from: 'color1', to: 'color2' },
                  { key: 'on_gradient_2_3', from: 'color2', to: 'color3' },
                  { key: 'on_gradient_3_4', from: 'color3', to: 'color4' },
                  { key: 'on_gradient_4_5', from: 'color4', to: 'color5' },
                  { key: 'on_gradient_5_1', from: 'color5', to: 'color1' }
                ].map((gradient) => (
                  <div key={`dark-${gradient.key}`} className="text-center">
                    <div
                      className="w-12 h-12 mx-auto rounded shadow-sm flex items-center justify-center text-xs font-bold"
                      style={{
                        background: `linear-gradient(45deg, ${darkColors[gradient.from]}, ${darkColors[gradient.to]})`,
                        color: darkVariants[gradient.key] || '#FFFFFF'
                      }}
                    >
                      Aa
                    </div>
                    <p className="text-xs text-gray-400 mt-1 font-mono">{darkVariants[gradient.key] || 'N/A'}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Calculated Color Variants - AA Accessibility */}
      <div className="card p-6">
        <h4 className="text-md font-medium text-primary mb-4">Calculated Color Variants - AA Accessibility</h4>
        <p className="text-sm text-muted mb-6">
          Enhanced contrast colors meeting WCAG AA accessibility standards (4.5:1 contrast ratio).
        </p>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Light Theme AA Variants Card */}
          <div className="card bg-white border border-gray-200 p-4 rounded-lg shadow-sm">
            <h5 className="text-sm font-semibold text-gray-900 mb-4">Light Theme AA Variants</h5>

            {/* On Colors */}
            <div className="space-y-3 mb-4">
              <h6 className="text-xs font-medium text-gray-700">Text Colors (On Colors)</h6>
              <div className="grid grid-cols-5 gap-2">
                {[1, 2, 3, 4, 5].map((num) => (
                  <div key={`light-aa-on-${num}`} className="text-center">
                    <div
                      className="w-12 h-12 mx-auto rounded shadow-sm flex items-center justify-center text-xs font-bold"
                      style={{
                        backgroundColor: lightColors[`color${num}`],
                        color: lightVariantsAA[`on_color${num}`] || '#000000'
                      }}
                    >
                      Aa
                    </div>
                    <p className="text-xs text-gray-600 mt-1 font-mono">{lightVariantsAA[`on_color${num}`] || 'N/A'}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Gradient Colors */}
            <div className="space-y-3">
              <h6 className="text-xs font-medium text-gray-700">Gradient Text Colors</h6>
              <div className="grid grid-cols-5 gap-2">
                {[
                  { key: 'on_gradient_1_2', from: 'color1', to: 'color2' },
                  { key: 'on_gradient_2_3', from: 'color2', to: 'color3' },
                  { key: 'on_gradient_3_4', from: 'color3', to: 'color4' },
                  { key: 'on_gradient_4_5', from: 'color4', to: 'color5' },
                  { key: 'on_gradient_5_1', from: 'color5', to: 'color1' }
                ].map((gradient) => (
                  <div key={`light-aa-${gradient.key}`} className="text-center">
                    <div
                      className="w-12 h-12 mx-auto rounded shadow-sm flex items-center justify-center text-xs font-bold"
                      style={{
                        background: `linear-gradient(45deg, ${lightColors[gradient.from]}, ${lightColors[gradient.to]})`,
                        color: lightVariantsAA[gradient.key] || '#000000'
                      }}
                    >
                      Aa
                    </div>
                    <p className="text-xs text-gray-600 mt-1 font-mono">{lightVariantsAA[gradient.key] || 'N/A'}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Dark Theme AA Variants Card */}
          <div className="card bg-gray-900 border border-gray-700 p-4 rounded-lg shadow-sm">
            <h5 className="text-sm font-semibold text-white mb-4">Dark Theme AA Variants</h5>

            {/* On Colors */}
            <div className="space-y-3 mb-4">
              <h6 className="text-xs font-medium text-gray-300">Text Colors (On Colors)</h6>
              <div className="grid grid-cols-5 gap-2">
                {[1, 2, 3, 4, 5].map((num) => (
                  <div key={`dark-aa-on-${num}`} className="text-center">
                    <div
                      className="w-12 h-12 mx-auto rounded shadow-sm flex items-center justify-center text-xs font-bold"
                      style={{
                        backgroundColor: darkColors[`color${num}`],
                        color: darkVariantsAA[`on_color${num}`] || '#FFFFFF'
                      }}
                    >
                      Aa
                    </div>
                    <p className="text-xs text-gray-400 mt-1 font-mono">{darkVariantsAA[`on_color${num}`] || 'N/A'}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Gradient Colors */}
            <div className="space-y-3">
              <h6 className="text-xs font-medium text-gray-300">Gradient Text Colors</h6>
              <div className="grid grid-cols-5 gap-2">
                {[
                  { key: 'on_gradient_1_2', from: 'color1', to: 'color2' },
                  { key: 'on_gradient_2_3', from: 'color2', to: 'color3' },
                  { key: 'on_gradient_3_4', from: 'color3', to: 'color4' },
                  { key: 'on_gradient_4_5', from: 'color4', to: 'color5' },
                  { key: 'on_gradient_5_1', from: 'color5', to: 'color1' }
                ].map((gradient) => (
                  <div key={`dark-aa-${gradient.key}`} className="text-center">
                    <div
                      className="w-12 h-12 mx-auto rounded shadow-sm flex items-center justify-center text-xs font-bold"
                      style={{
                        background: `linear-gradient(45deg, ${darkColors[gradient.from]}, ${darkColors[gradient.to]})`,
                        color: darkVariantsAA[gradient.key] || '#FFFFFF'
                      }}
                    >
                      Aa
                    </div>
                    <p className="text-xs text-gray-400 mt-1 font-mono">{darkVariantsAA[gradient.key] || 'N/A'}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Calculated Color Variants - AAA Accessibility */}
      <div className="card p-6">
        <h4 className="text-md font-medium text-primary mb-4">Calculated Color Variants - AAA Accessibility</h4>
        <p className="text-sm text-muted mb-6">
          Maximum contrast colors meeting WCAG AAA accessibility standards (7:1 contrast ratio).
        </p>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Light Theme AAA Variants Card */}
          <div className="card bg-white border border-gray-200 p-4 rounded-lg shadow-sm">
            <h5 className="text-sm font-semibold text-gray-900 mb-4">Light Theme AAA Variants</h5>

            {/* On Colors */}
            <div className="space-y-3 mb-4">
              <h6 className="text-xs font-medium text-gray-700">Text Colors (On Colors)</h6>
              <div className="grid grid-cols-5 gap-2">
                {[1, 2, 3, 4, 5].map((num) => (
                  <div key={`light-aaa-on-${num}`} className="text-center">
                    <div
                      className="w-12 h-12 mx-auto rounded shadow-sm flex items-center justify-center text-xs font-bold"
                      style={{
                        backgroundColor: lightColors[`color${num}`],
                        color: lightVariantsAAA[`on_color${num}`] || '#000000'
                      }}
                    >
                      Aa
                    </div>
                    <p className="text-xs text-gray-600 mt-1 font-mono">{lightVariantsAAA[`on_color${num}`] || 'N/A'}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Gradient Colors */}
            <div className="space-y-3">
              <h6 className="text-xs font-medium text-gray-700">Gradient Text Colors</h6>
              <div className="grid grid-cols-5 gap-2">
                {[
                  { key: 'on_gradient_1_2', from: 'color1', to: 'color2' },
                  { key: 'on_gradient_2_3', from: 'color2', to: 'color3' },
                  { key: 'on_gradient_3_4', from: 'color3', to: 'color4' },
                  { key: 'on_gradient_4_5', from: 'color4', to: 'color5' },
                  { key: 'on_gradient_5_1', from: 'color5', to: 'color1' }
                ].map((gradient) => (
                  <div key={`light-aaa-${gradient.key}`} className="text-center">
                    <div
                      className="w-12 h-12 mx-auto rounded shadow-sm flex items-center justify-center text-xs font-bold"
                      style={{
                        background: `linear-gradient(45deg, ${lightColors[gradient.from]}, ${lightColors[gradient.to]})`,
                        color: lightVariantsAAA[gradient.key] || '#000000'
                      }}
                    >
                      Aa
                    </div>
                    <p className="text-xs text-gray-600 mt-1 font-mono">{lightVariantsAAA[gradient.key] || 'N/A'}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Dark Theme AAA Variants Card */}
          <div className="card bg-gray-900 border border-gray-700 p-4 rounded-lg shadow-sm">
            <h5 className="text-sm font-semibold text-white mb-4">Dark Theme AAA Variants</h5>

            {/* On Colors */}
            <div className="space-y-3 mb-4">
              <h6 className="text-xs font-medium text-gray-300">Text Colors (On Colors)</h6>
              <div className="grid grid-cols-5 gap-2">
                {[1, 2, 3, 4, 5].map((num) => (
                  <div key={`dark-aaa-on-${num}`} className="text-center">
                    <div
                      className="w-12 h-12 mx-auto rounded shadow-sm flex items-center justify-center text-xs font-bold"
                      style={{
                        backgroundColor: darkColors[`color${num}`],
                        color: darkVariantsAAA[`on_color${num}`] || '#FFFFFF'
                      }}
                    >
                      Aa
                    </div>
                    <p className="text-xs text-gray-400 mt-1 font-mono">{darkVariantsAAA[`on_color${num}`] || 'N/A'}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Gradient Colors */}
            <div className="space-y-3">
              <h6 className="text-xs font-medium text-gray-300">Gradient Text Colors</h6>
              <div className="grid grid-cols-5 gap-2">
                {[
                  { key: 'on_gradient_1_2', from: 'color1', to: 'color2' },
                  { key: 'on_gradient_2_3', from: 'color2', to: 'color3' },
                  { key: 'on_gradient_3_4', from: 'color3', to: 'color4' },
                  { key: 'on_gradient_4_5', from: 'color4', to: 'color5' },
                  { key: 'on_gradient_5_1', from: 'color5', to: 'color1' }
                ].map((gradient) => (
                  <div key={`dark-aaa-${gradient.key}`} className="text-center">
                    <div
                      className="w-12 h-12 mx-auto rounded shadow-sm flex items-center justify-center text-xs font-bold"
                      style={{
                        background: `linear-gradient(45deg, ${darkColors[gradient.from]}, ${darkColors[gradient.to]})`,
                        color: darkVariantsAAA[gradient.key] || '#FFFFFF'
                      }}
                    >
                      Aa
                    </div>
                    <p className="text-xs text-gray-400 mt-1 font-mono">{darkVariantsAAA[gradient.key] || 'N/A'}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  )
}
