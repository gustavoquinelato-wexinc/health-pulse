import axios from 'axios'
import { motion } from 'framer-motion'
import {
  ChevronDown,
  LogOut,
  Moon,
  Sun,
  User
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'

interface Tenant {
  id: number
  name: string
  website?: string
  assets_folder?: string
  logo_filename?: string
  active: boolean
}

export default function Header() {
  const { user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const navigate = useNavigate()
  const [showUserMenu, setShowUserMenu] = useState(false)
  const userMenuRef = useRef<HTMLDivElement>(null)

  // Tenant state
  const [currentTenant, setCurrentTenant] = useState<Tenant | null>(null)
  const [tenantLoading, setTenantLoading] = useState(true)

  // Fetch tenant data
  useEffect(() => {
    const fetchTenant = async () => {
      try {
        setTenantLoading(true)
        const response = await axios.get('/api/v1/admin/tenants')
        if (response.data && Array.isArray(response.data) && response.data.length > 0) {
          setCurrentTenant(response.data[0]) // Get the first (current user's) tenant
        }
      } catch (error) {
        console.error('Failed to fetch tenant data:', error)
      } finally {
        setTenantLoading(false)
      }
    }

    if (user) {
      fetchTenant()
    }
  }, [user])

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setShowUserMenu(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [])

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

  // Helper function to get user initials
  const getUserInitials = (user: any) => {
    if (!user) return 'U'

    const first = (user.first_name || '').trim()
    const last = (user.last_name || '').trim()
    const fi = first ? first[0] : ''
    const li = last ? last[0] : ''

    if (fi && li) return (fi + li).toUpperCase()

    const uname = (user.email || '').split('@')[0]
    const parts = uname.split(/[.\-_]+/).filter(Boolean)

    if (fi && !li) {
      const second = (parts[1]?.[0]) || (parts[0]?.[1]) || ''
      return (fi + (second || '')).toUpperCase() || 'U'
    }
    if (!fi && li) {
      const firstFromEmail = (parts[0]?.[0]) || ''
      return ((firstFromEmail || '') + li).toUpperCase() || 'U'
    }

    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
    if (parts.length === 1 && parts[0]) return parts[0].slice(0, 2).toUpperCase()
    return 'U'
  }

  const toTitle = (s?: string) => s ? (s[0].toUpperCase() + s.slice(1).toLowerCase()) : ''
  const displayName = (user?.first_name && user?.last_name)
    ? `${toTitle(user.first_name)} ${toTitle(user.last_name)}`
    : (user?.first_name || user?.last_name)
      ? toTitle(user.first_name || user.last_name)
      : (() => { 
          const u = (user?.email || '').split('@')[0]
          const parts = u.split(/[.\-_]+/).filter(Boolean)
          return parts.length >= 2 ? `${toTitle(parts[0])} ${toTitle(parts[1])}` : toTitle(u)
        })()

  return (
    <header className="py-4 px-8 flex items-center justify-between sticky top-0 z-50 bg-primary" style={{
      boxShadow: theme === 'dark'
        ? '0 4px 6px -1px rgba(255, 255, 255, 0.1), 0 2px 4px -1px rgba(255, 255, 255, 0.06)'
        : '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
    }}>
      {/* Left Side - Logo and Title */}
      <div className="flex items-center space-x-4">
        {/* Tenant Logo */}
        <div className="h-10 flex items-center" style={{ minWidth: '40px', maxWidth: '150px' }}>
          {tenantLoading ? (
            // Loading placeholder - subtle animation
            <div className="h-6 w-20 bg-white bg-opacity-20 rounded animate-pulse"></div>
          ) : getLogoUrl() ? (
            <img
              src={getLogoUrl() || undefined}
              alt={`${currentTenant?.name || 'Tenant'} Logo`}
              className="h-full max-w-full object-contain"
              style={{ filter: theme === 'dark' ? 'brightness(0) invert(1)' : 'none' }}
            />
          ) : (
            // Fallback text when no logo is available
            <span className="text-sm font-medium text-blue-700 whitespace-nowrap">
              {currentTenant?.name || 'Tenant'}
            </span>
          )}
        </div>

        {/* Vertical Divisor */}
        <div className="h-8 w-px" style={{
          backgroundColor: theme === 'dark' ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.2)'
        }}></div>

        {/* Title Badge */}
        <div className="px-4 py-2 rounded text-sm font-medium" style={{
          background: 'var(--gradient-1-2)',
          color: 'var(--on-gradient-1-2)'
        }}>
          PULSE - ETL MANAGEMENT
        </div>
      </div>

      {/* Right Side Actions */}
      <div className="flex items-center space-x-2">
        {/* Analytics Dashboard Link */}
        <motion.a
          href={`${import.meta.env.VITE_API_BASE_URL?.replace(':3001', ':3000') || 'http://localhost:3000'}/home`}
          onClick={(e) => {
            e.preventDefault()
            const openInNewTab = e.ctrlKey || e.metaKey
            const url = `${import.meta.env.VITE_API_BASE_URL?.replace(':3001', ':3000') || 'http://localhost:3000'}/home`
            if (openInNewTab) {
              window.open(url, '_blank')
            } else {
              window.location.href = url
            }
            return false
          }}
          onAuxClick={(e) => {
            if (e.button === 1) {
              e.preventDefault()
              const url = `${import.meta.env.VITE_API_BASE_URL?.replace(':3001', ':3000') || 'http://localhost:3000'}/home`
              window.open(url, '_blank')
              return false
            }
          }}
          className="w-12 h-12 flex items-center justify-center mx-auto nav-item text-secondary hover:bg-tertiary hover:text-primary"
          style={{
            border: theme === 'dark' ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid rgba(0, 0, 0, 0.1)'
          }}
          aria-label="Analytics Dashboard"
          title="Analytics Dashboard (Ctrl+Click for new tab)"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
        </motion.a>

        {/* Theme Toggle */}
        <motion.button
          onClick={toggleTheme}
          className="w-12 h-12 flex items-center justify-center mx-auto nav-item text-secondary hover:bg-tertiary hover:text-primary"
          style={{
            border: theme === 'dark' ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid rgba(0, 0, 0, 0.1)'
          }}
          aria-label="Toggle theme"
          title="Toggle Theme"
        >
          {theme === 'light' ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
        </motion.button>

        {/* User Menu */}
        <div className="relative" ref={userMenuRef}>
          <motion.button
            onClick={() => setShowUserMenu(!showUserMenu)}
            className="h-12 rounded-lg flex items-center space-x-2 px-3 nav-item text-secondary hover:bg-tertiary hover:text-primary"
            style={{
              border: theme === 'dark' ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid rgba(0, 0, 0, 0.1)'
            }}
          >
            <div className="w-8 h-8 rounded-full flex items-center justify-center" style={{ background: 'linear-gradient(135deg, var(--color-3), var(--color-4))' }}>
              <span className="text-sm font-medium" style={{ color: 'var(--on-gradient-3-4)' }}>
                {getUserInitials(user)}
              </span>
            </div>
            <span className="text-sm font-medium hidden md:block text-secondary">
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
