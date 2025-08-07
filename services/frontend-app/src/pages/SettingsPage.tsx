import axios from 'axios'
import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import CollapsedSidebar from '../components/CollapsedSidebar'
import Header from '../components/Header'
import { useAuth } from '../contexts/AuthContext'
import useDocumentTitle from '../hooks/useDocumentTitle'

interface SystemStats {
  database: {
    database_size: string
    table_count: number
    total_records: number
  }
  users: {
    total_users: number
    active_users: number
    logged_users: number
    admin_users: number
  }
  tables: Record<string, number>
}

export default function SettingsPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const [systemStats, setSystemStats] = useState<SystemStats | null>(null)
  const [statsLoading, setStatsLoading] = useState(false)
  const [statsError, setStatsError] = useState<string | null>(null)

  // Set document title
  useDocumentTitle('Admin Settings')

  // Load system stats for admin users
  useEffect(() => {
    if (user?.role === 'admin') {
      loadSystemStats()
    }
  }, [user])

  const loadSystemStats = async () => {
    try {
      setStatsLoading(true)
      setStatsError(null)

      const response = await axios.get('/api/v1/admin/system/stats')
      setSystemStats(response.data)
    } catch (error: any) {
      console.error('Error loading system stats:', error)
      setStatsError(error.response?.data?.detail || 'Failed to load system statistics')
    } finally {
      setStatsLoading(false)
    }
  }
  return (
    <div className="min-h-screen bg-primary">
      <Header />

      <div className="flex">
        <CollapsedSidebar />

        <main className="flex-1 p-6 ml-16">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="space-y-6"
          >
            <div className="space-y-2">
              <h1 className="text-3xl font-bold text-primary">
                Admin Settings
              </h1>
              <p className="text-secondary">
                Configure platform-wide settings and manage organizational preferences
              </p>
            </div>

            {/* System Overview - Admin Only */}
            {user?.role === 'admin' && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="space-y-6"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-indigo-500 rounded-lg flex items-center justify-center">
                      <span className="text-white text-lg">📊</span>
                    </div>
                    <div>
                      <h2 className="text-xl font-semibold text-primary">System Overview</h2>
                      <p className="text-sm text-secondary">Database statistics and platform health</p>
                    </div>
                  </div>
                  <button
                    onClick={loadSystemStats}
                    disabled={statsLoading}
                    className="btn-secondary flex items-center space-x-2"
                  >
                    <span className={`${statsLoading ? 'animate-spin' : ''}`}>🔄</span>
                    <span>Refresh</span>
                  </button>
                </div>

                {statsError && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <span className="text-red-500">⚠️</span>
                        <span className="text-red-700">{statsError}</span>
                      </div>
                      <button
                        onClick={() => setStatsError(null)}
                        className="text-red-500 hover:text-red-700"
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                )}

                {statsLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                    <span className="ml-3 text-secondary">Loading system statistics...</span>
                  </div>
                ) : systemStats ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                    {/* Database Stats */}
                    <div className="card p-6">
                      <div className="flex items-center space-x-3 mb-4">
                        <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center">
                          <span className="text-blue-600 text-sm">💾</span>
                        </div>
                        <h3 className="font-semibold text-primary">Database</h3>
                      </div>
                      <div className="space-y-2">
                        <div className="flex justify-between">
                          <span className="text-secondary text-sm">Size:</span>
                          <span className="text-primary font-medium">{systemStats.database.database_size}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-secondary text-sm">Tables:</span>
                          <span className="text-primary font-medium">{systemStats.database.table_count}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-secondary text-sm">Records:</span>
                          <span className="text-primary font-medium">{systemStats.database.total_records.toLocaleString()}</span>
                        </div>
                      </div>
                    </div>

                    {/* User Stats */}
                    <div className="card p-6">
                      <div className="flex items-center space-x-3 mb-4">
                        <div className="w-8 h-8 bg-green-100 rounded-lg flex items-center justify-center">
                          <span className="text-green-600 text-sm">👥</span>
                        </div>
                        <h3 className="font-semibold text-primary">Users</h3>
                      </div>
                      <div className="space-y-2">
                        <div className="flex justify-between">
                          <span className="text-secondary text-sm">Total:</span>
                          <span className="text-primary font-medium">{systemStats.users.total_users}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-secondary text-sm">Active:</span>
                          <span className="text-primary font-medium">{systemStats.users.active_users}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-secondary text-sm">Online:</span>
                          <span className="text-primary font-medium">{systemStats.users.logged_users}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-secondary text-sm">Admins:</span>
                          <span className="text-primary font-medium">{systemStats.users.admin_users}</span>
                        </div>
                      </div>
                    </div>

                    {/* Top Tables */}
                    <div className="card p-6 md:col-span-2">
                      <div className="flex items-center space-x-3 mb-4">
                        <div className="w-8 h-8 bg-purple-100 rounded-lg flex items-center justify-center">
                          <span className="text-purple-600 text-sm">📋</span>
                        </div>
                        <h3 className="font-semibold text-primary">Table Records</h3>
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        {Object.entries(systemStats.tables)
                          .sort(([, a], [, b]) => b - a)
                          .slice(0, 8)
                          .map(([table, count]) => (
                            <div key={table} className="flex justify-between">
                              <span className="text-secondary text-sm capitalize">{table.replace('_', ' ')}:</span>
                              <span className="text-primary font-medium">{count.toLocaleString()}</span>
                            </div>
                          ))}
                      </div>
                    </div>
                  </div>
                ) : null}
              </motion.div>
            )}

            {/* Settings Overview */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
                className="card p-6 hover:shadow-lg transition-shadow cursor-pointer"
                onClick={() => navigate('/admin/color-scheme')}
              >
                <div className="flex items-center space-x-3 mb-4">
                  <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-violet-500 rounded-lg flex items-center justify-center">
                    <span className="text-white text-lg">🎨</span>
                  </div>
                  <h3 className="text-lg font-semibold text-primary">Color Scheme</h3>
                </div>
                <p className="text-secondary text-sm">
                  Customize your platform's color palette and theme preferences
                </p>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="card p-6 hover:shadow-lg transition-shadow cursor-pointer opacity-50"
              >
                <div className="flex items-center space-x-3 mb-4">
                  <div className="w-10 h-10 bg-gradient-to-br from-orange-500 to-red-500 rounded-lg flex items-center justify-center">
                    <span className="text-white text-lg">🔔</span>
                  </div>
                  <h3 className="text-lg font-semibold text-primary">Notifications</h3>
                </div>
                <p className="text-secondary text-sm">
                  Configure alerts and notification preferences
                </p>
                <span className="text-xs text-muted mt-2 block">Coming Soon</span>
              </motion.div>

              {/* Admin-only sections */}
              {user?.role === 'admin' && (
                <>
                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.4 }}
                    className="card p-6 hover:shadow-lg transition-shadow cursor-pointer"
                    onClick={() => navigate('/admin/user-management')}
                  >
                    <div className="flex items-center space-x-3 mb-4">
                      <div className="w-10 h-10 bg-gradient-to-br from-green-500 to-emerald-500 rounded-lg flex items-center justify-center">
                        <span className="text-white text-lg">👥</span>
                      </div>
                      <h3 className="text-lg font-semibold text-primary">User Management</h3>
                    </div>
                    <p className="text-secondary text-sm">
                      Manage users, roles, permissions, and active sessions
                    </p>
                  </motion.div>

                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.5 }}
                    className="card p-6 hover:shadow-lg transition-shadow cursor-pointer"
                    onClick={() => navigate('/admin/client-management')}
                  >
                    <div className="flex items-center space-x-3 mb-4">
                      <div className="w-10 h-10 bg-gradient-to-br from-cyan-500 to-blue-500 rounded-lg flex items-center justify-center">
                        <span className="text-white text-lg">🏢</span>
                      </div>
                      <h3 className="text-lg font-semibold text-primary">Client Management</h3>
                    </div>
                    <p className="text-secondary text-sm">
                      Manage client configurations, logos, and branding settings
                    </p>
                  </motion.div>
                </>
              )}
            </div>
          </motion.div>
        </main>
      </div>
    </div>
  )
}
