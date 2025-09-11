import axios from 'axios'
import { motion } from 'framer-motion'
import {
  BarChart3,
  ChevronDown,
  Database,
  LogOut,
  Moon,
  Rocket,
  Sun,
  User
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'
import clientLogger from '../utils/clientLogger'

interface Tenant {
  id: number
  name: string
  website?: string
  assets_folder?: string
  logo_filename?: string
  active: boolean
}

const quickActions = [
  { name: 'Run ETL Job', icon: Rocket, action: () => clientLogger.logUserAction('run_etl_job', 'quick_action_button') },
  { name: 'Generate Report', icon: BarChart3, action: () => clientLogger.logUserAction('generate_report', 'quick_action_button') }
]

const recentItems = [
  'Q4 Performance Review',
  'Team Velocity Analysis',
  'Deployment Frequency Report'
]

export default function Header() {
  const { user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const navigate = useNavigate()
  const [showUserMenu, setShowUserMenu] = useState(false)
  const [showQuickActions, setShowQuickActions] = useState(false)
  const [showRecentItems, setShowRecentItems] = useState(false)
  const [currentTenant, setCurrentTenant] = useState<Tenant | null>(null)
  const [tenantLoading, setTenantLoading] = useState(true)
  const [userProfileImage, setUserProfileImage] = useState<string | null>(null)

  // Function to get authentication token from localStorage or cookies
  const getAuthToken = () => {
    // Try localStorage first
    let token = localStorage.getItem('pulse_token')
    if (token) return token

    // Fallback to cookies
    const cookies = document.cookie.split(';')
    for (let cookie of cookies) {
      const [name, value] = cookie.trim().split('=')
      if (name === 'pulse_token') {
        return decodeURIComponent(value)
      }
    }
    return null
  }

  // Fetch current user's client information
  const fetchCurrentTenant = async () => {
    try {
      setTenantLoading(true)
      const token = getAuthToken()
      if (!token) {
        setTenantLoading(false)
        return
      }

      const response = await axios.get('/api/v1/admin/tenants', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      // Assuming the API returns the current user's tenant (should be filtered by backend)
      if (response.data && response.data.length > 0) {
        setCurrentTenant(response.data[0])
      }
    } catch (error) {
      console.error('Failed to fetch tenant information:', error)
    } finally {
      setTenantLoading(false)
    }
  }

  // Load tenant data when component mounts or user changes
  useEffect(() => {
    if (user) {
      fetchCurrentTenant()
      loadUserProfileImage()
    }
  }, [user])

  // Listen for logo update events
  useEffect(() => {
    const handleLogoUpdate = (event: CustomEvent) => {
      const { tenantId, assets_folder, logo_filename } = event.detail
      if (currentTenant && currentTenant.id === tenantId) {
        setCurrentTenant(prev => prev ? {
          ...prev,
          assets_folder,
          logo_filename
        } : null)

        // Force a small delay to ensure the file is fully written to disk
        setTimeout(() => {
          // Trigger a re-render by updating the timestamp in getLogoUrl
          setCurrentTenant(prev => prev ? { ...prev } : null)
        }, 100)
      }
    }

    window.addEventListener('logoUpdated', handleLogoUpdate as EventListener)
    return () => {
      window.removeEventListener('logoUpdated', handleLogoUpdate as EventListener)
    }
  }, [currentTenant])

  // Listen for profile image updates
  useEffect(() => {
    const handleProfileImageUpdate = () => {
      loadUserProfileImage()
    }

    window.addEventListener('profileImageUpdated', handleProfileImageUpdate)
    return () => {
      window.removeEventListener('profileImageUpdated', handleProfileImageUpdate)
    }
  }, [])

  // Function to get logo URL with cache busting
  const getLogoUrl = () => {
    if (currentTenant?.assets_folder && currentTenant?.logo_filename) {
      // Add timestamp to prevent browser caching issues
      const timestamp = Date.now()
      return `/assets/${currentTenant.assets_folder}/${currentTenant.logo_filename}?t=${timestamp}`
    }
    // Only show fallback if we're done loading and still no logo
    if (!tenantLoading) {
      return '/wex-logo-image.png'
    }
    // Return null while loading to prevent flash
    return null
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

    const first = (user.first_name || '').trim()
    const last = (user.last_name || '').trim()
    const fi = first ? first[0] : ''
    const li = last ? last[0] : ''

    // If both provided
    if (fi && li) return (fi + li).toUpperCase()

    // Derive from email username
    const uname = (user.email || '').split('@')[0]
    const parts = uname.split(/[.\-_]+/).filter(Boolean)

    if (fi && !li) {
      const second = (parts[1]?.[0]) || (parts[0]?.[1]) || ''
      const res = (fi + (second || '')).toUpperCase()
      return res || 'U'
    }
    if (!fi && li) {
      const firstFromEmail = (parts[0]?.[0]) || ''
      const res = ((firstFromEmail || '') + li).toUpperCase()
      return res || 'U'
    }

    // No names: use email parts
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
    if (parts.length === 1 && parts[0]) return parts[0].slice(0, 2).toUpperCase()
    return 'U'
  }

  const toTitle = (s?: string) => s ? (s[0].toUpperCase() + s.slice(1).toLowerCase()) : ''
  const displayName = (user?.first_name && user?.last_name)
    ? `${toTitle(user.first_name)} ${toTitle(user.last_name)}`
    : (user?.first_name || user?.last_name)
      ? toTitle(user.first_name || user.last_name)
      : (() => { const u = (user?.email || '').split('@')[0]; const parts = u.split(/[.\-_]+/).filter(Boolean); return parts.length >= 2 ? `${toTitle(parts[0])} ${toTitle(parts[1])}` : toTitle(u) })()

  // Function to load user profile image
  const loadUserProfileImage = async () => {
    try {
      const token = getAuthToken()
      if (!token) return

      const response = await axios.get('/api/v1/user/profile', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      const profileData = response.data
      if (profileData.profile_image_filename && profileData.email) {
        // Generate user folder using exact email (sanitized for filesystem)
        const userFolder = profileData.email.toLowerCase().replace('@', '_at_').replace(/\./g, '_').replace(/-/g, '_')
        const timestamp = Date.now()
        // Use client-specific folder structure: /assets/[client]/users/[email]/[filename]
        const imageUrl = `/assets/wex/users/${userFolder}/${profileData.profile_image_filename}?t=${timestamp}`
        setUserProfileImage(imageUrl)
      } else {
        setUserProfileImage(null)
      }
    } catch (error) {
      console.error('Failed to load user profile image:', error)
      setUserProfileImage(null)
    }
  }

  return (
    <header className="bg-secondary border-b border-default h-16 flex items-center justify-between px-6 sticky top-0 z-50">
      {/* Logo and Title */}
      <div className="flex items-center">
        {/* Tenant Logo */}
        <div className="h-8 flex items-center" style={{ minWidth: '32px', maxWidth: '120px' }}>
          {tenantLoading ? (
            // Loading placeholder - subtle animation
            <div className="h-6 w-20 bg-gray-200 rounded animate-pulse"></div>
          ) : getLogoUrl() ? (
            <img
              src={getLogoUrl()}
              alt={`${currentTenant?.name || 'Tenant'} Logo`}
              className="h-full max-w-full object-contain"
            />
          ) : (
            // Fallback text when no logo is available
            <span className="text-sm font-medium text-primary whitespace-nowrap">
              {currentTenant?.name || 'Tenant'}
            </span>
          )}
        </div>

        {/* Adaptive Divider - closer spacing */}
        <div className="h-6 w-px bg-gray-300 dark:bg-gray-600 mx-3"></div>

        {/* Pulse Brand - closer spacing */}
        <div className="flex items-center space-x-2">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center"
            style={{ background: 'var(--gradient-1-2)' }}
          >
            <span className="text-sm font-bold" style={{ color: 'var(--on-gradient-1-2)' }}>P</span>
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
            className="p-2 rounded-lg nav-item bg-tertiary hover:bg-tertiary hover:text-primary transition-all"
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
                  <action.icon className="w-4 h-4" />
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
            className="p-2 rounded-lg nav-item bg-tertiary hover:bg-tertiary hover:text-primary transition-all relative"
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
              // Detect if Ctrl+Click or Cmd+Click (open in new tab)
              const openInNewTab = e.ctrlKey || e.metaKey;
              handleETLDirectNavigation(openInNewTab);
              return false;
            }}
            onAuxClick={(e) => {
              // Handle middle mouse button click (also opens in new tab)
              if (e.button === 1) {
                e.preventDefault();
                handleETLDirectNavigation(true);
                return false;
              }
            }}
            className="p-2 rounded-lg nav-item bg-tertiary hover:bg-tertiary hover:text-primary transition-all inline-block"

            aria-label="ETL Management"
            title="ETL Management (Ctrl+Click for new tab)"
          >
            <Database className="w-5 h-5" />
          </motion.a>
        )}

        {/* Theme Toggle */}
        <motion.button
          onClick={toggleTheme}
          className="p-2 rounded-lg nav-item bg-tertiary hover:bg-tertiary hover:text-primary transition-all"

          aria-label="Toggle theme"
          title="Toggle Theme"
        >
          {theme === 'light' ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
        </motion.button>

        {/* User Menu */}
        <div className="relative" ref={userMenuRef}>
          <motion.button
            onClick={() => setShowUserMenu(!showUserMenu)}
            className="flex items-center space-x-2 p-2 rounded-lg nav-item bg-tertiary hover:bg-tertiary hover:text-primary transition-all"
          >
            {userProfileImage ? (
              <img
                src={userProfileImage}
                alt="Profile"
                className="w-8 h-8 rounded-full object-cover border border-tertiary"
              />
            ) : (
              <div className="w-8 h-8 rounded-full flex items-center justify-center" style={{ background: 'linear-gradient(135deg, var(--color-3), var(--color-4))' }}>
                <span className="text-sm font-medium" style={{ color: 'var(--on-gradient-3-4)' }}>
                  {getUserInitials(user)}
                </span>
              </div>
            )}
            <span className="text-sm font-medium text-primary hidden md:block">
              {displayName}
            </span>
            <ChevronDown className="w-4 h-4 text-secondary" />
          </motion.button>

          {/* User Dropdown */}
          {showUserMenu && (
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: -10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              className="absolute right-0 mt-2 w-64 card p-2 space-y-1"
            >
              <div className="px-3 py-2 border-b border-default">
                <p className="text-sm font-medium text-primary">{displayName}</p>
                <p className="text-xs text-muted">{user?.email}</p>
                <p className="text-xs text-muted">{user?.role}</p>
              </div>
              <button
                onClick={() => {
                  navigate('/profile')
                  setShowUserMenu(false)
                }}
                className="w-full text-left px-3 py-2 text-sm text-secondary hover:bg-tertiary rounded-md transition-colors flex items-center space-x-2 nav-item"
              >
                <User className="w-4 h-4" />
                <span>Profile Settings</span>
              </button>
              <hr className="border-default" />
              <button
                onClick={logout}
                className="w-full text-left px-3 py-2 text-sm rounded-md transition-colors flex items-center space-x-2 nav-item"
                style={{
                  color: 'var(--status-error)',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.1)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'transparent'
                }}
              >
                <LogOut className="w-4 h-4" />
                <span>Sign Out</span>
              </button>
            </motion.div>
          )}
        </div>
      </div>
    </header>
  )
}
