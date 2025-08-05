import { motion } from 'framer-motion';
import React, { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

interface NavigationItem {
  id: string;
  label: string;
  icon: string;
  path: string;
  adminOnly?: boolean;
  isAction?: boolean;
  subItems?: Array<{
    id: string;
    label: string;
    path: string;
  }>;
}

const navigationItems: NavigationItem[] = [
  {
    id: 'home',
    label: 'Home',
    icon: '🏠',
    path: '/home'
  },
  {
    id: 'dora',
    label: 'DORA Metrics',
    icon: '📊',
    path: '/dora',
    subItems: [
      { id: 'deployment-frequency', label: 'Deployment Frequency', path: '/dora/deployment-frequency' },
      { id: 'lead-time', label: 'Lead Time for Changes', path: '/dora/lead-time' },
      { id: 'time-to-restore', label: 'Time to Restore', path: '/dora/time-to-restore' },
      { id: 'change-failure-rate', label: 'Change Failure Rate', path: '/dora/change-failure-rate' }
    ]
  },
  {
    id: 'engineering',
    label: 'Engineering Analytics',
    icon: '⚙️',
    path: '/engineering'
  },

]

const secondaryItems: NavigationItem[] = [
  {
    id: 'settings',
    label: 'Settings',
    icon: '🔧',
    path: '/settings',
    subItems: [
      { id: 'color-scheme', label: 'Color Scheme', path: '/settings/color-scheme' },
      { id: 'user-preferences', label: 'User Preferences', path: '/settings/user-preferences' },
      { id: 'notifications', label: 'Notifications', path: '/settings/notifications' },
      { id: 'user-management', label: 'User Management', path: '/settings/user-management' },
      { id: 'client-management', label: 'Client Management', path: '/settings/client-management' }
    ]
  }
]

export default function CollapsedSidebar() {
  const { isAdmin } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [hoveredItem, setHoveredItem] = useState<string | null>(null)
  const [openSubmenu, setOpenSubmenu] = useState<string | null>(null)
  const [tooltipPosition, setTooltipPosition] = useState({ x: 0, y: 0 })
  const [isHoveringSubmenu, setIsHoveringSubmenu] = useState(false)
  const hoverTimeoutRef = useRef<number | null>(null)
  const sidebarRef = useRef<HTMLDivElement>(null)

  const clearHoverTimeout = () => {
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current)
      hoverTimeoutRef.current = null
    }
  }

  // Smart positioning approach
  const handleMouseEnter = (e: React.MouseEvent, item: any) => {
    clearHoverTimeout()

    const rect = e.currentTarget.getBoundingClientRect()
    const viewportHeight = window.innerHeight
    const submenuHeight = item.subItems ? (item.subItems.length * 40 + 60) : 40 // Estimate submenu height

    // Calculate optimal Y position
    let yPosition = rect.top

    // If submenu would extend below viewport, position it above the item
    if (rect.top + submenuHeight > viewportHeight) {
      yPosition = rect.bottom - submenuHeight
      // Ensure it doesn't go above the top of the viewport
      if (yPosition < 0) {
        yPosition = Math.max(0, viewportHeight - submenuHeight - 10)
      }
    }

    setTooltipPosition({ x: rect.right + 8, y: yPosition })
    setHoveredItem(item.id)

    // For items with submenus, show the submenu panel immediately
    if (item.subItems) {
      setOpenSubmenu(item.id)
    } else {
      setOpenSubmenu(null)
    }
  }

  const handleMouseLeave = () => {
    clearHoverTimeout()

    // For simple items, hide tooltip immediately
    if (hoveredItem && !openSubmenu) {
      setHoveredItem(null)
      return
    }

    // For submenu items, use a delay to allow moving to the submenu
    hoverTimeoutRef.current = setTimeout(() => {
      if (!isHoveringSubmenu) {
        setHoveredItem(null)
        setOpenSubmenu(null)
      }
    }, 200) // 200ms delay like gustractor_pulse
  }

  const handleSubmenuMouseEnter = () => {
    clearHoverTimeout()
    setIsHoveringSubmenu(true)
  }

  const handleSubmenuMouseLeave = () => {
    setTimeout(() => {
      setIsHoveringSubmenu(false)
      setHoveredItem(null)
      setOpenSubmenu(null)
    }, 100) // 100ms delay like gustractor_pulse
  }







  const handleNavClick = (path: string, item?: NavigationItem, openInNewTab = false) => {
    // Handle special actions
    if (item?.isAction) {
      if (item.id === 'etl-direct') {
        handleETLDirectNavigation(openInNewTab)
        return
      }
    }

    // Regular navigation
    navigate(path)
  }

  // POST-based ETL navigation function
  const handleETLDirectNavigation = async (openInNewTab = false) => {
    const token = localStorage.getItem('pulse_token')
    if (!token) {
      console.error('No authentication token found')
      return
    }

    try {
      const ETL_SERVICE_URL = import.meta.env.VITE_ETL_SERVICE_URL || 'http://localhost:8000'
      const API_BASE_URL = import.meta.env.DEV ? '' : (import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001')

      // Step 1: Setup ETL access via Backend Service
      console.log('Setting up ETL access...')
      const setupResponse = await fetch(`${API_BASE_URL}/auth/setup-etl-access`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        credentials: 'include'
      })

      if (!setupResponse.ok) {
        console.error('Failed to setup ETL access:', setupResponse.statusText)
        return
      }

      const setupData = await setupResponse.json()
      const etlToken = setupData.token

      // Step 2: Navigate to ETL service with the token
      const response = await fetch(`${ETL_SERVICE_URL}/auth/navigate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          token: etlToken,
          return_url: window.location.href
        }),
        credentials: 'include' // Important for cookies
      })

      if (response.ok) {
        const data = await response.json()
        if (data.redirect_url) {
          if (openInNewTab) {
            // Right click: Open in new tab without switching focus
            window.open(`${ETL_SERVICE_URL}${data.redirect_url}`, '_blank')

            // Immediately refocus current window to prevent tab switch
            setTimeout(() => {
              window.focus()
            }, 10)
          } else {
            // Normal click: Navigate in same page (like ETL service behavior)
            window.location.href = `${ETL_SERVICE_URL}${data.redirect_url}`
          }
        }
      } else {
        console.error('ETL navigation failed:', response.statusText)
      }
    } catch (error) {
      console.error('Failed to navigate to ETL service:', error)
    }
  }

  const isActive = (item: any) => {
    if (item.path === '/home' && location.pathname === '/home') return true
    if (item.path !== '/home' && location.pathname.startsWith(item.path)) return true
    if (item.subItems) {
      return item.subItems.some((subItem: any) => location.pathname === subItem.path)
    }
    return false
  }

  // Cleanup & Outside Click Handling - gustractor_pulse approach
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (sidebarRef.current && !sidebarRef.current.contains(event.target as Node)) {
        clearHoverTimeout()
        setOpenSubmenu(null)
        setHoveredItem(null)
        setIsHoveringSubmenu(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      clearHoverTimeout()
    }
  }, [])

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (sidebarRef.current && !sidebarRef.current.contains(event.target as Node)) {
        clearHoverTimeout()
        setOpenSubmenu(null)
        setHoveredItem(null)
        setIsHoveringSubmenu(false)
        // Remove any existing native submenu
        const existing = document.getElementById('native-submenu')
        if (existing) existing.remove()
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      clearHoverTimeout()
      // Clean up native submenu on unmount
      const existing = document.getElementById('native-submenu')
      if (existing) existing.remove()
    }
  }, [])

  return (
    <>
      {/* Collapsed Sidebar */}
      <aside
        ref={sidebarRef}
        className="fixed left-0 top-16 h-[calc(100vh-4rem)] w-16 bg-secondary border-r border-default shadow-lg z-40 overflow-visible flex flex-col"
      >
        {/* Main Navigation */}
        <div className="flex-1 flex flex-col space-y-2 py-4 px-2">
          {navigationItems
            .filter(item => !item.adminOnly || isAdmin) // Filter admin-only items
            .map((item) => (
              <div key={item.id} className="relative">
                <motion.button
                  onClick={() => handleNavClick(item.path, item, false)}
                  onContextMenu={(e) => {
                    e.preventDefault();
                    handleNavClick(item.path, item, true);
                  }}
                  onMouseEnter={(e) => handleMouseEnter(e, item)}
                  onMouseLeave={handleMouseLeave}
                  className={`w-12 h-12 flex items-center justify-center rounded-lg mx-auto transition-all duration-200 ${isActive(item)
                    ? 'text-white shadow-lg'
                    : 'text-secondary hover:bg-tertiary hover:text-primary hover:scale-105'
                    }`}
                  style={isActive(item) ? {
                    background: `linear-gradient(to bottom right, var(--color-1), var(--color-2))`
                  } : {}}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                >
                  <span className="text-lg">{item.icon}</span>
                </motion.button>
              </div>
            ))}
        </div>

        {/* Settings at Bottom - Admin Only */}
        {isAdmin && (
          <div className="border-t border-default px-2 py-4">
            {secondaryItems.map((item) => (
              <div key={item.id} className="relative">
                <motion.button
                  onClick={() => handleNavClick(item.path, item)}
                  onMouseEnter={(e) => handleMouseEnter(e, item)}
                  onMouseLeave={handleMouseLeave}
                  className={`w-12 h-12 flex items-center justify-center rounded-lg mx-auto transition-all duration-200 ${isActive(item)
                    ? 'text-white shadow-lg'
                    : 'text-secondary hover:bg-tertiary hover:text-primary hover:scale-105'
                    }`}
                  style={isActive(item) ? {
                    background: `linear-gradient(to bottom right, var(--color-1), var(--color-2))`
                  } : {}}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                >
                  <span className="text-lg">{item.icon}</span>
                </motion.button>
              </div>
            ))}
          </div>
        )}
      </aside>

      {/* Simple Tooltips for items without submenus */}
      {hoveredItem && !openSubmenu && (
        <div
          className="fixed z-[9999] pointer-events-none"
          style={{ left: tooltipPosition.x, top: tooltipPosition.y }}
        >
          {(() => {
            const item = [...navigationItems, ...secondaryItems].find(i => i.id === hoveredItem)
            if (!item || (item as any).subItems) return null

            return (
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="bg-secondary border border-default text-primary px-3 py-2 rounded-lg text-sm font-medium whitespace-nowrap shadow-lg"
              >
                {item.label}
              </motion.div>
            )
          })()}
        </div>
      )}

      {/* Submenu Panels for items with subpages - gustractor_pulse approach */}
      {openSubmenu && (
        <div
          className="fixed z-[9999]"
          style={{ left: tooltipPosition.x, top: tooltipPosition.y }}
        >
          {(() => {
            const item = [...navigationItems, ...secondaryItems].find(i => i.id === openSubmenu)
            if (!item || !(item as any).subItems) return null

            return (
              <motion.div
                initial={{ opacity: 0, scale: 0.95, x: -10 }}
                animate={{ opacity: 1, scale: 1, x: 0 }}
                className="bg-secondary border border-default rounded-lg shadow-xl py-2 min-w-48"
                onMouseEnter={handleSubmenuMouseEnter}
                onMouseLeave={handleSubmenuMouseLeave}
              >
                <div className="px-3 py-2 text-sm font-medium text-primary border-b border-default">
                  {item.label}
                </div>
                {(item as any).subItems.map((subItem: any) => (
                  <motion.div
                    key={subItem.id}
                    onMouseDown={(e) => {
                      e.preventDefault()
                      e.stopPropagation()

                      // Keep submenu open during click (gustractor_pulse approach)
                      clearHoverTimeout()
                      setIsHoveringSubmenu(true)

                      // Navigate
                      navigate(subItem.path)

                      // Close the submenu after a short delay (gustractor_pulse timing)
                      setTimeout(() => {
                        setHoveredItem(null)
                        setOpenSubmenu(null)
                        setIsHoveringSubmenu(false)
                      }, 50)
                    }}
                    className={`flex items-center px-3 py-2 text-sm cursor-pointer transition-colors ${location.pathname === subItem.path
                      ? 'text-white shadow-sm'
                      : 'text-secondary hover:bg-tertiary hover:text-primary'
                      }`}
                    style={location.pathname === subItem.path ? {
                      background: `linear-gradient(to bottom right, var(--color-1), var(--color-2))`
                    } : {}}
                    whileHover={{ x: 4 }}
                  >
                    {subItem.label}
                  </motion.div>
                ))}
              </motion.div>
            )
          })()}
        </div>
      )}
    </>
  )
}
