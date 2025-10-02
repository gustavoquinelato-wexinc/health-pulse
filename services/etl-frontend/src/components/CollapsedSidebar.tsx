import { motion } from 'framer-motion'
import {
  Database,
  Home,
  List,
  Plug,
  RefreshCw
} from 'lucide-react'
import React, { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'

interface NavigationItem {
  id: string
  label: string
  icon: React.ComponentType<{ className?: string }>
  path: string
  adminOnly?: boolean
  subItems?: Array<{
    id: string
    label: string
    path: string
  }>
}

const navigationItems: NavigationItem[] = [
  {
    id: 'home',
    label: 'Home',
    icon: Home,
    path: '/home'
  },
  {
    id: 'wits',
    label: 'Work Item Types',
    icon: List,
    path: '/wits-hierarchies',
    subItems: [
      { id: 'wits-hierarchies', label: 'Hierarchies', path: '/wits-hierarchies' },
      { id: 'wits-mappings', label: 'Mappings', path: '/wits-mappings' }
    ]
  },
  {
    id: 'statuses',
    label: 'Statuses',
    icon: RefreshCw,
    path: '/statuses-mappings',
    subItems: [
      { id: 'statuses-mappings', label: 'Mappings', path: '/statuses-mappings' },
      { id: 'workflows', label: 'Workflows', path: '/workflows' }
    ]
  },
  {
    id: 'integrations',
    label: 'Integrations',
    icon: Plug,
    path: '/integrations'
  },
  {
    id: 'qdrant',
    label: 'Qdrant',
    icon: Database,
    path: '/qdrant'
  }
]

const adminItems: NavigationItem[] = [
  // Admin-only items can be added here if needed
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

  const handleMouseEnter = (e: React.MouseEvent, item: any) => {
    clearHoverTimeout()

    const rect = e.currentTarget.getBoundingClientRect()
    const viewportHeight = window.innerHeight
    const submenuHeight = item.subItems ? (item.subItems.length * 40 + 60) : 40

    let yPosition = rect.top

    if (rect.top + submenuHeight > viewportHeight) {
      yPosition = rect.bottom - submenuHeight
      if (yPosition < 0) {
        yPosition = Math.max(0, viewportHeight - submenuHeight - 10)
      }
    }

    setTooltipPosition({ x: rect.right + 8, y: yPosition })
    setHoveredItem(item.id)

    if (item.subItems) {
      setOpenSubmenu(item.id)
    } else {
      setOpenSubmenu(null)
    }
  }

  const handleMouseLeave = () => {
    clearHoverTimeout()

    if (hoveredItem && !openSubmenu) {
      setHoveredItem(null)
      return
    }

    hoverTimeoutRef.current = setTimeout(() => {
      if (!isHoveringSubmenu) {
        setHoveredItem(null)
        setOpenSubmenu(null)
      }
    }, 200)
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
    }, 100)
  }

  const isActive = (item: any) => {
    if (item.path === '/home' && location.pathname === '/home') return true
    if (item.path !== '/home' && location.pathname.startsWith(item.path)) return true
    if (item.subItems) {
      return item.subItems.some((subItem: any) => location.pathname === subItem.path)
    }
    return false
  }

  // Cleanup & Outside Click Handling
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

  return (
    <>
      {/* Collapsed Sidebar */}
      <aside
        ref={sidebarRef}
        className="fixed left-0 top-16 h-[calc(100vh-4rem)] w-16 z-40 overflow-visible flex flex-col"
        style={{ background: 'transparent' }}
      >
        {/* Main Navigation */}
        <div className="flex-1 flex flex-col justify-center">
          <div className="flex flex-col space-y-3 py-4 w-full" style={{
            boxShadow: theme === 'dark'
              ? '0 -4px 6px -1px rgba(255, 255, 255, 0.03), 4px 0 6px -1px rgba(255, 255, 255, 0.03), 0 4px 6px -1px rgba(255, 255, 255, 0.03)'
              : '0 -4px 6px -1px rgba(0, 0, 0, 0.1), 4px 0 6px -1px rgba(0, 0, 0, 0.1), 0 4px 6px -1px rgba(0, 0, 0, 0.1)'
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
                    <item.icon className="w-5 h-5" />
                  </Link>
                </motion.div>
              </div>
            ))}
          </div>
        </div>

        {/* Admin Settings */}
        {isAdmin && (
          <div className="px-2 py-4">
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

      {/* Submenu Panels */}
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
