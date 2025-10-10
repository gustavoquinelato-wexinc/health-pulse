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
    <header
      className="px-6 flex items-center justify-between sticky top-0 z-50"
      style={{
        backgroundColor: theme === 'dark' ? '#24292f' : '#f6f8fa',
        borderBottom: theme === 'dark' ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid rgba(0, 0, 0, 0.1)',
        height: '64px'
      }}
    >
      {/* Left Side - Logo and Title */}
      <div className="flex items-center space-x-3">
        {/* Tenant Logo - Smaller, GitHub-style */}
        <div className="h-7 flex items-center justify-center" style={{ width: '100px' }}>
          {tenantLoading ? (
            <div
              className="h-5 w-16 rounded animate-pulse"
              style={{
                backgroundColor: theme === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'
              }}
            ></div>
          ) : getLogoUrl() ? (
            <img
              src={getLogoUrl() || undefined}
              alt={`${currentTenant?.name || 'Tenant'} Logo`}
              className="h-full max-w-full object-contain"
              style={{
                filter: theme === 'dark' ? 'brightness(0) invert(1)' : 'none',
                maxWidth: '100px',
                opacity: 1,
                transition: 'none'
              }}
              onError={(e) => {
                e.currentTarget.style.display = 'none'
              }}
            />
          ) : (
            <span
              className="text-sm font-medium whitespace-nowrap"
              style={{ color: theme === 'dark' ? '#ffffff' : '#24292f' }}
            >
              {currentTenant?.name || 'Tenant'}
            </span>
          )}
        </div>

        {/* Vertical Divisor */}
        <div
          className="h-6 w-px"
          style={{
            backgroundColor: theme === 'dark' ? 'rgba(255, 255, 255, 0.15)' : 'rgba(0, 0, 0, 0.15)'
          }}
        ></div>

        {/* Title - Simple text, no badge */}
        <div
          className="text-sm font-semibold whitespace-nowrap"
          style={{ color: theme === 'dark' ? '#ffffff' : '#24292f' }}
        >
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
          className="p-2 rounded-md transition-colors"
          style={{
            color: theme === 'dark' ? '#ffffff' : '#24292f',
            backgroundColor: 'transparent',
            border: theme === 'dark' ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid rgba(0, 0, 0, 0.1)'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = theme === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.05)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'transparent'
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
          className="p-2 rounded-md transition-colors"
          style={{
            color: theme === 'dark' ? '#ffffff' : '#24292f',
            backgroundColor: 'transparent',
            border: theme === 'dark' ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid rgba(0, 0, 0, 0.1)'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = theme === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.05)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'transparent'
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
            className="rounded-full transition-colors"
            style={{
              backgroundColor: 'transparent',
              border: theme === 'dark' ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid rgba(0, 0, 0, 0.1)',
              padding: '1px'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = theme === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.05)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'transparent'
            }}
            aria-label={displayName}
            title={displayName}
          >
            <div className="w-8 h-8 rounded-full flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #667eea, #764ba2)' }}>
              <span className="text-xs font-medium text-white">
                {getUserInitials(user)}
              </span>
            </div>
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
