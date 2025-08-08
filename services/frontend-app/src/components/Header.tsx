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

interface Client {
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
  const [currentClient, setCurrentClient] = useState<Client | null>(null)
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
  const fetchCurrentClient = async () => {
    try {
      const token = getAuthToken()
      if (!token) return

      const response = await axios.get('/api/v1/admin/clients', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      // Assuming the API returns the current user's client (should be filtered by backend)
      if (response.data && response.data.length > 0) {
        setCurrentClient(response.data[0])
      }
    } catch (error) {
      console.error('Failed to fetch client information:', error)
    }
  }

  // Load client data when component mounts or user changes
  useEffect(() => {
    if (user) {
      fetchCurrentClient()
      loadUserProfileImage()
    }
  }, [user])

  // Listen for logo update events
  useEffect(() => {
    const handleLogoUpdate = (event: CustomEvent) => {
      const { clientId, assets_folder, logo_filename } = event.detail
      if (currentClient && currentClient.id === clientId) {
        setCurrentClient(prev => prev ? {
          ...prev,
          assets_folder,
          logo_filename
        } : null)
      }
    }

    window.addEventListener('logoUpdated', handleLogoUpdate as EventListener)
    return () => {
      window.removeEventListener('logoUpdated', handleLogoUpdate as EventListener)
    }
  }, [currentClient])

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
    if (currentClient?.assets_folder && currentClient?.logo_filename) {
      // Add timestamp to prevent browser caching issues
      const timestamp = Date.now()
      return `/assets/${currentClient.assets_folder}/${currentClient.logo_filename}?t=${timestamp}`
    }
    // Fallback to default WEX logo
    return '/wex-logo-image.png'
  }

  // Simple ETL navigation function (subdomain cookies handle authentication)
  const handleETLDirectNavigation = (openInNewTab = false) => {
    const ETL_SERVICE_URL = import.meta.env.VITE_ETL_SERVICE_URL || 'http://localhost:8000'

    if (openInNewTab) {
      // Open in new tab
      window.open(`${ETL_SERVICE_URL}/home`, '_blank')
    } else {
      // Navigate in same page
      window.location.href = `${ETL_SERVICE_URL}/home`
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
      <div className="flex items-center space-x-4">
        {/* Client Logo */}
        <div className="h-8">
          <img
            src={getLogoUrl()}
            alt={`${currentClient?.name || 'Client'} Logo`}
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
            className="p-2 rounded-lg nav-item bg-tertiary hover:bg-primary transition-colors inline-block"

            aria-label="ETL Management"
            title="ETL Management (Ctrl+Click for new tab)"
          >
            <Database className="w-5 h-5" />
          </motion.a>
        )}

        {/* Theme Toggle */}
        <motion.button
          onClick={toggleTheme}
          className="p-2 rounded-lg nav-item bg-tertiary hover:bg-primary transition-colors"

          aria-label="Toggle theme"
          title="Toggle Theme"
        >
          {theme === 'light' ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
        </motion.button>

        {/* User Menu */}
        <div className="relative" ref={userMenuRef}>
          <motion.button
            onClick={() => setShowUserMenu(!showUserMenu)}
            className="flex items-center space-x-2 p-2 rounded-lg nav-item bg-tertiary hover:bg-primary transition-colors"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            {userProfileImage ? (
              <img
                src={userProfileImage}
                alt="Profile"
                className="w-8 h-8 rounded-full object-cover border border-tertiary"
              />
            ) : (
              <div className="w-8 h-8 rounded-full flex items-center justify-center" style={{ background: 'linear-gradient(135deg, var(--color-3), var(--color-4))' }}>
                <span className="text-sm font-medium text-white">
                  {getUserInitials(user)}
                </span>
              </div>
            )}
            <span className="text-sm font-medium text-primary hidden md:block">
              {user?.name || user?.email}
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
                <p className="text-sm font-medium text-primary">{user?.name || user?.email}</p>
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
                className="w-full text-left px-3 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md transition-colors flex items-center space-x-2 nav-item"
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
