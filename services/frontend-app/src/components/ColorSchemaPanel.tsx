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


  // Helper function to validate hex color format
  const isValidHexColor = (hex: string): boolean => {
    return /^#[0-9A-Fa-f]{6}$/.test(hex)
  }

  // Helper function to ensure valid hex color (fallback to default if invalid)
  const ensureValidHex = (hex: string, fallback: string = '#000000'): string => {
    return isValidHexColor(hex) ? hex : fallback
  }



  // Default colors (read-only)
  const defaultColors = [
    { label: 'Color 1', value: databaseDefaultColors.color1, description: 'Blue - Primary' },
    { label: 'Color 2', value: databaseDefaultColors.color2, description: 'Purple - Secondary' },
    { label: 'Color 3', value: databaseDefaultColors.color3, description: 'Emerald - Success' },
    { label: 'Color 4', value: databaseDefaultColors.color4, description: 'Sky Blue - Info' },
    { label: 'Color 5', value: databaseDefaultColors.color5, description: 'Amber - Warning' }
  ]

  // Custom colors (from database - always show original database values, never preview values)
  const customColors = [
    { label: 'Color 1', value: databaseCustomColors.color1, description: 'Custom Red - Primary' },
    { label: 'Color 2', value: databaseCustomColors.color2, description: 'Custom Blue - Secondary' },
    { label: 'Color 3', value: databaseCustomColors.color3, description: 'Custom Teal - Success' },
    { label: 'Color 4', value: databaseCustomColors.color4, description: 'Custom Light Blue - Info' },
    { label: 'Color 5', value: databaseCustomColors.color5, description: 'Custom Yellow - Warning' }
  ]

  // Editable color inputs (for custom mode)
  const colorInputs = [
    { key: 'color1', label: 'Color 1', description: 'Primary brand color' },
    { key: 'color2', label: 'Color 2', description: 'Secondary color' },
    { key: 'color3', label: 'Color 3', description: 'Success/accent color' },
    { key: 'color4', label: 'Color 4', description: 'Info/highlight color' },
    { key: 'color5', label: 'Color 5', description: 'Warning/attention color' }
  ]

  // Initialize database values when component mounts
  useEffect(() => {
    setDatabaseColors(colorSchema)
    setDatabaseMode(colorSchemaMode)
    setTempColorSchema(colorSchema)
    setTempColorSchemaMode(colorSchemaMode)
  }, []) // Run only on mount

  // Ingest palettes from user context (explicit default/custom) and fallback to API fetch if missing
  useEffect(() => {
    const data: any = user?.colorSchemaData
    if (data) {
      if (data.default_colors) setDatabaseDefaultColors(data.default_colors)
      if (data.custom_colors) setDatabaseCustomColors(data.custom_colors)
    }

    // Fallback: fetch explicit sets if not present (supports sessions created before API change)
    if (!data?.default_colors || !data?.custom_colors) {
      (async () => {
        try {
          const res = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001'}/api/v1/admin/color-schema`, {
            credentials: 'include',
            headers: { 'Authorization': `Bearer ${localStorage.getItem('pulse_token') || ''}` }
          })
          const json = await res.json()
          if (json?.success) {
            if (json.default_colors) setDatabaseDefaultColors(json.default_colors)
            if (json.custom_colors) setDatabaseCustomColors(json.custom_colors)
          }
        } catch (e) {
          console.warn('Failed to fetch explicit palettes for panel:', e)
        }
      })()
    }
  }, [user?.colorSchemaData])

  // When ThemeContext colors update due to server fetch, keep databaseColors in sync
  useEffect(() => {
    setDatabaseColors(colorSchema)
  }, [colorSchema])

  // Sync temp states with actual states when they change (only from external sources, not preview)
  useEffect(() => {
    // Only reset states when this is NOT a preview change
    // Preview changes come from handleColorChange/handleModeChange and should not reset flags
    const isPreviewChange = hasChanges || colorsChanged

    if (!isPreviewChange) {
      setTempColorSchema(colorSchema)
      setDatabaseColors(colorSchema)
    }
  }, [colorSchema]) // Removed colorSchemaMode dependency to prevent database mode updates during preview

  // Separate useEffect for initial mode sync (only when external mode changes, not preview)
  useEffect(() => {
    // Only update database mode when there are no pending changes (external change)
    if (!hasChanges && !colorsChanged) {
      setTempColorSchemaMode(colorSchemaMode)
      setDatabaseMode(colorSchemaMode)
    }
  }, [colorSchemaMode]) // Only respond to actual mode changes from external sources

  const handleColorChange = (colorKey: string, raw: string) => {
    // Normalize user input for a smoother UX: allow paste with or without '#', strip non-hex chars,
    // and clamp to 7 chars (# + RRGGBB). Keep partial inputs in the textbox; only preview when valid.
    let value = raw.trim()
    // Auto-prepend '#'
    if (!value.startsWith('#')) value = '#' + value
    // Remove any non-hex characters after '#'
    value = '#' + value.slice(1).replace(/[^0-9A-Fa-f]/g, '')
    // Clamp to # + 6 hex digits
    if (value.length > 7) value = value.slice(0, 7)

    // If no real change (case-insensitive), bail to avoid redundant state updates and flashes
    const current = (colorsChanged ? (tempColorSchema[colorKey as keyof typeof tempColorSchema] as string) : (databaseCustomColors[colorKey as keyof typeof databaseCustomColors] as string)) || ''
    if (value.toLowerCase() === (current || '').toLowerCase()) {
      return
    }

    // On first edit, prime the temp schema from databaseCustomColors to avoid resetting others to defaults
    setTempColorSchema(prev => {
      const base = (!colorsChanged && tempColorSchemaMode === 'custom') ? databaseCustomColors : prev
      return { ...base, [colorKey]: value }
    })
    setHasChanges(true)
    setColorsChanged(true)

    // Do not update global ThemeContext colors during editing to avoid app-wide flashing.
    // Global CSS vars will be updated on Apply.
  }

  const handleModeChange = (mode: 'default' | 'custom') => {
    // No-op if clicking the already active mode to prevent unnecessary re-applies and flashing
    if (mode === colorSchemaMode) return

    setTempColorSchemaMode(mode)
    // Apply visual preview immediately for UI feedback
    setColorSchemaMode(mode)

    // When switching modes, also set the active color schema to the matching database palette
    // so that subsequent edits merge into the correct base instead of mixing with defaults
    if (mode === 'custom') {
      updateColorSchema(databaseCustomColors)
    } else {
      updateColorSchema(databaseDefaultColors)
    }

    // Update hasChanges based on whether mode changed from database
    const modeChanged = mode !== databaseMode
    setHasChanges(modeChanged || colorsChanged)

    // Reset colorsChanged when switching modes (fresh start for color editing)
    setColorsChanged(false)

    // Note: Don't update databaseMode here - that only changes when Apply is clicked
  }

  const applyChanges = async () => {
    setIsSaving(true)
    try {
      // Save mode if it changed
      const originalDatabaseMode = databaseMode
      if (tempColorSchemaMode !== originalDatabaseMode) {
        const modeSuccess = await saveColorSchemaMode(tempColorSchemaMode)
        if (!modeSuccess) {
          alert('Failed to save color schema mode to database')
          setIsSaving(false)
          return
        }
      }

      // Save colors only if in custom mode and colors changed
      let colorSuccess = true // Default to true for default mode

      if (tempColorSchemaMode === 'custom' && colorsChanged) {
        updateColorSchema(tempColorSchema)
        colorSuccess = await saveColorSchema()
      }

      if (colorSuccess) {
        // Immediately reflect saved palette in panel preview without needing a full refresh
        const saved = tempColorSchema
        setDatabaseColors(saved)
        setDatabaseCustomColors(saved)
        setTempColorSchema(saved)
        setHasChanges(false)
        setColorsChanged(false)
        setDatabaseMode(tempColorSchemaMode)
        // Force a refresh from server so ThemeContext updates CSS vars and on-colors
        try {
          const res = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001'}/api/v1/admin/color-schema`, {
            credentials: 'include',
            headers: {
              'Authorization': `Bearer ${localStorage.getItem('pulse_token') || ''}`
            }
          })
          const data = await res.json()
          if (data?.success) {
            // Update storage so ThemeContext picks it up immediately
            localStorage.setItem('pulse_color_schema_mode', data.mode)
            localStorage.setItem('pulse_colors', JSON.stringify(data.colors))
            document.documentElement.setAttribute('data-color-schema', data.mode)
            // Sync explicit sets used by this panel's preview
            if (data.custom_colors) setDatabaseCustomColors(data.custom_colors)
            if (data.default_colors) setDatabaseDefaultColors(data.default_colors)
          }
        } catch (e) {
          console.warn('Post-save color schema refresh failed:', e)
        }
      } else {
        alert('Failed to save color schema to database')
      }
    } catch (error) {
      console.error('Error saving color schema:', error)
      alert('Failed to save color schema')
    } finally {
      setIsSaving(false)
    }
  }



  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.8 }}
      className="space-y-6"
    >

      {/* Global Apply/Discard removed - using individual Apply buttons instead */}

      {/* Color Schema Mode Selection */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-primary">Color Schema Mode</h3>
          <span className="text-sm text-muted">Choose your color system</span>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <button
            onClick={() => handleModeChange('default')}
            disabled={isSaving}
            className={`p-4 rounded-lg border-2 transition-all disabled:opacity-50 ${tempColorSchemaMode === 'default'
              ? 'border-color-1 bg-color-1 bg-opacity-10'
              : 'border-default hover:border-color-1'
              }`}
          >
            <h4 className={`font-medium mb-2 ${tempColorSchemaMode === 'default' ? '' : 'text-primary'}`} style={tempColorSchemaMode === 'default' ? { color: 'var(--on-color-1)' } : undefined}>Default Colors</h4>
            <p className={`text-sm mb-3 ${tempColorSchemaMode === 'default' ? '' : 'text-secondary'}`} style={tempColorSchemaMode === 'default' ? { color: 'color-mix(in oklab, var(--on-color-1) 80%, transparent)' } : undefined}>Use built-in theme colors</p>
            <div className="flex space-x-1">
              {defaultColors.map((color, index) => (
                <div
                  key={index}
                  className="w-6 h-6 rounded border border-default"
                  style={{ backgroundColor: color.value }}
                />
              ))}
            </div>
          </button>

          <button
            onClick={() => handleModeChange('custom')}
            disabled={isSaving}
            className={`p-4 rounded-lg border-2 transition-all disabled:opacity-50 ${tempColorSchemaMode === 'custom'
              ? ''
              : 'border-default hover:border-color-1'
              }`}
            style={tempColorSchemaMode === 'custom' ? {
              borderColor: databaseCustomColors.color1,
              backgroundColor: databaseCustomColors.color1,
              color: 'var(--on-color-1)'
            } : {}}
          >
            <h4 className={`font-medium mb-2 ${tempColorSchemaMode === 'custom' ? '' : 'text-primary'}`}
              style={tempColorSchemaMode === 'custom' ? { color: 'var(--on-color-1)' } : undefined}>Custom Colors</h4>
            <p className={`text-sm mb-3 ${tempColorSchemaMode === 'custom' ? '' : 'text-secondary'}`}
              style={tempColorSchemaMode === 'custom' ? { color: 'color-mix(in oklab, var(--on-color-1) 80%, transparent)' } : undefined}>Use custom database colors</p>
            <div className="flex space-x-1">
              {customColors.map((color, index) => (
                <div
                  key={index}
                  className="w-6 h-6 rounded border border-default"
                  style={{
                    backgroundColor: color.value  // Always show database values
                  }}
                />
              ))}
            </div>
          </button>
        </div>
      </div>

      {/* 5-Color Schema Section */}
      <div className="card p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <h3 className="text-lg font-semibold text-primary">
              {tempColorSchemaMode === 'default' ? 'Default' : 'Custom'} 5-Color Schema
            </h3>
            <div className="flex items-center space-x-3" style={{ visibility: 'hidden' }}>
              <span className="text-xs px-2 py-1 rounded text-white" style={{ backgroundColor: 'var(--color-1)' }}>
                Preview: {tempColorSchemaMode === 'default' ? 'Default Colors' : 'Custom Colors'}
              </span>
              <span className="text-xs px-2 py-1 rounded text-white" style={{ backgroundColor: 'var(--color-2)' }}>
                Database: {databaseMode || 'loading...'}
              </span>
              <span className="text-xs px-2 py-1 rounded text-white" style={{ backgroundColor: 'var(--color-3)' }}>
                Colors Changed: {colorsChanged ? 'Yes' : 'No'}
              </span>
            </div>
          </div>
          <div className="flex items-center space-x-3">
            {(() => {
              // Show Apply button when there are any differences from database
              const modeChanged = tempColorSchemaMode !== databaseMode

              // Always show Apply button if there are any changes (simplified logic)
              const shouldShowApply = hasChanges || modeChanged || colorsChanged



              return shouldShowApply ? (
                <button
                  onClick={applyChanges}
                  disabled={isSaving}
                  className="bg-blue-600 hover:bg-blue-700 text-white font-medium px-4 py-2 rounded-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  style={{
                    backgroundColor: '#2563eb',
                    color: '#ffffff'
                  }}
                >
                  {isSaving ? 'Applying...' : 'Apply Changes'}
                </button>
              ) : null
            })()}
          </div>
        </div>

        {/* Color Preview */}
        <div className="grid grid-cols-5 gap-4">
          {(tempColorSchemaMode === 'default' ? defaultColors : customColors).map((color, index) => (
            <div
              key={index}
              className="text-center space-y-2"
            >
              <div
                className="w-16 h-16 mx-auto rounded-xl shadow-md cursor-pointer transition-transform hover:scale-110"
                style={{
                  backgroundColor: (tempColorSchemaMode === 'custom')
                    ? (colorsChanged
                      ? (tempColorSchema[`color${index + 1}` as keyof typeof tempColorSchema] as string)
                      : (databaseCustomColors[`color${index + 1}` as keyof typeof databaseCustomColors] as string))
                    : (color.value as string)
                }}
              />
              <div>
                <p className="text-sm font-medium text-primary">{color.label}</p>
                <p className="text-xs text-muted">{color.description}</p>
                <p className="text-xs font-mono text-secondary">
                  {(tempColorSchemaMode === 'custom')
                    ? (colorsChanged
                      ? (tempColorSchema[`color${index + 1}` as keyof typeof tempColorSchema] as string)
                      : (databaseCustomColors[`color${index + 1}` as keyof typeof databaseCustomColors] as string))
                    : (color.value as string)}
                </p>
              </div>
            </div>
          ))}
        </div>

        {/* Color Customization - Only for Custom Mode */}
        {tempColorSchemaMode === 'custom' && (
          <div className="border-t border-default pt-6">
            <div className="flex items-center justify-between mb-4">
              <h4 className="text-md font-medium text-primary">Customize Colors</h4>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {colorInputs.map((color) => (
                <div key={color.key} className="space-y-3">
                  <label className="block text-sm font-medium text-primary">
                    {color.label}
                  </label>
                  <p className="text-xs text-muted">{color.description}</p>
                  <div className="flex space-x-3">
                    <input
                      type="color"
                      value={ensureValidHex((colorsChanged ? tempColorSchema[color.key as keyof typeof tempColorSchema] : databaseCustomColors[color.key as keyof typeof databaseCustomColors]) as string)}
                      onChange={(e) => handleColorChange(color.key, e.target.value)}
                      className="w-12 h-10 rounded-lg border border-default cursor-pointer"
                      disabled={tempColorSchemaMode !== 'custom'}
                    />
                    <input
                      type="text"
                      value={(colorsChanged ? tempColorSchema[color.key as keyof typeof tempColorSchema] : databaseCustomColors[color.key as keyof typeof databaseCustomColors]) as string}
                      onChange={(e) => handleColorChange(color.key, e.target.value)}
                      disabled={tempColorSchemaMode !== 'custom'}
                      className="input flex-1 text-sm"
                      placeholder="#000000"
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Read-only message for Default Mode */}
        {colorSchemaMode === 'default' && (
          <div className="border-t border-default pt-6">
            <div className="text-center p-6 bg-tertiary rounded-lg">
              <h4 className="text-md font-medium text-primary mb-2">Default Colors</h4>
              <p className="text-sm text-secondary">
                These are the built-in theme colors. Switch to "Custom Colors" mode to customize your own color palette.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Comprehensive Design System Showcase */}
      <div className="space-y-8">
        <h3 className="text-xl font-bold text-primary">Complete Design System Showcase</h3>

        {/* Search & Filters Row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Advanced Search */}
          <motion.div
            className="card p-6"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            <div className="space-y-4">
              <h4 className="text-md font-semibold text-primary">Search System</h4>
              <div className="relative">
                <input
                  type="text"
                  placeholder="Search repositories, users, issues..."
                  className="w-full pl-10 pr-4 py-3 rounded-lg border-2 focus:outline-none transition-all placeholder-gray-400"
                  style={{
                    backgroundColor: cardBg,
                    color: textColor,
                    borderColor: 'var(--color-1)'
                  }}
                />
                <div className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 dark:text-gray-500">
                  🔍
                </div>
                <button className="absolute right-2 top-1/2 transform -translate-y-1/2 px-3 py-1 rounded text-white text-sm hover:opacity-90 transition-opacity" style={{ backgroundColor: 'var(--color-1)' }}>
                  Search
                </button>
              </div>
              <div className="flex flex-wrap gap-2">
                {['Recent', 'Popular', 'Trending'].map((tag, index) => (
                  <span key={index} className="px-3 py-1 rounded-full text-white text-xs" style={{ backgroundColor: `var(--color-${index + 3})` }}>
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          </motion.div>

          {/* Filter System */}
          <motion.div
            className="card p-6"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <div className="space-y-4">
              <h4 className="text-md font-semibold text-primary">Filter Controls</h4>
              <div className="space-y-3">
                <div>
                  <label className="text-sm text-secondary mb-1 block">Status</label>
                  <select
                    className="w-full p-2 rounded border"
                    style={{
                      backgroundColor: cardBg,
                      color: textColor,
                      borderColor: mutedColor
                    }}
                  >
                    <option>All Status</option>
                    <option>Active</option>
                    <option>Pending</option>
                    <option>Completed</option>
                  </select>
                </div>
                <div>
                  <label className="text-sm text-secondary mb-1 block">Date Range</label>
                  <div className="flex space-x-2">
                    <button className="flex-1 px-3 py-2 rounded text-white text-sm hover:opacity-90 transition-opacity" style={{ backgroundColor: 'var(--color-4)' }}>
                      Last 7 days
                    </button>
                    <button className="flex-1 px-3 py-2 rounded bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300 text-sm hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors">
                      Last 30 days
                    </button>
                  </div>
                </div>
                <div className="flex space-x-2">
                  <button className="px-3 py-1 rounded-full text-white text-xs hover:opacity-90 transition-opacity" style={{ backgroundColor: 'var(--color-1)' }}>
                    Apply Filters
                  </button>
                  <button className="px-3 py-1 rounded-full bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300 text-xs hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors">
                    Clear All
                  </button>
                </div>
              </div>
            </div>
          </motion.div>

          {/* Status System (Fixed) */}
          <motion.div
            className="card p-6"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
          >
            <div className="space-y-4">
              <h4 className="text-md font-semibold text-primary">Status Indicators</h4>
              <div className="space-y-3">
                <div className="flex items-center justify-between p-3 rounded-lg border-l-4" style={{ backgroundColor: cardBg, borderLeftColor: 'var(--color-3)' }}>
                  <div className="flex items-center space-x-3">
                    <div className="w-3 h-3 rounded-full" style={{ backgroundColor: 'var(--color-3)' }}></div>
                    <span className="text-sm font-medium" style={{ color: textColor }}>ETL Job Running</span>
                  </div>
                  <span className="text-xs px-2 py-1 rounded-full text-white font-medium" style={{ backgroundColor: 'var(--color-3)' }}>
                    Active
                  </span>
                </div>
                <div className="flex items-center justify-between p-3 rounded-lg border-l-4" style={{ backgroundColor: cardBg, borderLeftColor: 'var(--color-4)' }}>
                  <div className="flex items-center space-x-3">
                    <div className="w-3 h-3 rounded-full" style={{ backgroundColor: 'var(--color-4)' }}></div>
                    <span className="text-sm font-medium" style={{ color: textColor }}>Sync Pending</span>
                  </div>
                  <span className="text-xs px-2 py-1 rounded-full text-white font-medium" style={{ backgroundColor: 'var(--color-4)' }}>
                    Info
                  </span>
                </div>
                <div className="flex items-center justify-between p-3 rounded-lg border-l-4" style={{ backgroundColor: cardBg, borderLeftColor: 'var(--color-5)' }}>
                  <div className="flex items-center space-x-3">
                    <div className="w-3 h-3 rounded-full" style={{ backgroundColor: 'var(--color-5)' }}></div>
                    <span className="text-sm font-medium" style={{ color: textColor }}>Alert Triggered</span>
                  </div>
                  <span className="text-xs px-2 py-1 rounded-full text-white font-medium" style={{ backgroundColor: 'var(--color-5)' }}>
                    Warning
                  </span>
                </div>
              </div>
            </div>
          </motion.div>
        </div>

        {/* Advanced Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Gradient Bar Chart (like homepage-backup) */}
          <motion.div
            className="card p-6"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
          >
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="text-md font-semibold text-primary">DORA Metrics</h4>
                <div className="flex space-x-2">
                  <button className="px-3 py-1 text-xs rounded-full text-white" style={{ backgroundColor: 'var(--color-1)' }}>Live</button>
                  <button className="px-3 py-1 text-xs rounded-full bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400">Historical</button>
                </div>
              </div>
              <div className="h-40 flex items-end space-x-3">
                {[
                  { label: 'Deploy Freq', value: 85, gradient: 'linear-gradient(to top, var(--color-1), var(--color-2))' },
                  { label: 'Lead Time', value: 72, gradient: 'linear-gradient(to top, var(--color-2), var(--color-3))' },
                  { label: 'MTTR', value: 90, gradient: 'linear-gradient(to top, var(--color-3), var(--color-4))' },
                  { label: 'Change Fail', value: 65, gradient: 'linear-gradient(to top, var(--color-4), var(--color-5))' }
                ].map((metric, index) => (
                  <div key={index} className="flex-1 text-center">
                    <motion.div
                      className="rounded-t-lg relative mb-2"
                      style={{
                        background: metric.gradient,
                        height: `${metric.value}%`,
                        minHeight: '20px'
                      }}
                      initial={{ height: 0 }}
                      animate={{ height: `${metric.value}%` }}
                      transition={{ delay: 0.6 + index * 0.1, duration: 0.8 }}
                    >
                      <div className="absolute -top-6 left-1/2 transform -translate-x-1/2 text-xs font-bold text-primary">
                        {metric.value}%
                      </div>
                    </motion.div>
                    <div className="text-xs text-muted font-medium">{metric.label}</div>
                  </div>
                ))}
              </div>
              <div className="text-center">
                <div className="text-sm text-muted">DevOps Performance Indicators</div>
              </div>
            </div>
          </motion.div>
          {/* Heat Mapping */}
          <motion.div
            className="card p-6"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
          >
            <div className="space-y-4">
              <h4 className="text-md font-semibold text-primary">Activity Heatmap</h4>
              <div className="space-y-2">
                {[
                  { day: 'Mon', hours: [2, 4, 6, 8, 9, 7, 5, 3, 2, 1, 3, 5, 7, 9, 8, 6, 4, 2, 1, 2, 3, 4, 3, 2] },
                  { day: 'Tue', hours: [1, 3, 5, 7, 8, 9, 6, 4, 3, 2, 4, 6, 8, 9, 7, 5, 3, 1, 2, 3, 4, 5, 4, 3] },
                  { day: 'Wed', hours: [3, 5, 7, 9, 8, 6, 4, 2, 1, 3, 5, 7, 9, 8, 6, 4, 2, 3, 4, 5, 6, 7, 5, 4] },
                  { day: 'Thu', hours: [2, 4, 6, 8, 9, 7, 5, 3, 2, 4, 6, 8, 9, 7, 5, 3, 1, 2, 3, 4, 5, 6, 4, 3] },
                  { day: 'Fri', hours: [4, 6, 8, 9, 7, 5, 3, 1, 2, 4, 6, 8, 9, 7, 5, 3, 2, 4, 5, 6, 7, 8, 6, 5] },
                  { day: 'Sat', hours: [1, 2, 3, 4, 3, 2, 1, 2, 3, 4, 5, 4, 3, 2, 1, 2, 3, 4, 3, 2, 1, 2, 1, 1] },
                  { day: 'Sun', hours: [1, 1, 2, 3, 2, 1, 1, 2, 3, 4, 3, 2, 1, 2, 3, 2, 1, 2, 3, 2, 1, 1, 1, 1] }
                ].map((dayData, dayIndex) => (
                  <div key={dayIndex} className="flex items-center space-x-1">
                    <div className="w-8 text-xs text-muted font-medium">{dayData.day}</div>
                    <div className="flex space-x-0.5">
                      {dayData.hours.map((intensity, hourIndex) => (
                        <motion.div
                          key={hourIndex}
                          className="w-2 h-2 rounded-sm"
                          style={{
                            backgroundColor: intensity > 7 ? 'var(--color-1)' :
                              intensity > 5 ? 'var(--color-2)' :
                                intensity > 3 ? 'var(--color-3)' :
                                  intensity > 1 ? 'var(--color-4)' : 'var(--color-5)',
                            opacity: intensity * 0.1 + 0.1
                          }}
                          initial={{ scale: 0 }}
                          animate={{ scale: 1 }}
                          transition={{ delay: 0.7 + (dayIndex * 24 + hourIndex) * 0.005, duration: 0.2 }}
                        />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              <div className="flex justify-between text-xs text-muted">
                <span>12 AM</span>
                <span>6 AM</span>
                <span>12 PM</span>
                <span>6 PM</span>
                <span>11 PM</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted">Less activity</span>
                <div className="flex space-x-1">
                  {[1, 3, 5, 7, 9].map(intensity => (
                    <div
                      key={intensity}
                      className="w-3 h-3 rounded-sm"
                      style={{
                        backgroundColor: `var(--color-${Math.ceil(intensity / 2)})`,
                        opacity: intensity * 0.1 + 0.1
                      }}
                    />
                  ))}
                </div>
                <span className="text-muted">More activity</span>
              </div>
            </div>
          </motion.div>

          {/* Line Chart with Trends */}
          <motion.div
            className="card p-6"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6 }}
          >
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="text-md font-semibold text-primary">Performance Trends</h4>
                <div className="flex space-x-2">
                  <button className="px-3 py-1 text-xs rounded-full text-white" style={{ backgroundColor: 'var(--color-1)' }}>Live</button>
                  <button className="px-3 py-1 text-xs rounded-full bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400">Historical</button>
                </div>
              </div>
              <div className="h-40 relative">
                <svg className="w-full h-full" viewBox="0 0 300 120">
                  {/* Grid lines */}
                  {[0, 1, 2, 3, 4].map(i => (
                    <line key={i} x1="0" y1={i * 30} x2="300" y2={i * 30} stroke="currentColor" strokeOpacity="0.1" />
                  ))}
                  {/* Line 1 - Performance */}
                  <motion.path
                    d="M0,80 Q50,60 100,50 T200,40 T300,30"
                    fill="none"
                    stroke="var(--color-1)"
                    strokeWidth="3"
                    initial={{ pathLength: 0 }}
                    animate={{ pathLength: 1 }}
                    transition={{ delay: 0.6, duration: 2 }}
                  />
                  {/* Line 2 - Quality */}
                  <motion.path
                    d="M0,90 Q50,85 100,70 T200,60 T300,45"
                    fill="none"
                    stroke="var(--color-2)"
                    strokeWidth="3"
                    initial={{ pathLength: 0 }}
                    animate={{ pathLength: 1 }}
                    transition={{ delay: 0.8, duration: 2 }}
                  />
                  {/* Line 3 - Velocity */}
                  <motion.path
                    d="M0,100 Q50,95 100,85 T200,75 T300,65"
                    fill="none"
                    stroke="var(--color-3)"
                    strokeWidth="3"
                    initial={{ pathLength: 0 }}
                    animate={{ pathLength: 1 }}
                    transition={{ delay: 1, duration: 2 }}
                  />
                </svg>
                <div className="absolute bottom-0 left-0 right-0 flex justify-between text-xs text-muted">
                  <span>Jan</span>
                  <span>Mar</span>
                  <span>May</span>
                  <span>Jul</span>
                  <span>Sep</span>
                  <span>Nov</span>
                </div>
              </div>
              <div className="flex justify-center space-x-6 text-sm">
                <div className="flex items-center space-x-2">
                  <div className="w-3 h-0.5" style={{ backgroundColor: 'var(--color-1)' }}></div>
                  <span className="text-muted">Performance</span>
                </div>
                <div className="flex items-center space-x-2">
                  <div className="w-3 h-0.5" style={{ backgroundColor: 'var(--color-2)' }}></div>
                  <span className="text-muted">Quality</span>
                </div>
                <div className="flex items-center space-x-2">
                  <div className="w-3 h-0.5" style={{ backgroundColor: 'var(--color-3)' }}></div>
                  <span className="text-muted">Velocity</span>
                </div>
              </div>
            </div>
          </motion.div>

        </div>

        {/* Performance Trend & CFD Row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Performance Trend (from backup homepage) */}
          <motion.div
            className="card p-6"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.7 }}
          >
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="text-lg font-semibold text-primary">Performance Trend</h4>
                <div className="flex space-x-2">
                  <button className="px-3 py-1 text-xs rounded-full text-white hover:opacity-90 transition-opacity" style={{ backgroundColor: 'var(--color-1)' }}>7D</button>
                  <button className="px-3 py-1 text-xs rounded-full bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors">30D</button>
                </div>
              </div>

              {/* Performance metrics cards */}
              <div className="grid grid-cols-2 gap-4 mb-4">
                {[
                  { label: 'Throughput', value: '847', unit: 'req/min', change: '+12%', color: 'var(--color-1)' },
                  { label: 'Response Time', value: '245', unit: 'ms', change: '-8%', color: 'var(--color-2)' },
                  { label: 'Error Rate', value: '0.12', unit: '%', change: '-15%', color: 'var(--color-3)' },
                  { label: 'Uptime', value: '99.9', unit: '%', change: '+0.1%', color: 'var(--color-4)' }
                ].map((metric, index) => (
                  <motion.div
                    key={index}
                    className="p-3 rounded-lg border-l-4"
                    style={{
                      backgroundColor: cardBg,
                      borderLeftColor: metric.color
                    }}
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.9 + index * 0.1 }}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs" style={{ color: mutedColor }}>{metric.label}</span>
                      <span className="text-xs px-1 py-0.5 rounded text-white" style={{ backgroundColor: metric.color }}>
                        {metric.change}
                      </span>
                    </div>
                    <div className="flex items-baseline space-x-1">
                      <span className="text-xl font-bold" style={{ color: metric.color }}>{metric.value}</span>
                      <span className="text-xs" style={{ color: mutedColor }}>{metric.unit}</span>
                    </div>
                  </motion.div>
                ))}
              </div>

              {/* Area chart like homepage backup */}
              <div className="h-32 relative rounded-lg p-4" style={{ backgroundColor: chartBg }}>
                <svg className="w-full h-full" viewBox="0 0 300 100">
                  {/* Grid lines */}
                  {[0, 1, 2, 3, 4].map(i => (
                    <line key={i} x1="0" y1={i * 25} x2="300" y2={i * 25} stroke="currentColor" strokeOpacity="0.1" />
                  ))}

                  {/* Area fill with gradient */}
                  <defs>
                    <linearGradient id="performanceGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                      <stop offset="0%" style={{ stopColor: 'var(--color-1)', stopOpacity: 0.8 }} />
                      <stop offset="50%" style={{ stopColor: 'var(--color-2)', stopOpacity: 0.4 }} />
                      <stop offset="100%" style={{ stopColor: 'var(--color-3)', stopOpacity: 0.1 }} />
                    </linearGradient>
                  </defs>

                  {/* Area path */}
                  <motion.path
                    d="M0,80 Q50,70 100,60 T200,45 T300,35 L300,100 L0,100 Z"
                    fill="url(#performanceGradient)"
                    initial={{ pathLength: 0, opacity: 0 }}
                    animate={{ pathLength: 1, opacity: 1 }}
                    transition={{ delay: 1.3, duration: 2 }}
                  />

                  {/* Line on top */}
                  <motion.path
                    d="M0,80 Q50,70 100,60 T200,45 T300,35"
                    fill="none"
                    stroke="var(--color-1)"
                    strokeWidth="3"
                    initial={{ pathLength: 0 }}
                    animate={{ pathLength: 1 }}
                    transition={{ delay: 1.5, duration: 2 }}
                  />

                  {/* Data points */}
                  {[
                    { x: 0, y: 80 }, { x: 75, y: 65 }, { x: 150, y: 50 }, { x: 225, y: 40 }, { x: 300, y: 35 }
                  ].map((point, index) => (
                    <motion.circle
                      key={index}
                      cx={point.x}
                      cy={point.y}
                      r="4"
                      fill="var(--color-1)"
                      stroke="white"
                      strokeWidth="2"
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ delay: 1.7 + index * 0.1, duration: 0.3 }}
                    />
                  ))}
                </svg>
              </div>
            </div>
          </motion.div>

          {/* Cumulative Flow Diagram (CFD) */}
          <motion.div
            className="card p-6"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.8 }}
          >
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="text-lg font-semibold text-primary">Cumulative Flow Diagram</h4>
                <div className="flex space-x-2">
                  <button className="px-3 py-1 text-xs rounded-full text-white hover:opacity-90 transition-opacity" style={{ backgroundColor: 'var(--color-2)' }}>Sprint</button>
                  <button className="px-3 py-1 text-xs rounded-full bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors">Quarter</button>
                </div>
              </div>

              {/* CFD Legend */}
              <div className="flex justify-center space-x-4 text-xs">
                {[
                  { label: 'Backlog', color: 'var(--color-5)' },
                  { label: 'In Progress', color: 'var(--color-4)' },
                  { label: 'Review', color: 'var(--color-3)' },
                  { label: 'Testing', color: 'var(--color-2)' },
                  { label: 'Done', color: 'var(--color-1)' }
                ].map((item, index) => (
                  <div key={index} className="flex items-center space-x-1">
                    <div className="w-3 h-3 rounded" style={{ backgroundColor: item.color }}></div>
                    <span className="text-muted">{item.label}</span>
                  </div>
                ))}
              </div>

              {/* Larger Stacked area chart */}
              <div className="h-56 relative rounded-lg p-4" style={{ backgroundColor: chartBg }}>
                <svg className="w-full h-full" viewBox="0 0 320 160">
                  {/* Grid */}
                  {[0, 1, 2, 3, 4, 5].map(i => (
                    <line key={i} x1="0" y1={i * 32} x2="320" y2={i * 32} stroke="currentColor" strokeOpacity="0.1" />
                  ))}

                  {/* Stacked areas - Larger */}
                  {/* Done (bottom layer) */}
                  <motion.path
                    d="M0,160 L0,130 Q80,125 160,120 T320,115 L320,160 Z"
                    fill="var(--color-1)"
                    fillOpacity="0.8"
                    initial={{ pathLength: 0 }}
                    animate={{ pathLength: 1 }}
                    transition={{ delay: 1.2, duration: 1.5 }}
                  />

                  {/* Testing */}
                  <motion.path
                    d="M0,130 Q80,125 160,120 T320,115 Q320,105 160,100 T0,110 Z"
                    fill="var(--color-2)"
                    fillOpacity="0.8"
                    initial={{ pathLength: 0 }}
                    animate={{ pathLength: 1 }}
                    transition={{ delay: 1.4, duration: 1.5 }}
                  />

                  {/* Review */}
                  <motion.path
                    d="M0,110 Q80,105 160,100 T320,95 Q320,85 160,80 T0,90 Z"
                    fill="var(--color-3)"
                    fillOpacity="0.8"
                    initial={{ pathLength: 0 }}
                    animate={{ pathLength: 1 }}
                    transition={{ delay: 1.6, duration: 1.5 }}
                  />

                  {/* In Progress */}
                  <motion.path
                    d="M0,90 Q80,85 160,80 T320,75 Q320,60 160,55 T0,65 Z"
                    fill="var(--color-4)"
                    fillOpacity="0.8"
                    initial={{ pathLength: 0 }}
                    animate={{ pathLength: 1 }}
                    transition={{ delay: 1.8, duration: 1.5 }}
                  />

                  {/* Backlog (top layer) */}
                  <motion.path
                    d="M0,65 Q80,60 160,55 T320,50 Q320,30 160,25 T0,35 Z"
                    fill="var(--color-5)"
                    fillOpacity="0.8"
                    initial={{ pathLength: 0 }}
                    animate={{ pathLength: 1 }}
                    transition={{ delay: 2.0, duration: 1.5 }}
                  />

                  {/* Time labels */}
                  <text x="50" y="175" className="text-xs fill-gray-600 dark:fill-gray-300">Week 1</text>
                  <text x="140" y="175" className="text-xs fill-gray-600 dark:fill-gray-300">Week 2</text>
                  <text x="230" y="175" className="text-xs fill-gray-600 dark:fill-gray-300">Week 3</text>
                  <text x="300" y="175" className="text-xs fill-gray-600 dark:fill-gray-300">Week 4</text>
                </svg>
              </div>

              {/* Enhanced CFD Insights */}
              <div className="grid grid-cols-2 gap-4">
                {[
                  { label: 'Avg Cycle Time', value: '4.2', unit: 'days', desc: 'From start to done', color: 'var(--color-1)' },
                  { label: 'WIP Limit', value: '23', unit: 'items', desc: 'Work in progress', color: 'var(--color-2)' },
                  { label: 'Throughput', value: '12', unit: '/week', desc: 'Items completed', color: 'var(--color-3)' },
                  { label: 'Lead Time', value: '6.8', unit: 'days', desc: 'Request to delivery', color: 'var(--color-4)' }
                ].map((metric, index) => (
                  <motion.div
                    key={index}
                    className="p-4 rounded-lg border-l-4"
                    style={{
                      backgroundColor: cardBg,
                      borderLeftColor: metric.color
                    }}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 2.5 + index * 0.1 }}
                  >
                    <div className="flex items-baseline space-x-1 mb-1">
                      <span className="text-xl font-bold" style={{ color: metric.color }}>{metric.value}</span>
                      <span className="text-sm" style={{ color: mutedColor }}>{metric.unit}</span>
                    </div>
                    <div className="text-sm font-medium mb-1" style={{ color: textColor }}>{metric.label}</div>
                    <div className="text-xs" style={{ color: mutedColor }}>{metric.desc}</div>
                  </motion.div>
                ))}
              </div>
            </div>
          </motion.div>
        </div>

        {/* Advanced Analytics Row */}
        <div className="grid grid-cols-1 gap-6">
          {/* Full-Width Histogram with Statistical Lines */}
          <motion.div
            className="card p-6"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.7 }}
          >
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="text-lg font-semibold text-primary">Statistical Distribution Analysis</h4>
                <div className="flex space-x-4 text-xs">
                  <div className="flex items-center space-x-1">
                    <div className="w-3 h-0.5" style={{ backgroundColor: 'var(--color-1)' }}></div>
                    <span className="text-muted">Mean: 187ms</span>
                  </div>
                  <div className="flex items-center space-x-1">
                    <div className="w-3 h-0.5" style={{ backgroundColor: 'var(--color-2)' }}></div>
                    <span className="text-muted">Median: 165ms</span>
                  </div>
                  <div className="flex items-center space-x-1">
                    <div className="w-3 h-0.5" style={{ backgroundColor: 'var(--color-3)' }}></div>
                    <span className="text-muted">Mode: 145ms</span>
                  </div>
                </div>
              </div>
              <div className="relative h-48 rounded-lg p-4" style={{ backgroundColor: chartBg }}>
                {/* Histogram Bars */}
                <div className="absolute inset-4 flex items-end justify-center space-x-1">
                  {[20, 35, 60, 85, 95, 88, 70, 45, 25, 15, 8, 3].map((height, index) => (
                    <motion.div
                      key={index}
                      className="flex-1 rounded-t relative group cursor-pointer"
                      style={{
                        backgroundColor: `var(--color-${(index % 5) + 1})`,
                        height: `${height}%`,
                        minHeight: '8px',
                        opacity: 0.8
                      }}
                      initial={{ height: 0 }}
                      animate={{ height: `${height}%` }}
                      transition={{ delay: 0.9 + index * 0.03, duration: 0.6 }}
                      whileHover={{ opacity: 1, scale: 1.02 }}
                    />
                  ))}
                </div>

                {/* Statistical Lines */}
                {/* Mean Line */}
                <motion.div
                  className="absolute top-0 bottom-0 w-0.5 z-10"
                  style={{
                    backgroundColor: 'var(--color-1)',
                    left: '62%' // Position based on mean value
                  }}
                  initial={{ opacity: 0, scaleY: 0 }}
                  animate={{ opacity: 1, scaleY: 1 }}
                  transition={{ delay: 1.5, duration: 0.8 }}
                >
                  <div className="absolute -top-6 left-1/2 transform -translate-x-1/2 text-xs font-bold px-2 py-1 rounded text-white" style={{ backgroundColor: 'var(--color-1)' }}>
                    Mean
                  </div>
                </motion.div>

                {/* Median Line */}
                <motion.div
                  className="absolute top-0 bottom-0 w-0.5 z-10"
                  style={{
                    backgroundColor: 'var(--color-2)',
                    left: '55%' // Position based on median value
                  }}
                  initial={{ opacity: 0, scaleY: 0 }}
                  animate={{ opacity: 1, scaleY: 1 }}
                  transition={{ delay: 1.7, duration: 0.8 }}
                >
                  <div className="absolute -top-6 left-1/2 transform -translate-x-1/2 text-xs font-bold px-2 py-1 rounded text-white" style={{ backgroundColor: 'var(--color-2)' }}>
                    Median
                  </div>
                </motion.div>

                {/* Mode Line */}
                <motion.div
                  className="absolute top-0 bottom-0 w-0.5 z-10"
                  style={{
                    backgroundColor: 'var(--color-3)',
                    left: '48%' // Position based on mode value
                  }}
                  initial={{ opacity: 0, scaleY: 0 }}
                  animate={{ opacity: 1, scaleY: 1 }}
                  transition={{ delay: 1.9, duration: 0.8 }}
                >
                  <div className="absolute -top-6 left-1/2 transform -translate-x-1/2 text-xs font-bold px-2 py-1 rounded text-white" style={{ backgroundColor: 'var(--color-3)' }}>
                    Mode
                  </div>
                </motion.div>
              </div>
              <div className="flex justify-between text-xs text-muted">
                <span>0ms</span>
                <span>100ms</span>
                <span>200ms</span>
                <span>300ms</span>
                <span>400ms</span>
                <span>500ms+</span>
              </div>
            </div>
          </motion.div>
        </div>

        {/* Specialized Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Radar Chart */}
          <motion.div
            className="card p-6"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.8 }}
          >
            <div className="space-y-4">
              <h4 className="text-md font-semibold text-primary">Performance Radar</h4>
              <div className="flex justify-center">
                <div className="relative w-40 h-40">
                  <svg className="w-40 h-40" viewBox="0 0 200 200">
                    {/* Grid circles */}
                    {[20, 40, 60, 80].map(radius => (
                      <circle
                        key={radius}
                        cx="100"
                        cy="100"
                        r={radius}
                        fill="none"
                        stroke="currentColor"
                        strokeOpacity="0.1"
                        strokeWidth="1"
                      />
                    ))}

                    {/* Grid lines */}
                    {[0, 60, 120, 180, 240, 300].map((angle) => {
                      const x = 100 + 80 * Math.cos((angle - 90) * Math.PI / 180)
                      const y = 100 + 80 * Math.sin((angle - 90) * Math.PI / 180)
                      return (
                        <line
                          key={angle}
                          x1="100"
                          y1="100"
                          x2={x}
                          y2={y}
                          stroke="currentColor"
                          strokeOpacity="0.1"
                          strokeWidth="1"
                        />
                      )
                    })}

                    {/* Data polygon */}
                    <motion.polygon
                      points="100,35 140,55 155,120 120,155 80,145 65,80"
                      fill="var(--color-1)"
                      fillOpacity="0.3"
                      stroke="var(--color-1)"
                      strokeWidth="2"
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ delay: 1.2, duration: 1 }}
                    />

                    {/* Data points */}
                    {[
                      { x: 100, y: 35, color: 'var(--color-1)' },
                      { x: 140, y: 55, color: 'var(--color-2)' },
                      { x: 155, y: 120, color: 'var(--color-3)' },
                      { x: 120, y: 155, color: 'var(--color-4)' },
                      { x: 80, y: 145, color: 'var(--color-5)' },
                      { x: 65, y: 80, color: 'var(--color-1)' }
                    ].map((point, index) => (
                      <motion.circle
                        key={index}
                        cx={point.x}
                        cy={point.y}
                        r="4"
                        fill={point.color}
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        transition={{ delay: 1.4 + index * 0.1, duration: 0.3 }}
                      />
                    ))}
                  </svg>

                  {/* Labels */}
                  <div className="absolute top-0 left-1/2 transform -translate-x-1/2 -translate-y-2 text-xs font-medium text-primary">Speed</div>
                  <div className="absolute top-3 right-0 transform translate-x-2 text-xs font-medium text-primary">Quality</div>
                  <div className="absolute bottom-3 right-0 transform translate-x-2 text-xs font-medium text-primary">Security</div>
                  <div className="absolute bottom-0 left-1/2 transform -translate-x-1/2 translate-y-2 text-xs font-medium text-primary">Cost</div>
                  <div className="absolute bottom-3 left-0 transform -translate-x-2 text-xs font-medium text-primary">Scale</div>
                  <div className="absolute top-3 left-0 transform -translate-x-2 text-xs font-medium text-primary">Reliability</div>
                </div>
              </div>
              <div className="text-center text-xs text-muted">DevOps Capability Assessment</div>
            </div>
          </motion.div>

          {/* Solar/Sunburst Chart */}
          <motion.div
            className="card p-6"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.9 }}
          >
            <div className="space-y-4">
              <h4 className="text-md font-semibold text-primary">Technology Stack</h4>
              <div className="flex justify-center">
                <div className="relative w-40 h-40">
                  <svg className="w-40 h-40" viewBox="0 0 200 200">
                    {/* Inner circle - Core */}
                    <motion.circle
                      cx="100"
                      cy="100"
                      r="25"
                      fill="var(--color-1)"
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ delay: 1.2, duration: 0.8 }}
                    />

                    {/* Middle ring - Frameworks */}
                    {[
                      { start: 0, end: 120, color: 'var(--color-2)' },
                      { start: 120, end: 240, color: 'var(--color-3)' },
                      { start: 240, end: 360, color: 'var(--color-4)' }
                    ].map((segment, index) => (
                      <motion.path
                        key={index}
                        d={`M 100 100 L ${100 + 45 * Math.cos((segment.start - 90) * Math.PI / 180)} ${100 + 45 * Math.sin((segment.start - 90) * Math.PI / 180)} A 45 45 0 ${segment.end - segment.start > 180 ? 1 : 0} 1 ${100 + 45 * Math.cos((segment.end - 90) * Math.PI / 180)} ${100 + 45 * Math.sin((segment.end - 90) * Math.PI / 180)} Z`}
                        fill={segment.color}
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        transition={{ delay: 1.4 + index * 0.2, duration: 0.6 }}
                      />
                    ))}

                    {/* Outer ring - Tools */}
                    {[
                      { start: 0, end: 60, color: 'var(--color-5)' },
                      { start: 60, end: 120, color: 'var(--color-1)' },
                      { start: 120, end: 180, color: 'var(--color-2)' },
                      { start: 180, end: 240, color: 'var(--color-3)' },
                      { start: 240, end: 300, color: 'var(--color-4)' },
                      { start: 300, end: 360, color: 'var(--color-5)' }
                    ].map((segment, index) => (
                      <motion.path
                        key={index}
                        d={`M 100 100 L ${100 + 70 * Math.cos((segment.start - 90) * Math.PI / 180)} ${100 + 70 * Math.sin((segment.start - 90) * Math.PI / 180)} A 70 70 0 0 1 ${100 + 70 * Math.cos((segment.end - 90) * Math.PI / 180)} ${100 + 70 * Math.sin((segment.end - 90) * Math.PI / 180)} L ${100 + 45 * Math.cos((segment.end - 90) * Math.PI / 180)} ${100 + 45 * Math.sin((segment.end - 90) * Math.PI / 180)} A 45 45 0 0 0 ${100 + 45 * Math.cos((segment.start - 90) * Math.PI / 180)} ${100 + 45 * Math.sin((segment.start - 90) * Math.PI / 180)} Z`}
                        fill={segment.color}
                        opacity="0.8"
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        transition={{ delay: 1.8 + index * 0.1, duration: 0.4 }}
                      />
                    ))}

                    {/* Center text */}
                    <text x="100" y="105" textAnchor="middle" className="text-xs font-bold fill-white dark:fill-gray-200">Core</text>
                  </svg>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2 text-xs">
                <div className="text-center">
                  <div className="w-3 h-3 rounded mx-auto mb-1" style={{ backgroundColor: 'var(--color-1)' }}></div>
                  <div className="text-muted">Core</div>
                </div>
                <div className="text-center">
                  <div className="w-3 h-3 rounded mx-auto mb-1" style={{ backgroundColor: 'var(--color-2)' }}></div>
                  <div className="text-muted">Frontend</div>
                </div>
                <div className="text-center">
                  <div className="w-3 h-3 rounded mx-auto mb-1" style={{ backgroundColor: 'var(--color-3)' }}></div>
                  <div className="text-muted">Backend</div>
                </div>
              </div>
            </div>
          </motion.div>

          {/* World Map with Pinpoints */}
          <motion.div
            className="card p-6"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 1.0 }}
          >
            <div className="space-y-4">
              <h4 className="text-md font-semibold text-primary">Global Activity</h4>
              <div className="relative h-32 bg-gray-50 dark:bg-gray-800 rounded-lg overflow-hidden">
                <svg className="w-full h-full" viewBox="0 0 400 160">
                  {/* Simplified world map continents */}
                  <motion.path
                    d="M60,40 Q90,30 120,45 L140,60 Q110,80 80,70 Z"
                    fill="currentColor"
                    fillOpacity="0.1"
                    stroke="currentColor"
                    strokeOpacity="0.2"
                    strokeWidth="1"
                    initial={{ pathLength: 0 }}
                    animate={{ pathLength: 1 }}
                    transition={{ delay: 1.3, duration: 1 }}
                  />
                  <motion.path
                    d="M160,35 Q200,25 240,40 L260,55 Q230,75 190,65 Z"
                    fill="currentColor"
                    fillOpacity="0.1"
                    stroke="currentColor"
                    strokeOpacity="0.2"
                    strokeWidth="1"
                    initial={{ pathLength: 0 }}
                    animate={{ pathLength: 1 }}
                    transition={{ delay: 1.4, duration: 1 }}
                  />
                  <motion.path
                    d="M280,45 Q320,35 360,50 L380,65 Q350,85 310,75 Z"
                    fill="currentColor"
                    fillOpacity="0.1"
                    stroke="currentColor"
                    strokeOpacity="0.2"
                    strokeWidth="1"
                    initial={{ pathLength: 0 }}
                    animate={{ pathLength: 1 }}
                    transition={{ delay: 1.5, duration: 1 }}
                  />
                  <motion.path
                    d="M80,90 Q120,80 160,95 L180,110 Q150,130 110,120 Z"
                    fill="currentColor"
                    fillOpacity="0.1"
                    stroke="currentColor"
                    strokeOpacity="0.2"
                    strokeWidth="1"
                    initial={{ pathLength: 0 }}
                    animate={{ pathLength: 1 }}
                    transition={{ delay: 1.6, duration: 1 }}
                  />

                  {/* Activity pinpoints with bubbles */}
                  {[
                    { x: 100, y: 55, size: 12, activity: 2400, color: 'var(--color-1)' },
                    { x: 220, y: 50, size: 8, activity: 1800, color: 'var(--color-2)' },
                    { x: 340, y: 60, size: 15, activity: 3200, color: 'var(--color-3)' },
                    { x: 140, y: 105, size: 6, activity: 900, color: 'var(--color-4)' },
                    { x: 70, y: 45, size: 10, activity: 1500, color: 'var(--color-5)' },
                    { x: 300, y: 70, size: 7, activity: 1200, color: 'var(--color-1)' },
                    { x: 180, y: 40, size: 9, activity: 1600, color: 'var(--color-2)' }
                  ].map((pin, index) => (
                    <g key={index}>
                      {/* Pulse animation */}
                      <motion.circle
                        cx={pin.x}
                        cy={pin.y}
                        r={pin.size}
                        fill={pin.color}
                        fillOpacity="0.3"
                        initial={{ scale: 0 }}
                        animate={{ scale: [0, 1.5, 1] }}
                        transition={{
                          delay: 1.8 + index * 0.2,
                          duration: 1,
                          repeat: Infinity,
                          repeatDelay: 2
                        }}
                      />
                      {/* Main pin */}
                      <motion.circle
                        cx={pin.x}
                        cy={pin.y}
                        r={pin.size * 0.6}
                        fill={pin.color}
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        transition={{ delay: 1.8 + index * 0.2, duration: 0.5 }}
                      />
                      {/* Activity label */}
                      <motion.text
                        x={pin.x}
                        y={pin.y - pin.size - 5}
                        textAnchor="middle"
                        className="text-xs font-bold fill-gray-800 dark:fill-gray-200"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: 2 + index * 0.2 }}
                      >
                        {pin.activity}
                      </motion.text>
                    </g>
                  ))}
                </svg>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="flex items-center space-x-2">
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: 'var(--color-1)' }}></div>
                  <span className="text-muted">High Traffic</span>
                </div>
                <div className="flex items-center space-x-2">
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: 'var(--color-2)' }}></div>
                  <span className="text-muted">Medium Traffic</span>
                </div>
                <div className="flex items-center space-x-2">
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: 'var(--color-3)' }}></div>
                  <span className="text-muted">Peak Activity</span>
                </div>
                <div className="flex items-center space-x-2">
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: 'var(--color-4)' }}></div>
                  <span className="text-muted">Low Activity</span>
                </div>
              </div>
            </div>
          </motion.div>
        </div>

        {/* Finance & Portfolio Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Portfolio Performance */}
          <motion.div
            className="card p-6"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 1.1 }}
          >
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <h4 className="text-lg font-semibold text-primary">Portfolio Performance</h4>
                <div className="flex items-center space-x-3">
                  <div className="text-right">
                    <div className="text-2xl font-bold" style={{ color: 'var(--color-3)' }}>+12.4%</div>
                    <div className="text-xs text-muted">YTD Return</div>
                  </div>
                  <div className="text-right">
                    <div className="text-lg font-bold text-primary">$847K</div>
                    <div className="text-xs text-muted">Total Value</div>
                  </div>
                </div>
              </div>

              {/* Larger Candlestick-style chart */}
              <div className="h-48 relative bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
                <svg className="w-full h-full" viewBox="0 0 320 160">
                  {/* Grid lines */}
                  {[0, 1, 2, 3, 4, 5].map(i => (
                    <line key={i} x1="0" y1={i * 32} x2="320" y2={i * 32} stroke="currentColor" strokeOpacity="0.1" strokeWidth="1" />
                  ))}
                  {[0, 1, 2, 3, 4, 5, 6, 7].map(i => (
                    <line key={i} x1={i * 40} y1="0" x2={i * 40} y2="160" stroke="currentColor" strokeOpacity="0.05" strokeWidth="1" />
                  ))}

                  {/* Candlesticks - Larger */}
                  {[
                    { x: 40, open: 100, close: 120, high: 125, low: 95, positive: true, volume: 85 },
                    { x: 80, open: 120, close: 110, high: 125, low: 105, positive: false, volume: 92 },
                    { x: 120, open: 110, close: 130, high: 135, low: 108, positive: true, volume: 78 },
                    { x: 160, open: 130, close: 125, high: 132, low: 120, positive: false, volume: 65 },
                    { x: 200, open: 125, close: 140, high: 145, low: 122, positive: true, volume: 88 },
                    { x: 240, open: 140, close: 145, high: 150, low: 138, positive: true, volume: 95 },
                    { x: 280, open: 145, close: 135, high: 148, low: 130, positive: false, volume: 72 }
                  ].map((candle, index) => (
                    <motion.g key={index}>
                      {/* Volume bars at bottom */}
                      <motion.rect
                        x={candle.x - 8}
                        y={160 - candle.volume * 0.3}
                        width="16"
                        height={candle.volume * 0.3}
                        fill="var(--color-4)"
                        fillOpacity="0.3"
                        initial={{ scaleY: 0 }}
                        animate={{ scaleY: 1 }}
                        transition={{ delay: 1.3 + index * 0.1, duration: 0.4 }}
                      />

                      {/* High-Low line */}
                      <motion.line
                        x1={candle.x}
                        y1={160 - candle.high}
                        x2={candle.x}
                        y2={160 - candle.low}
                        stroke={candle.positive ? 'var(--color-3)' : 'var(--color-5)'}
                        strokeWidth="2"
                        initial={{ scaleY: 0 }}
                        animate={{ scaleY: 1 }}
                        transition={{ delay: 1.5 + index * 0.1, duration: 0.3 }}
                      />
                      {/* Body */}
                      <motion.rect
                        x={candle.x - 6}
                        y={160 - Math.max(candle.open, candle.close)}
                        width="12"
                        height={Math.abs(candle.close - candle.open)}
                        fill={candle.positive ? 'var(--color-3)' : 'var(--color-5)'}
                        stroke={candle.positive ? 'var(--color-3)' : 'var(--color-5)'}
                        strokeWidth="1"
                        initial={{ scaleY: 0 }}
                        animate={{ scaleY: 1 }}
                        transition={{ delay: 1.5 + index * 0.1, duration: 0.3 }}
                      />
                    </motion.g>
                  ))}

                  {/* Moving averages */}
                  <motion.path
                    d="M40,110 Q80,105 120,95 T200,85 T280,90"
                    fill="none"
                    stroke="var(--color-1)"
                    strokeWidth="3"
                    strokeDasharray="8,4"
                    initial={{ pathLength: 0 }}
                    animate={{ pathLength: 1 }}
                    transition={{ delay: 2.5, duration: 1.5 }}
                  />
                  <motion.path
                    d="M40,115 Q80,110 120,100 T200,90 T280,95"
                    fill="none"
                    stroke="var(--color-2)"
                    strokeWidth="2"
                    strokeDasharray="4,2"
                    initial={{ pathLength: 0 }}
                    animate={{ pathLength: 1 }}
                    transition={{ delay: 2.7, duration: 1.5 }}
                  />

                  {/* Price labels */}
                  <text x="10" y="20" className="text-xs fill-gray-600 dark:fill-gray-300">$150</text>
                  <text x="10" y="50" className="text-xs fill-gray-600 dark:fill-gray-300">$130</text>
                  <text x="10" y="80" className="text-xs fill-gray-600 dark:fill-gray-300">$110</text>
                  <text x="10" y="110" className="text-xs fill-gray-600 dark:fill-gray-300">$90</text>
                </svg>
              </div>

              {/* Enhanced Portfolio breakdown */}
              <div className="grid grid-cols-3 gap-4">
                {[
                  { label: 'Stocks', value: '65%', amount: '$550K', color: 'var(--color-1)', change: '+8.2%' },
                  { label: 'Bonds', value: '25%', amount: '$212K', color: 'var(--color-2)', change: '+3.1%' },
                  { label: 'Crypto', value: '10%', amount: '$85K', color: 'var(--color-3)', change: '+24.7%' }
                ].map((asset, index) => (
                  <motion.div
                    key={index}
                    className="p-4 rounded-lg bg-gray-50 dark:bg-gray-800 border-l-4"
                    style={{ borderLeftColor: asset.color }}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 2.8 + index * 0.1 }}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-primary">{asset.label}</span>
                      <span className="text-xs px-2 py-1 rounded text-white" style={{ backgroundColor: asset.color }}>
                        {asset.change}
                      </span>
                    </div>
                    <div className="text-xl font-bold mb-1" style={{ color: asset.color }}>{asset.amount}</div>
                    <div className="text-sm text-muted">{asset.value} of portfolio</div>
                  </motion.div>
                ))}
              </div>

              {/* Performance metrics */}
              <div className="grid grid-cols-2 gap-4 text-sm">
                {[
                  { label: 'Annual Return', value: '+15.8%', color: 'var(--color-3)' },
                  { label: 'Total Gain', value: '+$92K', color: 'var(--color-1)' },
                  { label: 'Best Month', value: '+8.4%', color: 'var(--color-2)' },
                  { label: 'Win Rate', value: '73%', color: 'var(--color-4)' }
                ].map((metric, index) => (
                  <motion.div
                    key={index}
                    className="flex items-center justify-between p-3 rounded bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-700"
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 3.2 + index * 0.1 }}
                  >
                    <span className="text-muted">{metric.label}</span>
                    <span className="font-bold" style={{ color: metric.color }}>{metric.value}</span>
                  </motion.div>
                ))}
              </div>
            </div>
          </motion.div>

          {/* Risk Analysis */}
          <motion.div
            className="card p-6"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 1.2 }}
          >
            <div className="space-y-6">
              <h4 className="text-md font-semibold text-primary">Risk Analysis Dashboard</h4>

              {/* Large Risk gauge */}
              <div className="flex justify-center">
                <div className="relative w-64 h-32">
                  <svg className="w-64 h-32" viewBox="0 0 240 120">
                    {/* Background arc */}
                    <path
                      d="M 20 100 A 100 100 0 0 1 220 100"
                      fill="none"
                      stroke="currentColor"
                      strokeOpacity="0.1"
                      strokeWidth="16"
                    />

                    {/* Risk level arcs with labels */}
                    <motion.path
                      d="M 20 100 A 100 100 0 0 1 80 50"
                      fill="none"
                      stroke="var(--color-3)"
                      strokeWidth="16"
                      initial={{ pathLength: 0 }}
                      animate={{ pathLength: 1 }}
                      transition={{ delay: 1.6, duration: 0.8 }}
                    />
                    <motion.path
                      d="M 80 50 A 100 100 0 0 1 160 50"
                      fill="none"
                      stroke="var(--color-4)"
                      strokeWidth="16"
                      initial={{ pathLength: 0 }}
                      animate={{ pathLength: 1 }}
                      transition={{ delay: 1.8, duration: 0.8 }}
                    />
                    <motion.path
                      d="M 160 50 A 100 100 0 0 1 220 100"
                      fill="none"
                      stroke="var(--color-5)"
                      strokeWidth="16"
                      initial={{ pathLength: 0 }}
                      animate={{ pathLength: 1 }}
                      transition={{ delay: 2.0, duration: 0.8 }}
                    />

                    {/* Risk level labels */}
                    <text x="50" y="115" textAnchor="middle" className="text-xs font-medium" style={{ fill: 'var(--color-3)' }}>Low</text>
                    <text x="120" y="45" textAnchor="middle" className="text-xs font-medium" style={{ fill: 'var(--color-4)' }}>Medium</text>
                    <text x="190" y="115" textAnchor="middle" className="text-xs font-medium" style={{ fill: 'var(--color-5)' }}>High</text>

                    {/* Needle */}
                    <motion.line
                      x1="120"
                      y1="100"
                      x2="90"
                      y2="60"
                      stroke="var(--color-1)"
                      strokeWidth="4"
                      strokeLinecap="round"
                      initial={{ rotate: -45 }}
                      animate={{ rotate: -15 }}
                      transition={{ delay: 2.2, duration: 1, type: "spring" }}
                      style={{ transformOrigin: "120px 100px" }}
                    />

                    {/* Center dot */}
                    <circle cx="120" cy="100" r="6" fill="var(--color-1)" />

                    {/* Current value display */}
                    <text x="120" y="85" textAnchor="middle" className="text-lg font-bold" style={{ fill: 'var(--color-4)' }}>6.2</text>
                    <text x="120" y="95" textAnchor="middle" className="text-xs fill-gray-600 dark:fill-gray-300">Risk Score</text>
                  </svg>
                </div>
              </div>

              {/* Risk breakdown with larger metrics */}
              <div className="grid grid-cols-2 gap-4">
                {[
                  { label: 'Volatility', value: '18.2%', desc: 'Price fluctuation', color: 'var(--color-1)', trend: '+2.1%' },
                  { label: 'Sharpe Ratio', value: '1.34', desc: 'Risk-adjusted return', color: 'var(--color-2)', trend: '+0.08' },
                  { label: 'Max Drawdown', value: '-8.7%', desc: 'Worst decline', color: 'var(--color-5)', trend: '-1.2%' },
                  { label: 'Beta', value: '0.92', desc: 'Market correlation', color: 'var(--color-3)', trend: '-0.05' }
                ].map((metric, index) => (
                  <motion.div
                    key={index}
                    className="p-4 rounded-lg bg-gray-50 dark:bg-gray-800 border-l-4"
                    style={{ borderLeftColor: metric.color }}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 2.4 + index * 0.1 }}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-primary">{metric.label}</span>
                      <span className="text-xs px-2 py-1 rounded text-white" style={{ backgroundColor: metric.color }}>
                        {metric.trend}
                      </span>
                    </div>
                    <div className="text-2xl font-bold mb-1" style={{ color: metric.color }}>{metric.value}</div>
                    <div className="text-xs text-muted">{metric.desc}</div>
                  </motion.div>
                ))}
              </div>

              {/* Risk distribution chart */}
              <div className="space-y-3">
                <h5 className="text-sm font-semibold text-secondary">Risk Distribution</h5>
                <div className="space-y-2">
                  {[
                    { category: 'Market Risk', percentage: 45, color: 'var(--color-1)' },
                    { category: 'Credit Risk', percentage: 25, color: 'var(--color-2)' },
                    { category: 'Liquidity Risk', percentage: 20, color: 'var(--color-3)' },
                    { category: 'Operational Risk', percentage: 10, color: 'var(--color-4)' }
                  ].map((risk, index) => (
                    <motion.div
                      key={index}
                      className="flex items-center space-x-3"
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: 2.8 + index * 0.1 }}
                    >
                      <div className="w-20 text-xs text-muted">{risk.category}</div>
                      <div className="flex-1 bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                        <motion.div
                          className="h-2 rounded-full"
                          style={{ backgroundColor: risk.color }}
                          initial={{ width: 0 }}
                          animate={{ width: `${risk.percentage}%` }}
                          transition={{ delay: 3 + index * 0.1, duration: 0.8 }}
                        />
                      </div>
                      <div className="w-8 text-xs font-medium text-primary">{risk.percentage}%</div>
                    </motion.div>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </div>

      {/* Geo-Mapping & World Visualization */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* World Map Heatmap */}
        <motion.div
          className="card p-6 lg:col-span-2"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6 }}
        >
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="text-md font-semibold text-primary">Global Activity Heatmap</h4>
              <div className="flex items-center space-x-2 text-xs text-muted">
                <span>Low</span>
                <div className="flex space-x-1">
                  {[1, 2, 3, 4, 5].map(i => (
                    <div key={i} className="w-3 h-3 rounded" style={{ backgroundColor: `var(--color-${i})`, opacity: i * 0.2 }}></div>
                  ))}
                </div>
                <span>High</span>
              </div>
            </div>
            <div className="h-48 rounded-lg relative overflow-hidden" style={{ backgroundColor: chartBg }}>
              {/* Simplified World Map */}
              <svg className="w-full h-full" viewBox="0 0 400 200">
                {/* Continents as simplified shapes */}
                <motion.path
                  d="M50,80 Q80,60 120,70 L140,90 Q110,110 80,100 Z"
                  fill="var(--color-1)"
                  opacity="0.7"
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: 0.8, duration: 0.5 }}
                />
                <motion.path
                  d="M160,60 Q200,50 240,65 L250,85 Q220,95 190,85 Z"
                  fill="var(--color-2)"
                  opacity="0.8"
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: 1, duration: 0.5 }}
                />
                <motion.path
                  d="M270,70 Q310,60 350,75 L360,95 Q330,105 300,95 Z"
                  fill="var(--color-3)"
                  opacity="0.6"
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: 1.2, duration: 0.5 }}
                />
                <motion.path
                  d="M80,120 Q120,110 160,125 L170,145 Q140,155 110,145 Z"
                  fill="var(--color-4)"
                  opacity="0.5"
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: 1.4, duration: 0.5 }}
                />
                <motion.path
                  d="M200,130 Q240,120 280,135 L290,155 Q260,165 230,155 Z"
                  fill="var(--color-5)"
                  opacity="0.4"
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: 1.6, duration: 0.5 }}
                />

                {/* Activity dots */}
                {[
                  { x: 100, y: 85, color: 'var(--color-1)' },
                  { x: 220, y: 75, color: 'var(--color-2)' },
                  { x: 320, y: 85, color: 'var(--color-3)' },
                  { x: 140, y: 135, color: 'var(--color-4)' },
                  { x: 250, y: 145, color: 'var(--color-5)' }
                ].map((dot, index) => (
                  <motion.circle
                    key={index}
                    cx={dot.x}
                    cy={dot.y}
                    r="4"
                    fill={dot.color}
                    initial={{ scale: 0, opacity: 0 }}
                    animate={{ scale: [0, 1.5, 1], opacity: [0, 1, 0.8] }}
                    transition={{ delay: 2 + index * 0.2, duration: 0.8 }}
                  />
                ))}
              </svg>
            </div>
            <div className="grid grid-cols-5 gap-4 text-xs">
              {[
                { region: 'North America', users: '2.4M', color: 'var(--color-1)' },
                { region: 'Europe', users: '1.8M', color: 'var(--color-2)' },
                { region: 'Asia Pacific', users: '3.2M', color: 'var(--color-3)' },
                { region: 'South America', users: '0.9M', color: 'var(--color-4)' },
                { region: 'Africa', users: '0.6M', color: 'var(--color-5)' }
              ].map((region, index) => (
                <div key={index} className="text-center">
                  <div className="w-4 h-4 rounded mx-auto mb-1" style={{ backgroundColor: region.color }}></div>
                  <div className="text-primary font-medium">{region.users}</div>
                  <div className="text-muted">{region.region}</div>
                </div>
              ))}
            </div>
          </div>
        </motion.div>

        {/* Geographic Stats */}
        <motion.div
          className="card p-6"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7 }}
        >
          <div className="space-y-4">
            <h4 className="text-md font-semibold text-primary">Regional Metrics</h4>
            <div className="space-y-4">
              {[
                { label: 'Active Regions', value: '127', change: '+12%', color: 'var(--color-1)' },
                { label: 'Peak Traffic', value: '89K/min', change: '+5%', color: 'var(--color-2)' },
                { label: 'Avg Latency', value: '45ms', change: '-8%', color: 'var(--color-3)' },
                { label: 'Error Rate', value: '0.02%', change: '-15%', color: 'var(--color-4)' }
              ].map((metric, index) => (
                <motion.div
                  key={index}
                  className="flex items-center justify-between p-3 rounded-lg bg-gray-50 dark:bg-gray-800"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.9 + index * 0.1 }}
                >
                  <div className="flex items-center space-x-3">
                    <div className="w-3 h-3 rounded-full" style={{ backgroundColor: metric.color }}></div>
                    <div>
                      <div className="text-sm font-medium text-primary">{metric.value}</div>
                      <div className="text-xs text-muted">{metric.label}</div>
                    </div>
                  </div>
                  <div className="text-xs font-medium" style={{ color: metric.change.startsWith('+') ? 'var(--color-3)' : 'var(--color-5)' }}>
                    {metric.change}
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </motion.div>
      </div>

      {/* Data Tables & Advanced Components */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Data Table */}
        <motion.div
          className="card p-6"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.8 }}
        >
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="text-md font-semibold text-primary">Data Table</h4>
              <button className="px-3 py-1 text-xs rounded text-white hover:opacity-90 transition-opacity" style={{ backgroundColor: 'var(--color-1)' }}>
                Export
              </button>
            </div>
            <div className="overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700">
              <table className="w-full">
                <thead className="bg-gray-50 dark:bg-gray-800">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Repository</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Status</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Score</th>
                  </tr>
                </thead>
                <tbody className="bg-gray-50 dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                  {[
                    { name: 'frontend-app', status: 'Active', score: 98, color: 'var(--color-3)' },
                    { name: 'backend-service', status: 'Building', score: 85, color: 'var(--color-4)' },
                    { name: 'etl-service', status: 'Warning', score: 72, color: 'var(--color-5)' }
                  ].map((row, index) => (
                    <motion.tr
                      key={index}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: 1 + index * 0.1 }}
                      className="hover:bg-gray-50 dark:hover:bg-gray-700"
                    >
                      <td className="px-4 py-4 whitespace-nowrap text-sm font-medium text-primary">{row.name}</td>
                      <td className="px-4 py-4 whitespace-nowrap">
                        <span className="px-2 py-1 text-xs rounded-full text-white" style={{ backgroundColor: row.color }}>
                          {row.status}
                        </span>
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <div className="w-16 bg-gray-200 dark:bg-gray-700 rounded-full h-2 mr-2">
                            <div
                              className="h-2 rounded-full"
                              style={{ backgroundColor: row.color, width: `${row.score}%` }}
                            ></div>
                          </div>
                          <span className="text-sm text-primary">{row.score}%</span>
                        </div>
                      </td>
                    </motion.tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </motion.div>

        {/* Advanced UI Components */}
        <motion.div
          className="card p-6"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.9 }}
        >
          <div className="space-y-4">
            <h4 className="text-md font-semibold text-primary">UI Components</h4>

            {/* Progress Rings */}
            <div className="grid grid-cols-3 gap-4">
              {[
                { label: 'CPU', value: 75, color: 'var(--color-1)' },
                { label: 'Memory', value: 60, color: 'var(--color-2)' },
                { label: 'Disk', value: 90, color: 'var(--color-3)' }
              ].map((item, index) => (
                <div key={index} className="text-center">
                  <div className="relative w-16 h-16 mx-auto mb-2">
                    <svg className="w-16 h-16 transform -rotate-90" viewBox="0 0 36 36">
                      <path
                        d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeOpacity="0.2"
                      />
                      <motion.path
                        d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                        fill="none"
                        stroke={item.color}
                        strokeWidth="2"
                        strokeDasharray={`${item.value}, 100`}
                        initial={{ strokeDasharray: "0, 100" }}
                        animate={{ strokeDasharray: `${item.value}, 100` }}
                        transition={{ delay: 1.2 + index * 0.2, duration: 1 }}
                      />
                    </svg>
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className="text-xs font-bold text-primary">{item.value}%</span>
                    </div>
                  </div>
                  <div className="text-xs text-muted">{item.label}</div>
                </div>
              ))}
            </div>

            {/* Toggle Switches */}
            <div className="space-y-3">
              <h5 className="text-sm font-medium text-secondary">Feature Toggles</h5>
              {[
                { label: 'Real-time Updates', enabled: true, color: 'var(--color-3)' },
                { label: 'Dark Mode', enabled: false, color: 'var(--color-4)' },
                { label: 'Notifications', enabled: true, color: 'var(--color-1)' }
              ].map((toggle, index) => (
                <div key={index} className="flex items-center justify-between">
                  <span className="text-sm text-primary">{toggle.label}</span>
                  <div
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${toggle.enabled ? '' : 'bg-gray-200 dark:bg-gray-700'
                      }`}
                    style={{ backgroundColor: toggle.enabled ? toggle.color : undefined }}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${toggle.enabled ? 'translate-x-6' : 'translate-x-1'
                        }`}
                    />
                  </div>
                </div>
              ))}
            </div>

            {/* Action Buttons */}
            <div className="grid grid-cols-2 gap-2">
              <button className="px-4 py-2 rounded-lg font-medium transition-all hover:opacity-90" style={{ backgroundColor: 'var(--color-1)', color: 'var(--on-color-1)' }}>
                Primary
              </button>
              <button className="px-4 py-2 rounded-lg font-medium transition-all hover:opacity-90" style={{ backgroundColor: 'var(--color-2)', color: 'var(--on-color-2)' }}>
                Secondary
              </button>
              <button className="px-4 py-2 rounded-lg font-medium transition-all hover:opacity-90" style={{ backgroundColor: 'var(--color-3)', color: 'var(--on-color-3)' }}>
                Success
              </button>
              <button className="px-4 py-2 rounded-lg font-medium transition-all hover:opacity-90" style={{ backgroundColor: 'var(--color-5)', color: 'var(--on-color-5)' }}>
                Warning
              </button>
            </div>
          </div>
        </motion.div>
      </div>

      {/* Modern Glass Cards */}
      <motion.div
        className="grid grid-cols-1 md:grid-cols-4 gap-4"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1 }}
      >
        {[
          { title: 'Glass Morphism', desc: 'Backdrop blur effects', icon: '✨', gradient: 'linear-gradient(135deg, var(--color-1) 0%, var(--color-2) 100%)', onVar: '--on-gradient-1-2' },
          { title: 'Micro Animations', desc: 'Smooth transitions', icon: '⚡', gradient: 'linear-gradient(135deg, var(--color-2) 0%, var(--color-3) 100%)', onVar: '--on-gradient-2-3' },
          { title: 'Data Visualization', desc: 'Interactive charts', icon: '📊', gradient: 'linear-gradient(135deg, var(--color-3) 0%, var(--color-4) 100%)', onVar: '--on-gradient-3-4' },
          { title: 'Modern UI', desc: 'Clean aesthetics', icon: '🎨', gradient: 'linear-gradient(135deg, var(--color-4) 0%, var(--color-5) 100%)', onVar: '--on-gradient-4-5' }
        ].map((card, index) => (
          <motion.div
            key={index}
            className="relative p-6 rounded-xl backdrop-blur-sm border border-white border-opacity-20 transition-all duration-300 cursor-pointer overflow-hidden hover:shadow-lg"
            style={{ background: card.gradient }}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 1.2 + index * 0.1 }}
          >
            <div className="relative z-10" style={{ color: `var(${(card as any).onVar || '--on-gradient-1-2'})` }}>
              <div className="text-2xl mb-3">{card.icon}</div>
              <h5 className="font-bold mb-2">{card.title}</h5>
              <p className="text-sm opacity-90">{card.desc}</p>
            </div>
            <div className="absolute inset-0 bg-white bg-opacity-10 backdrop-blur-sm"></div>
          </motion.div>
        ))}
      </motion.div>
    </motion.div>
  )
}
