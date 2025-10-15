import { motion } from 'framer-motion';
import {
  BarChart3,
  Home,
  Settings
} from 'lucide-react';
import React, { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';

interface NavigationItem {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
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
    icon: Home,
    path: '/home'
  },
  {
    id: 'dora',
    label: 'DORA Metrics',
    icon: BarChart3,
    path: '/dora',
    subItems: [
      { id: 'deployment-frequency', label: 'Deployment Frequency', path: '/dora/deployment-frequency' },
      { id: 'lead-time', label: 'Lead Time for Changes', path: '/dora/lead-time' },
      { id: 'time-to-restore', label: 'Time to Restore', path: '/dora/time-to-restore' },
      { id: 'change-failure-rate', label: 'Change Failure Rate', path: '/dora/change-failure-rate' },
      { id: 'dora-flow', label: 'DORA + Flow', path: '/dora/combined' }
    ]
  },
  {
    id: 'settings',
    label: 'Settings',
    icon: Settings,
    path: '/settings',
    adminOnly: true,
    subItems: [
      { id: 'ai-config', label: 'AI Configuration', path: '/settings/ai-config' },
      { id: 'ai-performance', label: 'AI Performance', path: '/settings/ai-performance' },
      { id: 'color-scheme', label: 'Color Scheme', path: '/settings/color-scheme' },
      { id: 'notifications', label: 'Notifications', path: '/settings/notifications' },
      { id: 'client-management', label: 'Tenant Management', path: '/settings/client-management' },
      { id: 'user-management', label: 'User Management', path: '/settings/user-management' }
    ]
  }
]

export default function CollapsedSidebar() {
  const { isAdmin } = useAuth()
  const { theme } = useTheme()
  const location = useLocation()
  const [hoveredItem, setHoveredItem] = useState<string | null>(null)
  const [openSubmenu, setOpenSubmenu] = useState<string | null>(null)
  const [tooltipPosition, setTooltipPosition] = useState({ x: 0, y: 0 })
  const [isHoveringSubmenu, setIsHoveringSubmenu] = useState(false)
  const hoverTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const sidebarRef = useRef<HTMLDivElement>(null)
  const submenuRef = useRef<HTMLDivElement>(null)

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
      const t = event.target as Node
      const insideSidebar = sidebarRef.current?.contains(t)
      const insideSubmenu = submenuRef.current?.contains(t)
      if (!insideSidebar && !insideSubmenu) {
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
      const t = event.target as Node
      const insideSidebar = sidebarRef.current?.contains(t)
      const insideSubmenu = submenuRef.current?.contains(t)
      if (!insideSidebar && !insideSubmenu) {
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
        className="fixed left-0 w-16 z-40 overflow-visible flex flex-col"
        style={{
          top: '64px',
          height: 'calc(100vh - 64px)',
          background: 'transparent'
        }}
      >
        {/* Main Navigation - Vertically centered with dynamic height + 2 extra item spaces */}
        <div className="flex-1 flex flex-col justify-center">
          <div className="flex flex-col space-y-3 w-full overflow-visible" style={{
            backgroundColor: theme === 'dark' ? '#24292f' : '#f6f8fa',
            borderRight: theme === 'dark' ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid rgba(0, 0, 0, 0.1)',
            boxShadow: theme === 'dark'
              ? '2px 0 4px 0 rgba(0, 0, 0, 0.2), 0 -2px 4px 0 rgba(0, 0, 0, 0.1), 0 2px 4px 0 rgba(0, 0, 0, 0.1)'
              : '2px 0 4px 0 rgba(0, 0, 0, 0.1), 0 -2px 4px 0 rgba(0, 0, 0, 0.05), 0 2px 4px 0 rgba(0, 0, 0, 0.05)',
            borderTopRightRadius: '32px',
            borderBottomRightRadius: '32px',
            paddingTop: '64px',
            paddingBottom: '64px'
          }}>
            {navigationItems
              .filter(item => !item.adminOnly || isAdmin)
              .map((item) => (
                <div key={item.id} className="relative">
                  <motion.div
                    onMouseEnter={(e) => handleMouseEnter(e, item)}
                    onMouseLeave={handleMouseLeave}
                  >
                    <Link
                      to={item.path}
                      className={`w-12 h-12 flex items-center justify-center mx-auto nav-item ${isActive(item)
                        ? 'nav-item-active'
                        : 'text-secondary hover:bg-tertiary hover:text-primary'
                        }`}
                      style={isActive(item) ? {
                        background: 'var(--gradient-1-2)',
                        color: 'var(--on-gradient-1-2)'
                      } : {}}
                      onMouseEnter={(e) => {
                        if (!isActive(item)) {
                          e.currentTarget.style.border = '1px solid rgba(0, 0, 0, 0.1)'
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (!isActive(item)) {
                          e.currentTarget.style.border = 'none'
                        }
                      }}
                    >
                      <item.icon className="w-[18px] h-[18px]" />
                    </Link>
                  </motion.div>
                </div>
              ))}
          </div>
        </div>
      </aside>

      {/* Simple Tooltips for items without submenus */}
      {hoveredItem && !openSubmenu && (
        <div
          className="fixed z-[9999] pointer-events-none"
          style={{ left: tooltipPosition.x, top: tooltipPosition.y }}
        >
          {(() => {
            const item = navigationItems.find(i => i.id === hoveredItem)
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

      {/* Submenu Panels for items with subpages */}
      {openSubmenu && (
        <div
          ref={submenuRef}
          className="fixed z-[9999]"
          style={{ left: tooltipPosition.x, top: tooltipPosition.y }}
        >
          {(() => {
            const item = navigationItems.find(i => i.id === openSubmenu)
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
                  <motion.div key={subItem.id}>
                    <Link
                      to={subItem.path}
                      className={`flex items-center px-3 py-2 text-sm cursor-pointer transition-colors ${location.pathname === subItem.path
                        ? 'shadow-sm'
                        : 'text-secondary hover:bg-tertiary hover:text-primary'
                        }`}
                      style={location.pathname === subItem.path ? {
                        background: 'var(--gradient-1-2)',
                        color: 'var(--on-gradient-1-2)'
                      } : {}}
                    >
                      {subItem.label}
                    </Link>
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
