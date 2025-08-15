import { motion } from 'framer-motion';
import {
  BarChart3,
  Home,
  Settings,
  TrendingUp
} from 'lucide-react';
import React, { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

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
    id: 'engineering',
    label: 'Engineering Analytics',
    icon: TrendingUp,
    path: '/engineering',
    subItems: [
      { id: 'lead-time', label: 'Lead-Time Drivers', path: '/engineering/lead-time' },
      { id: 'lead-time-pr', label: '• PR Lifecycle', path: '/engineering/lead-time/pr-lifecycle' },
      { id: 'lead-time-reviews', label: '• Reviews', path: '/engineering/lead-time/reviews' },
      { id: 'lead-time-wip', label: '• WIP & Batch Size', path: '/engineering/lead-time/wip-batch' },
      { id: 'lead-time-flow', label: '• Flow Efficiency', path: '/engineering/lead-time/flow-efficiency' },
      { id: 'deployments', label: 'Deployment Drivers', path: '/engineering/deployments' },
      { id: 'deployments-branching', label: '• Branching & Merge Strategy', path: '/engineering/deployments/branching' },
      { id: 'deployments-cadence', label: '• Cadence', path: '/engineering/deployments/cadence' },
      { id: 'quality', label: 'Quality Drivers', path: '/engineering/quality' },
      { id: 'quality-post-release', label: '• Post-Release Defects', path: '/engineering/quality/post-release' },
      { id: 'quality-hotfixes', label: '• Hotfixes', path: '/engineering/quality/hotfixes' },
      { id: 'reliability', label: 'Reliability Drivers', path: '/engineering/reliability' },
      { id: 'reliability-incidents', label: '• Incidents', path: '/engineering/reliability/incidents' },
      { id: 'reliability-recovery', label: '• Recovery', path: '/engineering/reliability/recovery' }
    ]
  },

]



// Admin settings - only for admins
const adminItems: NavigationItem[] = [
  {
    id: 'admin',
    label: 'System Overview',
    icon: Settings,
    path: '/admin',
    subItems: [
      { id: 'color-scheme', label: 'Color Scheme', path: '/admin/color-scheme' },
      { id: 'user-management', label: 'User Management', path: '/admin/user-management' },
      { id: 'client-management', label: 'Client Management', path: '/admin/client-management' },
      { id: 'notifications', label: 'Notifications', path: '/admin/notifications' }
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

  // ETL navigation function with color data transfer
  const handleETLDirectNavigation = (openInNewTab = false) => {
    const ETL_SERVICE_URL = import.meta.env.VITE_ETL_SERVICE_URL || 'http://localhost:8000'

    // Transfer color data to ETL service via URL parameters
    try {
      const completeColorData = localStorage.getItem('pulse_complete_color_data')
      const theme = localStorage.getItem('pulse_theme') || 'light'
      const mode = localStorage.getItem('pulse_color_schema_mode') || 'default'

      let targetUrl = `${ETL_SERVICE_URL}/home`

      // Add color data as URL parameters if available
      if (completeColorData) {
        const params = new URLSearchParams()
        params.set('color_data', encodeURIComponent(completeColorData))
        params.set('theme', theme)
        params.set('mode', mode)
        targetUrl += `?${params.toString()}`
      }

      if (openInNewTab) {
        // Open in new tab
        window.open(targetUrl, '_blank')
      } else {
        // Navigate in same page
        window.location.href = targetUrl
      }
    } catch (error) {
      console.warn('Failed to transfer color data to ETL, using basic navigation:', error)
      // Fallback to basic navigation
      const basicUrl = `${ETL_SERVICE_URL}/home`
      if (openInNewTab) {
        window.open(basicUrl, '_blank')
      } else {
        window.location.href = basicUrl
      }
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
        className="fixed left-0 top-16 h-[calc(100vh-4rem)] w-16 sidebar-container z-40 overflow-visible flex flex-col"
      >
        {/* Main Navigation */}
        <div className="flex-1 flex flex-col justify-center space-y-3 px-2">
          {navigationItems
            .filter(item => !item.adminOnly || isAdmin) // Filter admin-only items
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
                  >
                    <item.icon className="w-5 h-5" />
                  </Link>
                </motion.div>
              </div>
            ))}
        </div>



        {/* System Overview & Admin Settings - Admin Only */}
        {isAdmin && (
          <div className="border-t border-default px-2 py-4">
            {adminItems.map((item) => (
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
                  >
                    <item.icon className="w-5 h-5" />
                  </Link>
                </motion.div>
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
            const item = [...navigationItems, ...adminItems].find(i => i.id === hoveredItem)
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
          ref={submenuRef}
          className="fixed z-[9999]"
          style={{ left: tooltipPosition.x, top: tooltipPosition.y }}
        >
          {(() => {
            const item = [...navigationItems, ...adminItems].find(i => i.id === openSubmenu)
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
