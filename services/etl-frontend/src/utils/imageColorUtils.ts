/**
 * Utility functions for analyzing image colors and determining appropriate filters
 */

/**
 * Calculate relative luminance of a color (WCAG formula)
 * Returns a value between 0 (black) and 1 (white)
 */
export function calculateLuminance(r: number, g: number, b: number): number {
  // Convert RGB to sRGB
  const rsRGB = r / 255
  const gsRGB = g / 255
  const bsRGB = b / 255

  // Apply gamma correction
  const rLinear = rsRGB <= 0.03928 ? rsRGB / 12.92 : Math.pow((rsRGB + 0.055) / 1.055, 2.4)
  const gLinear = gsRGB <= 0.03928 ? gsRGB / 12.92 : Math.pow((gsRGB + 0.055) / 1.055, 2.4)
  const bLinear = bsRGB <= 0.03928 ? bsRGB / 12.92 : Math.pow((bsRGB + 0.055) / 1.055, 2.4)

  // Calculate relative luminance
  return 0.2126 * rLinear + 0.7152 * gLinear + 0.0722 * bLinear
}

/**
 * Extract dominant color from an image
 * Returns average RGB values from the image
 */
export function extractDominantColor(imgElement: HTMLImageElement): Promise<{ r: number; g: number; b: number }> {
  return new Promise((resolve, reject) => {
    try {
      const canvas = document.createElement('canvas')
      const ctx = canvas.getContext('2d')
      
      if (!ctx) {
        reject(new Error('Could not get canvas context'))
        return
      }

      // Set canvas size to image size (or smaller for performance)
      const maxSize = 100
      const scale = Math.min(maxSize / imgElement.width, maxSize / imgElement.height, 1)
      canvas.width = imgElement.width * scale
      canvas.height = imgElement.height * scale

      // Draw image to canvas
      ctx.drawImage(imgElement, 0, 0, canvas.width, canvas.height)

      // Get image data
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height)
      const data = imageData.data

      let r = 0, g = 0, b = 0
      let count = 0

      // Calculate average color (skip fully transparent pixels)
      for (let i = 0; i < data.length; i += 4) {
        const alpha = data[i + 3]
        
        // Only count pixels that are not fully transparent
        if (alpha > 25) {
          r += data[i]
          g += data[i + 1]
          b += data[i + 2]
          count++
        }
      }

      if (count === 0) {
        // If all pixels are transparent, return white
        resolve({ r: 255, g: 255, b: 255 })
        return
      }

      // Calculate average
      resolve({
        r: Math.round(r / count),
        g: Math.round(g / count),
        b: Math.round(b / count)
      })
    } catch (error) {
      reject(error)
    }
  })
}

/**
 * Determine if a logo should be inverted to white based on its luminance
 * @param luminance - The calculated luminance (0-1)
 * @param threshold - The threshold below which to invert (default: 0.5)
 * @returns true if the logo should be inverted to white
 */
export function shouldInvertToWhite(luminance: number, threshold: number = 0.5): boolean {
  return luminance < threshold
}

/**
 * Get CSS filter to make an image white
 * This uses brightness and invert filters to convert any color to white
 */
export function getWhiteFilter(): string {
  // This filter combination converts any color to white:
  // 1. brightness(0) makes it black
  // 2. invert(1) makes black -> white
  return 'brightness(0) invert(1)'
}

/**
 * Analyze an image and determine if it needs a white filter
 * Returns the appropriate CSS filter string
 */
export async function getLogoFilter(
  imgElement: HTMLImageElement,
  theme: 'light' | 'dark',
  luminanceThreshold: number = 0.5
): Promise<string> {
  try {
    // Only apply filter in dark mode
    if (theme !== 'dark') {
      return 'none'
    }

    // Extract dominant color
    const color = await extractDominantColor(imgElement)

    // Calculate luminance
    const luminance = calculateLuminance(color.r, color.g, color.b)

    // Log for debugging (includes image name)
    const imageName = imgElement.src.split('/').pop()?.split('?')[0] || 'unknown'
    console.log(`🎨 Logo Analysis: ${imageName}`, {
      dominantColor: `rgb(${color.r}, ${color.g}, ${color.b})`,
      luminance: luminance.toFixed(3),
      threshold: luminanceThreshold,
      willInvert: luminance < luminanceThreshold
    })

    // Determine if we should invert to white
    if (shouldInvertToWhite(luminance, luminanceThreshold)) {
      return getWhiteFilter()
    }

    return 'none'
  } catch (error) {
    console.error('Error analyzing logo color:', error)
    return 'none'
  }
}

/**
 * Hook to use with img elements - automatically applies filter based on logo color
 * Usage: <img ref={el => el && applyLogoFilter(el, theme)} ... />
 */
export async function applyLogoFilter(
  imgElement: HTMLImageElement,
  theme: 'light' | 'dark',
  luminanceThreshold: number = 0.5
): Promise<void> {
  // Wait for image to load if not already loaded
  if (!imgElement.complete) {
    await new Promise((resolve) => {
      imgElement.onload = resolve
      imgElement.onerror = resolve
    })
  }

  // Get and apply filter
  const filter = await getLogoFilter(imgElement, theme, luminanceThreshold)
  imgElement.style.filter = filter
}

