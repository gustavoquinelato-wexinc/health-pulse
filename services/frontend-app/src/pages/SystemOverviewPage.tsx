import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import CollapsedSidebar from '../components/CollapsedSidebar'
import Header from '../components/Header'
import useDocumentTitle from '../hooks/useDocumentTitle'
import axios from 'axios'

interface DatabaseStats {
  database_size: string
  table_count: number
  total_records: number
}

interface UserStats {
  total_users: number
  active_users: number
  logged_users: number
  admin_users: number
}

interface TableStats {
  [tableName: string]: number
}

interface SystemStats {
  database: DatabaseStats
  users: UserStats
  tables: TableStats
}

export default function SystemOverviewPage() {
  const navigate = useNavigate()
  const [stats, setStats] = useState<SystemStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showTableDetails, setShowTableDetails] = useState(false)

  // Set document title
  useDocumentTitle('System Overview - Settings')

  useEffect(() => {
    loadSystemStats()
  }, [])

  const loadSystemStats = async () => {
    try {
      setLoading(true)
      setError(null)
      
      const response = await axios.get('/api/v1/admin/system/stats')
      setStats(response.data)
    } catch (error: any) {
      console.error('Error loading system stats:', error)
      setError(error.response?.data?.detail || 'Failed to load system statistics')
    } finally {
      setLoading(false)
    }
  }

  const refreshStats = () => {
    loadSystemStats()
  }

  // Group tables by category for better organization
  const getTablesByCategory = (tables: TableStats) => {
    const categories = {
      'Core Data': ['users', 'user_sessions', 'user_permissions', 'clients', 'integrations'],
      'Issues & Workflow': ['projects', 'issues', 'issue_changelogs', 'issuetypes', 'statuses', 'status_mappings', 'workflows', 'issuetype_mappings', 'issuetype_hierarchies', 'projects_issuetypes', 'projects_statuses'],
      'Development Data': ['repositories', 'pull_requests', 'pull_request_commits', 'pull_request_reviews', 'pull_request_comments'],
      'Linking & Mapping': ['jira_pull_request_links'],
      'System': ['job_schedules', 'system_settings', 'migration_history']
    }

    const result: { [category: string]: { [table: string]: number } } = {}
    
    Object.entries(categories).forEach(([category, tableNames]) => {
      result[category] = {}
      tableNames.forEach(tableName => {
        if (tables[tableName] !== undefined) {
          result[category][tableName] = tables[tableName]
        }
      })
    })

    return result
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
            {/* Header */}
            <div className="flex items-center justify-between">
              <div className="space-y-2">
                <div className="flex items-center space-x-3">
                  <button
                    onClick={() => navigate('/settings')}
                    className="text-secondary hover:text-primary transition-colors"
                  >
                    ← Back to Settings
                  </button>
                </div>
                <h1 className="text-3xl font-bold text-primary">
                  System Overview
                </h1>
                <p className="text-secondary">
                  Database statistics and system management
                </p>
              </div>
              <button
                onClick={refreshStats}
                disabled={loading}
                className="btn-secondary flex items-center space-x-2"
              >
                <span className={`${loading ? 'animate-spin' : ''}`}>🔄</span>
                <span>Refresh</span>
              </button>
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <div className="flex items-center space-x-2">
                  <span className="text-red-500">⚠️</span>
                  <span className="text-red-700">{error}</span>
                </div>
              </div>
            )}

            {loading ? (
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                <span className="ml-3 text-secondary">Loading system statistics...</span>
              </div>
            ) : stats ? (
              <>
                {/* Database Statistics */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 }}
                    className="card p-6 text-center"
                  >
                    <div className="text-4xl mb-3">💾</div>
                    <h3 className="text-2xl font-bold text-primary mb-1">
                      {stats.database.database_size}
                    </h3>
                    <p className="text-secondary">Database Size</p>
                  </motion.div>

                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                    className="card p-6 text-center"
                  >
                    <div className="text-4xl mb-3">📊</div>
                    <h3 className="text-2xl font-bold text-primary mb-1">
                      {stats.database.table_count.toLocaleString()}
                    </h3>
                    <p className="text-secondary">Active Tables</p>
                  </motion.div>

                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3 }}
                    className="card p-6 text-center"
                  >
                    <div className="text-4xl mb-3">🗃️</div>
                    <h3 className="text-2xl font-bold text-primary mb-1">
                      {stats.database.total_records.toLocaleString()}
                    </h3>
                    <p className="text-secondary">Total DB Records</p>
                  </motion.div>
                </div>

                {/* User Statistics */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.4 }}
                    className="card p-6 text-center"
                  >
                    <div className="text-4xl mb-3">👥</div>
                    <h3 className="text-2xl font-bold text-primary mb-1">
                      {stats.users.total_users}
                    </h3>
                    <p className="text-secondary">Total Users</p>
                  </motion.div>

                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.5 }}
                    className="card p-6 text-center"
                  >
                    <div className="text-4xl mb-3">✅</div>
                    <h3 className="text-2xl font-bold text-primary mb-1">
                      {stats.users.active_users}
                    </h3>
                    <p className="text-secondary">Active Users</p>
                  </motion.div>

                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.6 }}
                    className="card p-6 text-center"
                  >
                    <div className="text-4xl mb-3">🔐</div>
                    <h3 className="text-2xl font-bold text-primary mb-1">
                      {stats.users.logged_users}
                    </h3>
                    <p className="text-secondary">Logged Users</p>
                  </motion.div>

                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.7 }}
                    className="card p-6 text-center"
                  >
                    <div className="text-4xl mb-3">👑</div>
                    <h3 className="text-2xl font-bold text-primary mb-1">
                      {stats.users.admin_users}
                    </h3>
                    <p className="text-secondary">Admin Users</p>
                  </motion.div>
                </div>

                {/* Database Table Details */}
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.8 }}
                  className="card"
                >
                  <div className="p-6 border-b border-tertiary">
                    <div className="flex items-center justify-between">
                      <h3 className="text-lg font-semibold text-primary flex items-center space-x-2">
                        <span>📋</span>
                        <span>Database Table Statistics</span>
                      </h3>
                      <button
                        onClick={() => setShowTableDetails(!showTableDetails)}
                        className="btn-secondary text-sm"
                      >
                        {showTableDetails ? 'Hide Details' : 'Show Details'}
                      </button>
                    </div>
                  </div>
                  
                  {showTableDetails && (
                    <div className="p-6">
                      {Object.entries(getTablesByCategory(stats.tables)).map(([category, tables]) => (
                        <div key={category} className="mb-6 last:mb-0">
                          <h4 className="text-md font-medium text-primary mb-3">{category}</h4>
                          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {Object.entries(tables).map(([tableName, count]) => (
                              <div key={tableName} className="bg-tertiary rounded-lg p-3">
                                <div className="flex justify-between items-center">
                                  <span className="text-sm text-secondary font-medium">{tableName}</span>
                                  <span className="text-sm font-bold text-primary">{count.toLocaleString()}</span>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </motion.div>
              </>
            ) : null}
          </motion.div>
        </main>
      </div>
    </div>
  )
}
