import { useEffect, useRef } from 'react'
import { applyLogoFilter } from '../utils/imageColorUtils'

/**
 * React hook to automatically apply white filter to dark logos in dark mode
 * 
 * @param theme - Current theme ('light' | 'dark')
 * @param luminanceThreshold - Threshold below which to invert logo to white (0-1, default: 0.5)
 * @returns ref to attach to img element
 * 
 * @example
 * const logoRef = useLogoFilter(theme)
 * return <img ref={logoRef} src={logoUrl} alt="Logo" />
 */
export function useLogoFilter(theme: 'light' | 'dark', luminanceThreshold: number = 0.5) {
  const imgRef = useRef<HTMLImageElement>(null)

  useEffect(() => {
    const img = imgRef.current
    if (!img) return

    // Apply filter when image loads or theme changes
    const handleImageLoad = () => {
      applyLogoFilter(img, theme, luminanceThreshold)
    }

    // If image is already loaded, apply immediately
    if (img.complete) {
      handleImageLoad()
    } else {
      // Otherwise wait for load
      img.addEventListener('load', handleImageLoad)
    }

    // Reapply when theme changes
    handleImageLoad()

    return () => {
      img.removeEventListener('load', handleImageLoad)
    }
  }, [theme, luminanceThreshold])

  return imgRef
}

