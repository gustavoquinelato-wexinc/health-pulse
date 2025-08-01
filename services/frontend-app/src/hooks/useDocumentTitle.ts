import { useEffect } from 'react'

/**
 * Custom hook to set the document title
 * @param title - The title to set (without the "Pulse - " prefix)
 * @param includePrefix - Whether to include "Pulse - " prefix (default: true)
 */
export function useDocumentTitle(title: string, includePrefix: boolean = true) {
  useEffect(() => {
    const previousTitle = document.title
    
    if (includePrefix) {
      document.title = `Pulse - ${title}`
    } else {
      document.title = title
    }

    // Cleanup function to restore previous title
    return () => {
      document.title = previousTitle
    }
  }, [title, includePrefix])
}

export default useDocumentTitle
