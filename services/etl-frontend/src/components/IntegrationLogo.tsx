import React from 'react'
import { useTheme } from '../contexts/ThemeContext'
import { useLogoFilter } from '../hooks/useLogoFilter'

interface IntegrationLogoProps {
  logoFilename?: string
  integrationName?: string
  className?: string
  luminanceThreshold?: number
  fallbackClassName?: string
}

/**
 * Integration Logo component with automatic color inversion for dark mode
 * 
 * Automatically detects if the logo is too dark for dark mode and inverts it to white
 * 
 * @param logoFilename - The logo filename (will be loaded from /assets/integrations/)
 * @param integrationName - Name of the integration (used for alt text and fallback)
 * @param className - CSS classes for the img element
 * @param luminanceThreshold - Threshold below which to invert logo (0-1, default: 0.5)
 * @param fallbackClassName - CSS classes for the fallback element when no logo
 */
export default function IntegrationLogo({
  logoFilename,
  integrationName,
  className = 'h-6 w-auto max-w-16 object-contain',
  luminanceThreshold = 0.5,
  fallbackClassName = 'text-sm text-table-row'
}: IntegrationLogoProps) {
  const { theme } = useTheme()
  const logoRef = useLogoFilter(theme, luminanceThreshold)

  if (!logoFilename) {
    return (
      <span className={fallbackClassName}>
        {integrationName || '-'}
      </span>
    )
  }

  return (
    <img
      ref={logoRef}
      src={`/assets/integrations/${logoFilename}`}
      alt={integrationName || 'Integration'}
      className={className}
      onError={(e) => {
        e.currentTarget.style.display = 'none'
        if (e.currentTarget.nextElementSibling) {
          (e.currentTarget.nextElementSibling as HTMLElement).style.display = 'inline'
        }
      }}
    />
  )
}

