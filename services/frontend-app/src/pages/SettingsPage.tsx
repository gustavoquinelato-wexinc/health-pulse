import axios from 'axios'
import { motion } from 'framer-motion'
import { Activity, Database, RefreshCw, Users } from 'lucide-react'
import { useEffect, useState } from 'react'

import CollapsedSidebar from '../components/CollapsedSidebar'
import Header from '../components/Header'
import { useAuth } from '../contexts/AuthContext'
import useDocumentTitle from '../hooks/useDocumentTitle'

// Utility function to format large numbers with K, M abbreviations
const formatNumber = (num: number): string => {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1).replace(/\.0$/, '') + 'M'
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(1).replace(/\.0$/, '') + 'K'
  }
  return num.toString()
}

interface SystemStats {
  database: {
    database_size: string
    table_count: number
    total_records: number
    monthly_growth_percentage?: number
  }
  users: {
    total_users: number
    active_users: number
    logged_users: number
    admin_users: number
    today_active: number
    week_active: number
    month_active: number
    inactive_30_days: number
  }
  performance: {
    connection_pool_utilization: number
    active_connections: number
    total_connections: number
    avg_response_time_ms?: number
    database_health: string
  }
  tables: Record<string, number>
  table_categories?: Record<string, Record<string, number>>
}

