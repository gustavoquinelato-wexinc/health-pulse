/**
 * Centralized Color Schema Mode Service
 * 
 * Single source of truth for color schema mode loading and management.
 * Eliminates race conditions and scattered fallbacks throughout the app.
 */

import axios from 'axios'

export type ColorSchemaMode = 'default' | 'custom'

/**
 * Get color schema mode from database with centralized fallback logic.
 * This is the ONLY place where fallbacks should happen.
 * 
 * @returns Promise<ColorSchemaMode> - Always returns a valid mode
 */
export const getColorSchemaMode = async (): Promise<ColorSchemaMode> => {
  try {


    const response = await axios.get('/api/v1/admin/color-schema/unified')

    if (response.data?.success && response.data.color_schema_mode) {
      const mode = response.data.color_schema_mode

      // Validate the mode value
      if (['default', 'custom'].includes(mode)) {
        // Sync to localStorage immediately for consistency
        try {
          localStorage.setItem('pulse_color_schema_mode', mode)

        } catch (error) {
          console.warn('Failed to sync color schema mode to localStorage:', error)
        }

        return mode as ColorSchemaMode
      } else {
        console.warn(`Invalid color schema mode from API: ${mode}, using default`)
      }
    } else {
      console.warn('No color_schema_mode in API response, using default')
    }
  } catch (error) {
    console.warn('Failed to load color schema mode from database:', error)
  }

  // SINGLE FALLBACK POINT - only place where 'default' is used as fallback
  console.log('🎨 Using fallback color schema mode: default')

  try {
    localStorage.setItem('pulse_color_schema_mode', 'default')
  } catch (error) {
    console.warn('Failed to set fallback mode in localStorage:', error)
  }

  return 'default'
}

/**
 * Get color schema mode from localStorage (for immediate access during initialization).
 * This should only be used during app startup before the database call completes.
 * 
 * @returns ColorSchemaMode | null - Returns cached mode or null if not available
 */
export const getCachedColorSchemaMode = (): ColorSchemaMode | null => {
  try {
    const cached = localStorage.getItem('pulse_color_schema_mode')
    if (cached && ['default', 'custom'].includes(cached)) {
      return cached as ColorSchemaMode
    }
  } catch (error) {
    console.warn('Failed to get cached color schema mode:', error)
  }

  return null
}

/**
 * Save color schema mode to database and sync to localStorage.
 * 
 * @param mode - The mode to save
 * @returns Promise<boolean> - Success status
 */
export const saveColorSchemaMode = async (mode: ColorSchemaMode): Promise<boolean> => {
  try {
    console.log(`🎨 Saving color schema mode to database: ${mode}`)

    const response = await axios.post('/api/v1/admin/color-schema/mode', { mode })

    if (response.data?.success) {
      // Sync to localStorage immediately
      try {
        localStorage.setItem('pulse_color_schema_mode', mode)
        console.log(`✅ Color schema mode saved and synced: ${mode}`)
      } catch (error) {
        console.warn('Failed to sync saved mode to localStorage:', error)
      }

      return true
    }
  } catch (error) {
    console.error('Failed to save color schema mode:', error)
  }

  return false
}
