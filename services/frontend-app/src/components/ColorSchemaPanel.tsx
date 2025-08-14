import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'

export default function ColorSchemaPanel() {
  const { theme, colorSchemaMode, setColorSchemaMode, saveColorSchemaMode, colorSchema, updateColorSchema, saveColorSchema } = useTheme()
  const { user } = useAuth()

  // Fix: Force DOM update when theme changes (keep this fix)
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  // CSS custom properties for dark mode (since Tailwind dark classes aren't working)
  const chartBg = theme === 'dark' ? '#1f2937' : '#f3f4f6' // gray-800 : gray-100
  const cardBg = theme === 'dark' ? '#1f2937' : '#f3f4f6'  // gray-800 : gray-100
  const textColor = theme === 'dark' ? '#f9fafb' : '#111827' // gray-50 : gray-900
  const mutedColor = theme === 'dark' ? '#9ca3af' : '#6b7280' // gray-400 : gray-600
  const [tempColorSchema, setTempColorSchema] = useState(colorSchema)
  const [tempColorSchemaMode, setTempColorSchemaMode] = useState(colorSchemaMode)
  const [hasChanges, setHasChanges] = useState(false)
  const [isSaving, setIsSaving] = useState(false)

  // Store database palettes explicitly (from server)
  const [databaseDefaultColors, setDatabaseDefaultColors] = useState<any>(colorSchema)
  const [databaseCustomColors, setDatabaseCustomColors] = useState<any>(colorSchema)
  // Back-compat: keep previous single databaseColors for preview logic when needed
  const [databaseColors, setDatabaseColors] = useState(colorSchema)
  // Store original database mode (immutable for comparison)
  const [databaseMode, setDatabaseMode] = useState(colorSchemaMode)
  // Track if colors have been changed (separate from mode changes)
  const [colorsChanged, setColorsChanged] = useState(false)
  // Track color definition mode (light/dark)
  const [tempColorDefinitionMode, setTempColorDefinitionMode] = useState('light')


  // Helper function to validate hex color format
  const isValidHexColor = (hex: string): boolean => {
    return /^#[0-9A-Fa-f]{6}$/.test(hex)
  }

  // Helper function to ensure valid hex color (fallback to default if invalid)
  const ensureValidHex = (hex: string, fallback: string = '#000000'): string => {
    return isValidHexColor(hex) ? hex : fallback
  }



  // Default colors (read-only)
  const defaultColors = {
    color1: '#C8102E',
    color2: '#253746',
    color3: '#00C7B1',
    color4: '#A2DDF8',
    color5: '#FFBF3F'
  }

  // Calculated color variants (read-only display)
  const calculatedVariants = [
    { category: 'On Colors', description: 'Optimal text colors for each base color', colors: ['on_color1', 'on_color2', 'on_color3', 'on_color4', 'on_color5'] },
    { category: 'Gradient Colors', description: 'Colors for gradient transitions (shows both on-color and gradient)', colors: ['on_gradient_1_2', 'on_gradient_2_3', 'on_gradient_3_4', 'on_gradient_4_5', 'on_gradient_5_1'] },
    { category: 'Adaptive Colors', description: 'Colors automatically adjusted for opposite theme mode (light↔dark)', colors: ['adaptive_color1', 'adaptive_color2', 'adaptive_color3', 'adaptive_color4', 'adaptive_color5'] }
  ]

  // Fetch color data from API on component mount
  useEffect(() => {
    const fetchColorData = async () => {
      try {
        const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001'}/api/v1/admin/color-schema`, {
          method: 'GET',
          credentials: 'include',
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('pulse_token') || ''}`
          }
        })

        if (response.ok) {
          const json = await response.json()
          if (json?.success) {
            if (json.default_colors) {
              console.log('🎨 Received default colors:', json.default_colors)
              setDatabaseDefaultColors(json.default_colors)
            }
            if (json.custom_colors) {
              console.log('🎨 Received custom colors:', json.custom_colors)
              setDatabaseCustomColors(json.custom_colors)
              // Initialize color definition mode from custom colors
              if (json.custom_colors.colors_defined_in_mode) {
                setTempColorDefinitionMode(json.custom_colors.colors_defined_in_mode)
              }
            }
          }
        }
      } catch (error) {
        console.error('Error fetching color data:', error)
      }
    }

    fetchColorData()
  }, [])

  // Update temp values when theme context changes
  useEffect(() => {
    setTempColorSchema(colorSchema)
    setTempColorSchemaMode(colorSchemaMode)
    setDatabaseColors(colorSchema)
    setDatabaseMode(colorSchemaMode)
  }, [colorSchema, colorSchemaMode])

  // Check for changes
  useEffect(() => {
    const modeChanged = tempColorSchemaMode !== databaseMode
    const hasChanges = modeChanged || colorsChanged
    setHasChanges(hasChanges)
  }, [tempColorSchemaMode, databaseMode, colorsChanged])

  // Reset function
  const handleReset = () => {
    setTempColorSchema(colorSchema)
    setTempColorSchemaMode(colorSchemaMode)
    setColorsChanged(false)
    setHasChanges(false)
  }

  const handleColorChange = (colorKey: string, newValue: string) => {
    setTempColorSchema(prev => ({
      ...prev,
      [colorKey]: newValue
    }))
    setColorsChanged(true)
    setHasChanges(true)

    // Do not update global ThemeContext colors during editing to avoid app-wide flashing.
    // Global CSS vars will be updated on Apply.
  }

  const handleColorDefinitionModeChange = (mode: 'light' | 'dark') => {
    setTempColorDefinitionMode(mode)
    setColorsChanged(true)
    setHasChanges(true)
  }

  const handleModeChange = (mode: 'default' | 'custom') => {
    setTempColorSchemaMode(mode)
    setHasChanges(true)
  }

  // Apply changes function
  const applyChanges = async () => {
    if (!hasChanges) return

    setIsSaving(true)
    try {
      // Save mode first
      let modeSuccess = true
      if (tempColorSchemaMode !== databaseMode) {
        setColorSchemaMode(tempColorSchemaMode)
        modeSuccess = await saveColorSchemaMode()
      }

      // Save colors only if in custom mode and colors changed
      let colorSuccess = true // Default to true for default mode

      if (tempColorSchemaMode === 'custom' && colorsChanged) {
        // Make direct API call to include color definition mode
        try {
          const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001'}/api/v1/admin/color-schema`, {
            method: 'POST',
            credentials: 'include',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${localStorage.getItem('pulse_token') || ''}`
            },
            body: JSON.stringify({
              colors: tempColorSchema,
              colors_defined_in_mode: tempColorDefinitionMode
            })
          })

          colorSuccess = response.status >= 200 && response.status < 300

          if (colorSuccess) {
            // Update ThemeContext with the new colors
            updateColorSchema(tempColorSchema)
          }
        } catch (error) {
          console.error('Error saving color schema:', error)
          colorSuccess = false
        }
      }

      if (modeSuccess && colorSuccess) {
        // Update database state to match current temp state
        setDatabaseMode(tempColorSchemaMode)
        setColorsChanged(false)
        setHasChanges(false)
        console.log('✅ Changes applied successfully')
      } else {
        console.error('❌ Failed to apply changes')
      }
    } catch (error) {
      console.error('Error applying changes:', error)
    } finally {
      setIsSaving(false)
    }
  }

  // Get current colors for display (either default or custom based on mode)
  const currentColors = tempColorSchemaMode === 'default' ? databaseDefaultColors : databaseCustomColors

  return (
    <motion.div
      className="space-y-8"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      {/* Color Schema Mode Selection */}
      <div className="card p-6 hover:shadow-lg transition-all duration-300">
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="text-xl font-bold text-primary">Color Schema Settings</h3>
            {hasChanges && (
              <div className="flex items-center space-x-3">
                <button
                  onClick={handleReset}
                  className="px-4 py-2 text-sm border border-default rounded-lg text-muted hover:text-secondary hover:border-gray-400 transition-colors"
                >
                  Reset
                </button>
                <button
                  onClick={applyChanges}
                  disabled={isSaving}
                  className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
                >
                  {isSaving ? 'Applying...' : 'Apply Changes'}
                </button>
              </div>
            )}
          </div>

          {/* Mode Selection */}
          <div className="space-y-4">
            <h4 className="text-md font-medium text-primary">Schema Mode</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <label className="flex items-center space-x-3 p-4 border border-default rounded-lg cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors">
                <input
                  type="radio"
                  name="colorMode"
                  value="default"
                  checked={tempColorSchemaMode === 'default'}
                  onChange={() => handleModeChange('default')}
                  className="text-blue-600"
                />
                <div>
                  <div className="font-medium text-primary">Default Colors</div>
                  <div className="text-sm text-muted">Use system default color palette</div>
                </div>
              </label>
              <label className="flex items-center space-x-3 p-4 border border-default rounded-lg cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors">
                <input
                  type="radio"
                  name="colorMode"
                  value="custom"
                  checked={tempColorSchemaMode === 'custom'}
                  onChange={() => handleModeChange('custom')}
                  className="text-blue-600"
                />
                <div>
                  <div className="font-medium text-primary">Custom Colors</div>
                  <div className="text-sm text-muted">Customize your own color palette</div>
                </div>
              </label>
            </div>
          </div>
        </div>
      </div>

      {/* Color Customization - Only for Custom Mode */}
      {tempColorSchemaMode === 'custom' && (
        <div className="card p-6 hover:shadow-lg transition-all duration-300">
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h4 className="text-md font-medium text-primary">Customize Base Colors</h4>
              <span className="text-xs text-muted">Only base colors can be edited</span>
            </div>

            {/* Color Definition Mode Selector */}
            <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg border border-yellow-200 dark:border-yellow-800">
              <div className="flex items-center justify-between mb-3">
                <h5 className="text-sm font-medium text-yellow-800 dark:text-yellow-200">Color Definition Mode</h5>
                <span className="text-xs text-yellow-600 dark:text-yellow-400">Affects adaptive color calculations</span>
              </div>
              <div className="flex items-center space-x-4">
                <label className="flex items-center space-x-2 cursor-pointer">
                  <input
                    type="radio"
                    name="colorDefinitionMode"
                    value="light"
                    checked={tempColorDefinitionMode === 'light'}
                    onChange={() => handleColorDefinitionModeChange('light')}
                    className="text-yellow-600"
                  />
                  <span className="text-sm text-yellow-800 dark:text-yellow-200">Light Mode</span>
                  <span className="text-xs text-yellow-600 dark:text-yellow-400">(adaptive colors will be lighter for dark theme)</span>
                </label>
                <label className="flex items-center space-x-2 cursor-pointer">
                  <input
                    type="radio"
                    name="colorDefinitionMode"
                    value="dark"
                    checked={tempColorDefinitionMode === 'dark'}
                    onChange={() => handleColorDefinitionModeChange('dark')}
                    className="text-yellow-600"
                  />
                  <span className="text-sm text-yellow-800 dark:text-yellow-200">Dark Mode</span>
                  <span className="text-xs text-yellow-600 dark:text-yellow-400">(adaptive colors will be darker for light theme)</span>
                </label>
              </div>
            </div>

            {/* Base Color Editors */}
            <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
              {Object.entries(defaultColors).map(([colorKey, defaultValue]) => {
                const currentValue = tempColorSchema[colorKey] || defaultValue
                const validColor = ensureValidHex(currentValue, defaultValue)

                return (
                  <div key={colorKey} className="text-center space-y-3">
                    <div className="relative">
                      <div
                        className="w-20 h-20 mx-auto rounded-xl shadow-md border border-default cursor-pointer hover:scale-105 transition-transform"
                        style={{ backgroundColor: validColor }}
                        onClick={() => document.getElementById(`color-input-${colorKey}`)?.click()}
                      />
                      <input
                        id={`color-input-${colorKey}`}
                        type="color"
                        value={validColor}
                        onChange={(e) => handleColorChange(colorKey, e.target.value)}
                        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                      />
                    </div>
                    <div className="space-y-1">
                      <p className="text-sm font-medium text-primary">{colorKey.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase())}</p>
                      <p className="text-xs text-muted font-mono">{validColor}</p>
                      <input
                        type="text"
                        value={currentValue}
                        onChange={(e) => handleColorChange(colorKey, e.target.value)}
                        className="w-full text-xs text-center border border-default rounded px-2 py-1 bg-transparent"
                        placeholder={defaultValue}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {/* Color Variants Display */}
      <div className="card p-6 hover:shadow-lg transition-all duration-300">
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h4 className="text-md font-medium text-primary">Calculated Color Variants</h4>
            <span className="text-xs text-muted">Auto-generated from base colors</span>
          </div>

          {calculatedVariants.map((variant, variantIndex) => (
            <div key={variantIndex} className="space-y-4">
              <div className="flex items-center justify-between">
                <h5 className="text-sm font-semibold text-secondary">{variant.category}</h5>
                <span className="text-xs text-muted">{variant.description}</span>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                {variant.colors.map((colorKey) => {
                  const colorValue = currentColors?.[colorKey]
                  const isAvailable = colorValue && colorValue !== 'N/A'

                  // Special handling for gradient colors
                  if (colorKey.includes('gradient')) {
                    const gradientMatch = colorKey.match(/on_gradient_(\d)_(\d)/)
                    if (gradientMatch) {
                      const fromColorKey = `color${gradientMatch[1]}`
                      const toColorKey = `color${gradientMatch[2]}`
                      const fromColorValue = currentColors?.[fromColorKey] || defaultColors[fromColorKey]
                      const toColorValue = currentColors?.[toColorKey] || defaultColors[toColorKey]

                      return (
                        <div key={colorKey} className="text-center space-y-2">
                          {/* Actual gradient on top */}
                          <div
                            className="w-16 h-8 mx-auto rounded-t-xl shadow-md border border-default"
                            style={{
                              background: `linear-gradient(90deg, ${fromColorValue} 0%, ${toColorValue} 100%)`
                            }}
                            title={`Gradient: ${fromColorValue} → ${toColorValue}`}
                          />
                          {/* On-color for gradient on bottom */}
                          <div
                            className={`w-16 h-8 mx-auto rounded-b-xl shadow-md border border-default relative ${!isAvailable ? 'opacity-50' : ''}`}
                            style={{ backgroundColor: colorValue }}
                            title={`${colorKey}: ${colorValue}${!isAvailable ? ' (Not available)' : ''}`}
                          >
                            {!isAvailable && (
                              <div className="absolute inset-0 flex items-center justify-center">
                                <span className="text-xs text-gray-600">N/A</span>
                              </div>
                            )}
                          </div>
                          <div className="space-y-1">
                            <p className="text-xs font-medium text-primary">{colorKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</p>
                            <p className="text-xs text-muted font-mono">{isAvailable ? colorValue : 'Not calculated'}</p>
                            <p className="text-xs text-muted">On-Color</p>
                          </div>
                        </div>
                      )
                    }
                  }

                  // Regular color display
                  return (
                    <div key={colorKey} className="text-center space-y-2">
                      <div
                        className={`w-16 h-16 mx-auto rounded-xl shadow-md border border-default relative ${!isAvailable ? 'opacity-50' : ''}`}
                        style={{ backgroundColor: isAvailable ? colorValue : '#f3f4f6' }}
                        title={`${colorKey}: ${colorValue}${!isAvailable ? ' (Not available)' : ''}`}
                      >
                        {!isAvailable && (
                          <div className="absolute inset-0 flex items-center justify-center">
                            <span className="text-xs text-gray-600">N/A</span>
                          </div>
                        )}
                      </div>
                      <div className="space-y-1">
                        <p className="text-xs font-medium text-primary">{colorKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</p>
                        <p className="text-xs text-muted font-mono">{isAvailable ? colorValue : 'Not calculated'}</p>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  )
}