export default function SettingsPage() {
  const { user } = useAuth()
  const [systemStats, setSystemStats] = useState<SystemStats | null>(null)
  const [statsLoading, setStatsLoading] = useState(false)
  const [statsError, setStatsError] = useState<string | null>(null)
  const [showAllTables, setShowAllTables] = useState(true)

  // Set document title
  useDocumentTitle('System Overview')

  // Group tables by category for better organization
  const getTablesByCategory = (tables: Record<string, number>, tableCategories?: Record<string, Record<string, number>>) => {
    // If we have categorized data from the API, use it
    if (tableCategories) {
      return tableCategories
    }

    // Otherwise, use the fallback categorization
    const categories = {
      'Core Data': ['users', 'user_sessions', 'user_permissions', 'clients', 'integrations'],
      'Issues & Workflow': ['projects', 'issues', 'issue_changelogs', 'issuetypes', 'statuses', 'status_mappings', 'workflows', 'issuetype_mappings', 'issuetype_hierarchies', 'projects_issuetypes', 'projects_statuses'],
      'Development Data': ['repositories', 'pull_requests', 'pull_request_commits', 'pull_request_reviews', 'pull_request_comments'],
      'Linking & Mapping': ['jira_pull_request_links'],
      'System': ['job_schedules', 'system_settings', 'migration_history']
    }

    const result: Record<string, Record<string, number>> = {}
    const categorizedTables = new Set<string>()

    // First, categorize known tables
    Object.entries(categories).forEach(([category, tableNames]) => {
      result[category] = {}
      tableNames.forEach(tableName => {
        if (tables[tableName] !== undefined) {
          result[category][tableName] = tables[tableName]
          categorizedTables.add(tableName)
        }
      })
    })

    // Then, add any remaining tables to an "Other" category
    const remainingTables = Object.entries(tables).filter(([tableName]) => !categorizedTables.has(tableName))
    if (remainingTables.length > 0) {
      result['Other'] = {}
      remainingTables.forEach(([tableName, count]) => {
        result['Other'][tableName] = count
      })
    }

    return result
  }

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
              <div className="flex items-center justify-between">
                <div>
                  <h1 className="text-3xl font-bold text-primary">
                    System Overview
                  </h1>
                  <p className="text-secondary">
                    Platform health monitoring and administrative insights
                  </p>
                </div>
                <button
                  onClick={loadSystemStats}
                  disabled={statsLoading}
                  className="btn-neutral-tertiary flex items-center space-x-2"
                >
                  <RefreshCw className={`w-4 h-4 text-white ${statsLoading ? 'animate-spin' : ''}`} />
                  <span>Refresh</span>
                </button>
              </div>
            </div>

            {/* Users Overview Section */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="card p-8"
            >
              <div className="flex items-center space-x-3 mb-6">
                <div className="w-10 h-10 bg-color-2 rounded-lg flex items-center justify-center">
                  <Users className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-primary">Users Overview</h2>
                  <p className="text-sm text-secondary">Platform engagement and user activity metrics</p>
                </div>
              </div>

              <div className="grid grid-cols-7 gap-3">
                {/* Online - Color #2 */}
                <div className="bg-tertiary rounded-lg p-4 text-center border-l-4 border-color-2 flex flex-col justify-between h-24">
                  <div className="text-3xl font-bold text-color-2 mb-2">
                    {statsLoading ? (
                      <div className="h-10 w-10 bg-primary rounded animate-pulse mx-auto"></div>
                    ) : (
                      formatNumber(systemStats?.users.logged_users || 0)
                    )}
                  </div>
                  <div className="text-xs text-secondary h-8 flex items-center justify-center">Online</div>
                </div>

                {/* Today - Color #3 */}
                <div className="bg-tertiary rounded-lg p-4 text-center border-l-4 border-color-3 flex flex-col justify-between h-24">
                  <div className="text-3xl font-bold text-color-3 mb-2">
                    {statsLoading ? (
                      <div className="h-10 w-10 bg-primary rounded animate-pulse mx-auto"></div>
                    ) : (
                      formatNumber(systemStats?.users.today_active || 0)
                    )}
                  </div>
                  <div className="text-xs text-secondary h-8 flex items-center justify-center">Today</div>
                </div>

                {/* Week - Color #3 */}
                <div className="bg-tertiary rounded-lg p-4 text-center border-l-4 border-color-3 flex flex-col justify-between h-24">
                  <div className="text-3xl font-bold text-color-3 mb-2">
                    {statsLoading ? (
                      <div className="h-10 w-10 bg-primary rounded animate-pulse mx-auto"></div>
                    ) : (
                      formatNumber(systemStats?.users.week_active || 0)
                    )}
                  </div>
                  <div className="text-xs text-secondary h-8 flex items-center justify-center">Week</div>
                </div>

                {/* Month - Color #3 */}
                <div className="bg-tertiary rounded-lg p-4 text-center border-l-4 border-color-3 flex flex-col justify-between h-24">
                  <div className="text-3xl font-bold text-color-3 mb-2">
                    {statsLoading ? (
                      <div className="h-10 w-10 bg-primary rounded animate-pulse mx-auto"></div>
                    ) : (
                      formatNumber(systemStats?.users.month_active || 0)
                    )}
                  </div>
                  <div className="text-xs text-secondary h-8 flex items-center justify-center">Month</div>
                </div>

                {/* Active - Color #4 */}
                <div className="bg-tertiary rounded-lg p-4 text-center border-l-4 border-color-4 flex flex-col justify-between h-24">
                  <div className="text-3xl font-bold text-color-4 mb-2">
                    {statsLoading ? (
                      <div className="h-10 w-10 bg-primary rounded animate-pulse mx-auto"></div>
                    ) : (
                      formatNumber(systemStats?.users.active_users || 0)
                    )}
                  </div>
                  <div className="text-xs text-secondary h-8 flex items-center justify-center">Active</div>
                </div>

                {/* Not active > 30 days - Color #4 */}
                <div className="bg-tertiary rounded-lg p-4 text-center border-l-4 border-color-4 flex flex-col justify-between h-24">
                  <div className="text-3xl font-bold text-color-4 mb-2">
                    {statsLoading ? (
                      <div className="h-10 w-10 bg-primary rounded animate-pulse mx-auto"></div>
                    ) : (
                      formatNumber(systemStats?.users.inactive_30_days || 0)
                    )}
                  </div>
                  <div className="text-xs text-secondary h-8 flex items-center justify-center">Not active &gt; 30 days</div>
                </div>

                {/* Total - Color #5 */}
                <div className="bg-tertiary rounded-lg p-4 text-center border-l-4 border-color-5 flex flex-col justify-between h-24">
                  <div className="text-3xl font-bold text-color-5 mb-2">
                    {statsLoading ? (
                      <div className="h-10 w-10 bg-primary rounded animate-pulse mx-auto"></div>
                    ) : (
                      formatNumber(systemStats?.users.total_users || 0)
                    )}
                  </div>
                  <div className="text-xs text-secondary h-8 flex items-center justify-center">Total</div>
                </div>
              </div>
            </motion.div>

            {/* Database Overview Section */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
              className="card p-8"
            >
              <div className="flex items-center space-x-3 mb-6">
                <div className="w-10 h-10 bg-color-1 rounded-lg flex items-center justify-center">
                  <Database className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-primary">Database Overview</h2>
                  <p className="text-sm text-secondary">Infrastructure metrics and performance indicators</p>
                </div>
              </div>

              {/* Colorful Database Cards */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-6"
              >
                <div className="bg-gradient-to-br from-color-1 to-color-2 rounded-xl p-4" style={{ color: 'var(--on-gradient-1-2)' }}>
                  <div className="flex items-center justify-between mb-3">
                    <div className="w-8 h-8 bg-white bg-opacity-20 rounded-lg flex items-center justify-center">
                      <Database className="w-4 h-4" />
                    </div>
                    <span className="text-xs bg-white bg-opacity-20 px-2 py-1 rounded">STORAGE</span>
                  </div>
                  <div className="text-2xl font-bold mb-1">
                    {statsLoading ? (
                      <div className="h-6 w-16 bg-white bg-opacity-20 rounded animate-pulse"></div>
                    ) : (
                      systemStats?.database.database_size || 'N/A'
                    )}
                  </div>
                  <div className="text-sm opacity-90">Database Size</div>
                </div>

                <div className="bg-gradient-to-br from-color-2 to-color-3 rounded-xl p-4" style={{ color: 'var(--on-gradient-2-3)' }}>
                  <div className="flex items-center justify-between mb-3">
                    <div className="w-8 h-8 bg-white bg-opacity-20 rounded-lg flex items-center justify-center">
                      <span className="text-sm font-bold">#</span>
                    </div>
                    <span className="text-xs bg-white bg-opacity-20 px-2 py-1 rounded">SCHEMA</span>
                  </div>
                  <div className="text-2xl font-bold mb-1">
                    {statsLoading ? (
                      <div className="h-6 w-12 bg-white bg-opacity-20 rounded animate-pulse"></div>
                    ) : (
                      systemStats?.database.table_count || 0
                    )}
                  </div>
                  <div className="text-sm opacity-90">Tables</div>
                </div>

                <div className="bg-gradient-to-br from-color-3 to-color-4 rounded-xl p-4" style={{ color: 'var(--on-gradient-3-4)' }}>
                  <div className="flex items-center justify-between mb-3">
                    <div className="w-8 h-8 bg-white bg-opacity-20 rounded-lg flex items-center justify-center">
                      <span className="text-sm font-bold">∑</span>
                    </div>
                    <span className="text-xs bg-white bg-opacity-20 px-2 py-1 rounded">RECORDS</span>
                  </div>
                  <div className="text-2xl font-bold mb-1">
                    {statsLoading ? (
                      <div className="h-6 w-16 bg-white bg-opacity-20 rounded animate-pulse"></div>
                    ) : (
                      systemStats?.database.total_records ?
                        (systemStats.database.total_records / 1000000).toFixed(1) + 'M' : '0'
                    )}
                  </div>
                  <div className="text-sm opacity-90">Data Records</div>
                </div>

                <div className="bg-gradient-to-br from-color-4 to-color-5 rounded-xl p-4" style={{ color: 'var(--on-gradient-4-5)' }}>
                  <div className="flex items-center justify-between mb-3">
                    <div className="w-8 h-8 bg-white bg-opacity-20 rounded-lg flex items-center justify-center">
                      <Activity className="w-4 h-4" />
                    </div>
                    <span className="text-xs bg-white bg-opacity-20 px-2 py-1 rounded">GROWTH</span>
                  </div>
                  <div className="text-2xl font-bold mb-1">
                    {statsLoading ? (
                      <div className="h-6 w-16 bg-white bg-opacity-20 rounded animate-pulse"></div>
                    ) : (
                      systemStats?.database.monthly_growth_percentage !== null && systemStats?.database.monthly_growth_percentage !== undefined ? (
                        <>
                          <span className="text-xl">{systemStats.database.monthly_growth_percentage >= 0 ? '+' : ''}</span>
                          {systemStats.database.monthly_growth_percentage.toFixed(1)}%
                        </>
                      ) : (
                        'N/A'
                      )
                    )}
                  </div>
                  <div className="text-sm opacity-90">Monthly Growth</div>
                  <div className="text-xs opacity-75 mt-1">Data records created</div>
                </div>
              </div>
            </motion.div>

            {/* Database Schema Section - Collapsible */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="card p-8"
            >
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 bg-color-1 rounded-lg flex items-center justify-center">
                    <Database className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <h2 className="text-xl font-semibold text-primary">Database Schema</h2>
                    <p className="text-sm text-secondary">Complete table structure and record counts</p>
                  </div>
                </div>
                <button
                  onClick={() => setShowAllTables(!showAllTables)}
                  className="btn-secondary flex items-center space-x-2"
                >
                  <Database className="w-4 h-4" />
                  <span>{showAllTables ? 'Hide Tables' : 'View All Tables'}</span>
                  <span className="text-color-1">{showAllTables ? '▼' : '▶'}</span>
                </button>
              </div>

              {statsError && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <div className="w-4 h-4 bg-red-500 rounded-full"></div>
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

              {/* Database Schema Details */}
              {showAllTables && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.3 }}
                  className="border-t border-tertiary pt-8"
                >
                  <h3 className="text-lg font-semibold text-primary mb-6">Database Schema Details</h3>

                  {statsLoading ? (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="bg-tertiary rounded-lg p-4 animate-pulse">
                        <div className="h-4 bg-primary rounded mb-2"></div>
                        <div className="h-3 bg-primary rounded"></div>
                      </div>
                      <div className="bg-tertiary rounded-lg p-4 animate-pulse">
                        <div className="h-4 bg-primary rounded mb-2"></div>
                        <div className="h-3 bg-primary rounded"></div>
                      </div>
                      <div className="bg-tertiary rounded-lg p-4 animate-pulse">
                        <div className="h-4 bg-primary rounded mb-2"></div>
                        <div className="h-3 bg-primary rounded"></div>
                      </div>
                    </div>
                  ) : systemStats ? (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                      {Object.entries(getTablesByCategory(systemStats.tables, systemStats.table_categories)).map(([category, tables]) => (
                        <div key={category} className="bg-tertiary rounded-lg p-6">
                          <div className="flex items-center space-x-2 mb-4">
                            <div className="w-3 h-3 bg-color-1 rounded-full"></div>
                            <h4 className="font-semibold text-primary text-sm uppercase tracking-wide">{category}</h4>
                          </div>
                          <div className="space-y-3">
                            {Object.entries(tables).map(([table, count]) => (
                              <div key={table} className="flex justify-between items-center py-2 border-b border-primary last:border-b-0">
                                <span className="text-secondary text-sm capitalize font-medium">
                                  {table.replace(/_/g, ' ')}
                                </span>
                                <div className="flex items-center space-x-2">
                                  <span className="text-primary font-bold text-sm">
                                    {count.toLocaleString()}
                                  </span>
                                  <div className={`w-2 h-2 rounded-full ${count > 1000 ? 'bg-color-3' :
                                    count > 0 ? 'bg-color-4' : 'bg-gray-400'
                                    }`}></div>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="bg-tertiary rounded-lg p-4">
                        <div className="h-4 bg-primary rounded mb-2"></div>
                        <div className="h-3 bg-primary rounded"></div>
                      </div>
                      <div className="h-4 bg-tertiary rounded animate-pulse"></div>
                    </div>
                  )}
                </motion.div>
              )}
            </motion.div>
          </motion.div>
        </main>
      </div>
    </div>
  )
}
