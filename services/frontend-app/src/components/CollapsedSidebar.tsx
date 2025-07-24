import { motion } from 'framer-motion'
import React, { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

const navigationItems = [
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
  }
]

const secondaryItems = [
  {
    id: 'settings',
    label: 'Settings',
    icon: '🔧',
    path: '/settings'
  }
]

export default function CollapsedSidebar() {
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

  // Exact gustractor_pulse approach
  const handleMouseEnter = (e: React.MouseEvent, item: any) => {
    clearHoverTimeout()

    const rect = e.currentTarget.getBoundingClientRect()
    setTooltipPosition({ x: rect.right + 8, y: rect.top })
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







  const handleNavClick = (path: string) => {
    navigate(path)
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
          {navigationItems.map((item) => (
            <div key={item.id} className="relative">
              <motion.button
                onClick={() => handleNavClick(item.path)}
                onMouseEnter={(e) => handleMouseEnter(e, item)}
                onMouseLeave={handleMouseLeave}
                className={`w-12 h-12 flex items-center justify-center rounded-lg mx-auto transition-all duration-200 ${isActive(item)
                  ? 'bg-gradient-to-br from-blue-600 to-violet-600 text-white shadow-lg'
                  : 'text-secondary hover:bg-tertiary hover:text-primary hover:scale-105'
                  }`}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
              >
                <span className="text-lg">{item.icon}</span>
              </motion.button>
            </div>
          ))}
        </div>

        {/* Settings at Bottom */}
        <div className="border-t border-default px-2 py-4">
          {secondaryItems.map((item) => (
            <div key={item.id} className="relative">
              <motion.button
                onClick={() => handleNavClick(item.path)}
                onMouseEnter={(e) => handleMouseEnter(e, item)}
                onMouseLeave={handleMouseLeave}
                className={`w-12 h-12 flex items-center justify-center rounded-lg mx-auto transition-all duration-200 ${isActive(item)
                  ? 'bg-gradient-to-br from-blue-600 to-violet-600 text-white shadow-lg'
                  : 'text-secondary hover:bg-tertiary hover:text-primary hover:scale-105'
                  }`}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
              >
                <span className="text-lg">{item.icon}</span>
              </motion.button>
            </div>
          ))}
        </div>
      </aside>

      {/* Simple Tooltips for items without submenus */}
      {hoveredItem && !openSubmenu && (
        <div
          className="fixed z-50 pointer-events-none"
          style={{ left: tooltipPosition.x, top: tooltipPosition.y }}
        >
          {(() => {
            const item = [...navigationItems, ...secondaryItems].find(i => i.id === hoveredItem)
            if (!item || (item as any).subItems) return null

            return (
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="bg-gray-900 text-white px-3 py-2 rounded-lg text-sm font-medium whitespace-nowrap"
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
          className="fixed z-50"
          style={{ left: tooltipPosition.x, top: tooltipPosition.y }}
        >
          {(() => {
            const item = navigationItems.find(i => i.id === openSubmenu)
            if (!item || !item.subItems) return null

            return (
              <motion.div
                initial={{ opacity: 0, scale: 0.95, x: -10 }}
                animate={{ opacity: 1, scale: 1, x: 0 }}
                className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-xl py-2 min-w-48"
                onMouseEnter={handleSubmenuMouseEnter}
                onMouseLeave={handleSubmenuMouseLeave}
              >
                <div className="px-3 py-2 text-sm font-medium text-gray-900 dark:text-gray-100 border-b border-gray-200 dark:border-gray-700">
                  {item.label}
                </div>
                {item.subItems.map(subItem => (
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
                      ? 'bg-gradient-to-br from-blue-600 to-violet-600 text-white shadow-sm'
                      : 'text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700'
                      }`}
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
