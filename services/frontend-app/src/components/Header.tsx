import { motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'
import clientLogger from '../utils/clientLogger'

const quickActions = [
  { name: 'Run ETL Job', icon: '🚀', action: () => clientLogger.logUserAction('run_etl_job', 'quick_action_button') },
  { name: 'Generate Report', icon: '📊', action: () => clientLogger.logUserAction('generate_report', 'quick_action_button') }
]

const recentItems = [
  'Q4 Performance Review',
  'Team Velocity Analysis',
  'Deployment Frequency Report'
]

export default function Header() {
  const { user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const [showUserMenu, setShowUserMenu] = useState(false)
  const [showQuickActions, setShowQuickActions] = useState(false)
  const [showRecentItems, setShowRecentItems] = useState(false)

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

  const userMenuRef = useRef<HTMLDivElement>(null)
  const quickActionsRef = useRef<HTMLDivElement>(null)
  const recentItemsRef = useRef<HTMLDivElement>(null)

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      // Close user menu if clicking outside
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setShowUserMenu(false)
      }

      // Close quick actions if clicking outside
      if (quickActionsRef.current && !quickActionsRef.current.contains(event.target as Node)) {
        setShowQuickActions(false)
      }

      // Close recent items if clicking outside
      if (recentItemsRef.current && !recentItemsRef.current.contains(event.target as Node)) {
        setShowRecentItems(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [])

  // Helper function to get user initials from first and last name
  const getUserInitials = (user: any) => {
    if (!user) return 'U'

    // Try to extract first and last name from the full name
    const fullName = user.name || user.email
    const nameParts = fullName.split(' ')

    if (nameParts.length >= 2) {
      // Use first letter of first name + first letter of last name
      return (nameParts[0][0] + nameParts[nameParts.length - 1][0]).toUpperCase()
    } else if (fullName && fullName !== user.email) {
      // Use first letter of name
      return fullName[0].toUpperCase()
    } else {
      // Fallback to email
      return user.email?.[0]?.toUpperCase() || 'U'
    }
  }

  return (
    <header className="bg-secondary border-b border-default h-16 flex items-center justify-between px-6 sticky top-0 z-50">
      {/* Logo and Title */}
      <div className="flex items-center space-x-4">
        {/* WEX Logo */}
        <div className="h-8">
          <img
            src="/wex-logo-image.png"
            alt="WEX Logo"
            className="h-full object-contain"
          />
        </div>

        {/* Divider */}
        <div className="h-6 w-px bg-gray-300 dark:bg-gray-600"></div>

        {/* Pulse Brand */}
        <div className="flex items-center space-x-2">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center"
            style={{ background: 'linear-gradient(to bottom right, var(--color-1), var(--color-2))' }}
          >
            <span className="text-sm font-bold text-white">P</span>
          </div>
          <div>
            <h1 className="text-lg font-semibold text-primary">PULSE</h1>
          </div>
        </div>
      </div>

      {/* Search Bar */}
      <div className="flex-1 max-w-md mx-8">
        <div className="relative">
          <input
            type="text"
            placeholder="Search analytics... (Cmd+K)"
            className="input w-full pl-10 pr-4 py-2"
          />
          <div className="absolute left-3 top-1/2 transform -translate-y-1/2">
            <svg className="w-4 h-4 text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
        </div>
      </div>

      {/* Right Side Actions */}
      <div className="flex items-center space-x-4">
        {/* Quick Actions */}
        <div className="relative" ref={quickActionsRef}>
          <motion.button
            onClick={() => setShowQuickActions(!showQuickActions)}
            className="p-2 rounded-lg bg-tertiary hover:bg-primary transition-colors"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            aria-label="Quick Actions"
            title="Quick Actions"
          >
            <svg className="w-5 h-5 text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </motion.button>

          {/* Quick Actions Dropdown */}
          {showQuickActions && (
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: -10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              className="absolute right-0 mt-2 w-48 card p-2 space-y-1"
            >
              <div className="px-3 py-2 border-b border-default">
                <p className="text-sm font-medium text-primary">Quick Actions</p>
              </div>
              {quickActions.map((action, index) => (
                <button
                  key={index}
                  onClick={() => {
                    action.action()
                    setShowQuickActions(false)
                  }}
                  className="w-full text-left px-3 py-2 text-sm text-secondary hover:bg-tertiary rounded-md transition-colors flex items-center space-x-2"
                >
                  <span>{action.icon}</span>
                  <span>{action.name}</span>
                </button>
              ))}
            </motion.div>
          )}
        </div>

        {/* Recent Items */}
        <div className="relative" ref={recentItemsRef}>
          <motion.button
            onClick={() => setShowRecentItems(!showRecentItems)}
            className="p-2 rounded-lg bg-tertiary hover:bg-primary transition-colors relative"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            aria-label="Recent Items"
            title="Recent Items"
          >
            <svg className="w-5 h-5 text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="absolute -top-1 -right-1 w-2 h-2 bg-blue-500 rounded-full"></span>
          </motion.button>

          {/* Recent Items Dropdown */}
          {showRecentItems && (
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: -10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              className="absolute right-0 mt-2 w-64 card p-2 space-y-1"
            >
              <div className="px-3 py-2 border-b border-default">
                <p className="text-sm font-medium text-primary">Recent</p>
              </div>
              {recentItems.map((item, index) => (
                <button
                  key={index}
                  onClick={() => setShowRecentItems(false)}
                  className="w-full text-left px-3 py-2 text-sm text-secondary hover:bg-tertiary rounded-md transition-colors flex items-center space-x-2"
                >
                  <div className="w-2 h-2 bg-blue-400 rounded-full"></div>
                  <span className="truncate">{item}</span>
                </button>
              ))}
            </motion.div>
          )}
        </div>

        {/* ETL Management */}
        {user?.role === 'admin' && (
          <motion.a
            href={`${import.meta.env.VITE_ETL_SERVICE_URL || 'http://localhost:8000'}/home`}
            onClick={(e) => {
              e.preventDefault();
              // Normal left click: navigate in same page with authentication
              handleETLDirectNavigation(false);
              return false;
            }}
            className="p-2 rounded-lg bg-tertiary hover:bg-primary transition-colors inline-block"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            aria-label="ETL Management"
            title="ETL Management"
          >
            <img src="/archive-solid-svgrepo-com.svg" alt="ETL Management" width="20" height="20" />
          </motion.a>
        )}

        {/* Theme Toggle */}
        <motion.button
          onClick={toggleTheme}
          className="p-2 rounded-lg bg-tertiary hover:bg-primary transition-colors"
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          aria-label="Toggle theme"
          title="Toggle Theme"
        >
          {theme === 'light' ? '🌙' : '☀️'}
        </motion.button>

        {/* User Menu */}
        <div className="relative" ref={userMenuRef}>
          <motion.button
            onClick={() => setShowUserMenu(!showUserMenu)}
            className="flex items-center space-x-2 p-2 rounded-lg bg-tertiary hover:bg-primary transition-colors"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            <div className="w-8 h-8 rounded-full flex items-center justify-center" style={{ background: 'linear-gradient(135deg, var(--color-3), var(--color-4))' }}>
              <span className="text-sm font-medium text-white">
                {getUserInitials(user)}
              </span>
            </div>
            <span className="text-sm font-medium text-primary hidden md:block">
              {user?.name || user?.email}
            </span>
          </motion.button>

          {/* User Dropdown */}
          {showUserMenu && (
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: -10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              className="absolute right-0 mt-2 w-64 card p-2 space-y-1"
            >
              <div className="px-3 py-2 border-b border-default">
                <p className="text-sm font-medium text-primary">{user?.name || user?.email}</p>
                <p className="text-xs text-muted">{user?.email}</p>
                <p className="text-xs text-muted">{user?.role}</p>
              </div>
              <button className="w-full text-left px-3 py-2 text-sm text-secondary hover:bg-tertiary rounded-md transition-colors">
                Profile Settings
              </button>
              <button className="w-full text-left px-3 py-2 text-sm text-secondary hover:bg-tertiary rounded-md transition-colors">
                Preferences
              </button>
              <hr className="border-default" />
              <button
                onClick={logout}
                className="w-full text-left px-3 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md transition-colors"
              >
                Sign Out
              </button>
            </motion.div>
          )}
        </div>
      </div>
    </header>
  )
}
