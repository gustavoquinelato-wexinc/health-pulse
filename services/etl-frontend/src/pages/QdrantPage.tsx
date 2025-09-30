import React, { useState, useEffect } from 'react'
import { Loader2, Database, Eye, Play, Trash2, Zap, Download } from 'lucide-react'
import Header from '../components/Header'
import CollapsedSidebar from '../components/CollapsedSidebar'
import IntegrationLogo from '../components/IntegrationLogo'
import { qdrantApi } from '../services/etlApiService'

interface EntityData {
  name: string
  database_count: number
  qdrant_count: number
  completion: number
}

interface EntityGroup {
  title: string
  logo_filename: string
  entities: EntityData[]
}

interface DashboardData {
  total_database: number
  total_vectorized: number
  overall_completion: number
  integration_groups: EntityGroup[]
  queue_pending: number
  queue_failed: number
}

const QdrantPage: React.FC = () => {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null)

  useEffect(() => {
    const fetchQdrantData = async () => {
      try {
        setLoading(true)
        const response = await qdrantApi.getDashboard()
        setDashboardData(response.data)
        setError(null)
      } catch (err) {
        console.error('Error fetching Qdrant data:', err)
        setError('Failed to load Qdrant database information')
      } finally {
        setLoading(false)
      }
    }

    fetchQdrantData()
  }, [])

  const getEntityIcon = (entityName: string) => {
    const iconMap: Record<string, string> = {
      'Work Items': 'file-text',
      'Changelogs': 'git-commit',
      'Projects': 'folder',
      'Statuses': 'tag',
      'Work Item Types': 'layers',
      'WIT Hierarchies': 'git-branch',
      'WIT Mappings': 'link',
      'WIT PR Links': 'git-pull-request',
      'Status Mappings': 'shuffle',
      'Workflows': 'workflow',
      'Pull Requests': 'git-pull-request',
      'PR Comments': 'message-square',
      'PR Reviews': 'eye',
      'PR Commits': 'git-commit',
      'Repositories': 'database',
    }
    return iconMap[entityName] || 'circle'
  }

  // Use real data from API or defaults
  const totals = dashboardData ? {
    totalDatabase: dashboardData.total_database,
    totalVectorized: dashboardData.total_vectorized,
    overallCompletion: dashboardData.overall_completion
  } : { totalDatabase: 0, totalVectorized: 0, overallCompletion: 0 }

  const entityGroups = dashboardData?.integration_groups || []
  const queuePending = dashboardData?.queue_pending || 0
  const queueFailed = dashboardData?.queue_failed || 0

  return (
    <div className="min-h-screen">
      <Header />
      <div className="flex">
        <CollapsedSidebar />
        <main className="flex-1 ml-16 py-8">
          <div className="ml-20 mr-12">
            {/* Page Header */}
            <div className="mb-8">
              <h1 className="text-3xl font-bold text-primary">
                Qdrant Database
              </h1>
              <p className="text-lg text-secondary">
                Vector database collections and vectorization status
              </p>
            </div>

            {/* Content */}
            {loading ? (
              <div className="bg-secondary rounded-lg shadow-sm p-6">
                <div className="text-center py-12">
                  <Loader2 className="h-12 w-12 animate-spin mx-auto mb-4 text-primary" />
                  <h2 className="text-2xl font-semibold text-primary mb-2">
                    Loading...
                  </h2>
                  <p className="text-secondary">
                    Fetching Qdrant database information
                  </p>
                </div>
              </div>
            ) : error ? (
              <div className="bg-secondary rounded-lg shadow-sm p-6">
                <div className="text-center py-12">
                  <div className="text-6xl mb-4">❌</div>
                  <h2 className="text-2xl font-semibold text-primary mb-2">
                    Error
                  </h2>
                  <p className="text-secondary mb-6">
                    {error}
                  </p>
                  <button
                    onClick={() => window.location.reload()}
                    className="px-4 py-2 bg-accent text-on-accent rounded-lg hover:bg-accent/90 transition-colors"
                  >
                    Retry
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-6">
                {/* Summary Cards */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  {/* Total Records Card */}
                  <div 
                    className="rounded-xl p-6 space-y-4 backdrop-blur-sm hover:shadow-md transition-all duration-300"
                    style={{ 
                      background: 'linear-gradient(135deg, var(--color-1) 0%, var(--color-2) 100%)',
                      color: 'var(--on-gradient-1-2)'
                    }}
                  >
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-medium opacity-90">Total Records</h3>
                      <div className="w-3 h-3 bg-white bg-opacity-30 rounded-full"></div>
                    </div>
                    <div className="space-y-2">
                      <div className="text-2xl font-bold">{totals.totalDatabase.toLocaleString()}</div>
                      <div className="text-xs opacity-80">In Database</div>
                    </div>
                  </div>

                  {/* Vectorized Card */}
                  <div 
                    className="rounded-xl p-6 space-y-4 backdrop-blur-sm hover:shadow-md transition-all duration-300"
                    style={{ 
                      background: 'linear-gradient(135deg, var(--color-2) 0%, var(--color-3) 100%)',
                      color: 'var(--on-gradient-2-3)'
                    }}
                  >
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-medium opacity-90">Vectorized</h3>
                      <div className="w-3 h-3 bg-white bg-opacity-30 rounded-full"></div>
                    </div>
                    <div className="space-y-2">
                      <div className="text-2xl font-bold">{totals.totalVectorized.toLocaleString()}</div>
                      <div className="text-xs opacity-80">In Qdrant</div>
                    </div>
                  </div>

                  {/* Completion Card */}
                  <div 
                    className="rounded-xl p-6 space-y-4 backdrop-blur-sm hover:shadow-md transition-all duration-300"
                    style={{ 
                      background: 'linear-gradient(135deg, var(--color-3) 0%, var(--color-4) 100%)',
                      color: 'var(--text-primary)'
                    }}
                  >
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-medium opacity-90">Completion</h3>
                      <div className="w-3 h-3 bg-white bg-opacity-30 rounded-full"></div>
                    </div>
                    <div className="space-y-2">
                      <div className="text-2xl font-bold">{totals.overallCompletion}%</div>
                      <div className="text-xs opacity-80">Overall Progress</div>
                    </div>
                  </div>
                </div>

                {/* Entity Breakdown by Integration */}
                <div className="space-y-6">
                  {entityGroups.map((group, groupIndex) => (
                    <div
                      key={groupIndex}
                      className="rounded-lg bg-secondary shadow-md border border-transparent hover:border-blue-200 transition-all duration-300 overflow-hidden"
                    >
                      {/* Group Header */}
                      <div className="px-6 py-4 bg-gradient-to-r from-blue-50 to-indigo-50 border-b border-blue-200 flex items-center space-x-3">
                        <div className="w-8 h-8 rounded-lg bg-white border-2 border-blue-200 flex items-center justify-center overflow-hidden">
                          <IntegrationLogo
                            logoFilename={group.logo_filename}
                            integrationName={group.title}
                            className="h-6 w-6 object-contain"
                          />
                        </div>
                        <div>
                          <h3 className="text-sm font-bold text-gray-700 uppercase tracking-wide">{group.title}</h3>
                          <p className="text-xs text-gray-500">{group.entities.length} entities</p>
                        </div>
                      </div>

                      {/* Entity Tiles */}
                      <div className="p-6">
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
                          {group.entities.map((entity, entityIndex) => {
                            const statusClass = entity.completion >= 100 ? 'complete' : entity.completion > 0 ? 'partial' : 'empty'
                            const completionClass = entity.completion >= 100 ? 'bg-green-100 text-green-700' : entity.completion > 0 ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-500'
                            const dotClass = entity.completion >= 100 ? 'bg-green-500' : entity.completion > 0 ? 'bg-yellow-500' : 'bg-gray-300'

                            return (
                              <div
                                key={entityIndex}
                                className="bg-primary border border-border rounded-lg p-4 hover:shadow-md transition-all duration-200 flex flex-col justify-between"
                              >
                                <div className="flex items-start justify-between mb-3">
                                  <div className="flex items-center space-x-2">
                                    <Database className="w-4 h-4 text-secondary" />
                                    <span className="text-sm font-semibold text-primary">{entity.name}</span>
                                  </div>
                                  <div className={`w-2 h-2 rounded-full ${dotClass}`}></div>
                                </div>
                                <div className="space-y-2">
                                  <div className="text-xs text-secondary">
                                    {entity.qdrant_count}/{entity.database_count} vectorized
                                  </div>
                                  <div className="flex items-center justify-between">
                                    <span className={`text-xs px-2 py-1 rounded font-medium ${completionClass}`}>
                                      {entity.completion}%
                                    </span>
                                    <button
                                      className="p-1 hover:bg-tertiary rounded transition-colors"
                                      title="View Details"
                                    >
                                      <Eye className="w-3 h-3 text-secondary" />
                                    </button>
                                  </div>
                                </div>
                              </div>
                            )
                          })}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Quick Actions */}
                <div className="rounded-lg bg-secondary shadow-md p-6">
                  <h4 className="font-semibold mb-4 text-primary">Quick Actions</h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <button
                      className="p-4 rounded-lg border text-left hover:opacity-80 transition-colors text-white"
                      style={{ backgroundColor: 'var(--color-1)', borderColor: 'var(--color-1)' }}
                    >
                      <div className="flex items-center space-x-3">
                        <Play className="w-5 h-5" />
                        <div>
                          <div className="font-medium">Start Vectorization</div>
                          <div className="text-sm opacity-80">{queuePending} pending items to process</div>
                        </div>
                      </div>
                    </button>
                    <button
                      className="p-4 rounded-lg border text-left hover:opacity-80 transition-colors text-white"
                      style={{ backgroundColor: 'var(--status-warning)', borderColor: 'var(--status-warning)' }}
                    >
                      <div className="flex items-center space-x-3">
                        <Trash2 className="w-5 h-5" />
                        <div>
                          <div className="font-medium">Cleanup Failed Items</div>
                          <div className="text-sm opacity-80">{queueFailed} failed items to clean</div>
                        </div>
                      </div>
                    </button>
                    <button
                      className="p-4 rounded-lg border text-left hover:opacity-80 transition-colors text-white"
                      style={{ backgroundColor: 'var(--color-3)', borderColor: 'var(--color-3)' }}
                    >
                      <div className="flex items-center space-x-3">
                        <Zap className="w-5 h-5" />
                        <div>
                          <div className="font-medium">Optimize Collections</div>
                          <div className="text-sm opacity-80">Improve query performance</div>
                        </div>
                      </div>
                    </button>
                    <button
                      className="p-4 rounded-lg border text-left hover:opacity-80 transition-colors text-white"
                      style={{ backgroundColor: 'var(--color-4)', borderColor: 'var(--color-4)' }}
                    >
                      <div className="flex items-center space-x-3">
                        <Download className="w-5 h-5" />
                        <div>
                          <div className="font-medium">Export Data</div>
                          <div className="text-sm opacity-80">Download vector collections</div>
                        </div>
                      </div>
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  )
}

export default QdrantPage

