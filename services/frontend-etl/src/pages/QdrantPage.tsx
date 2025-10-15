import React, { useState, useEffect } from 'react'
import { Loader2, Database, RefreshCw } from 'lucide-react'
import Header from '../components/Header'
import CollapsedSidebar from '../components/CollapsedSidebar'
import IntegrationLogo from '../components/IntegrationLogo'
import ToastContainer from '../components/ToastContainer'
import { qdrantApi } from '../services/etlApiService'
import { useToast } from '../hooks/useToast'

interface EntityData {
  name: string
  database_count: number
  qdrant_count: number
  completion: number
  qdrant_collection_exists: boolean
  qdrant_actual_vectors: number
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
  const [creatingCollections, setCreatingCollections] = useState(false)
  const { toasts, removeToast, showSuccess, showError } = useToast()

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

  useEffect(() => {
    fetchQdrantData()
  }, [])

  const handleCreateCollections = async () => {
    try {
      setCreatingCollections(true)
      const response = await qdrantApi.createAllCollections()
      const data = response.data

      if (data.success) {
        showSuccess(
          'Collections Created',
          `Successfully created ${data.collections_created} collections. ${data.collections_already_exist} already existed. ${data.collections_failed} failed.`
        )
        // Refresh dashboard data
        await fetchQdrantData()
      } else {
        showError('Creation Failed', 'Failed to create collections')
      }
    } catch (err: any) {
      console.error('Error creating collections:', err)
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to create collections'
      showError('Creation Failed', errorMessage)
    } finally {
      setCreatingCollections(false)
    }
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
          <div className="ml-12 mr-12">
            {/* Page Header */}
            <div className="mb-8 flex justify-between items-start">
              <div>
                <h1 className="text-3xl font-bold text-primary">
                  Qdrant Database
                </h1>
                <p className="text-lg text-secondary">
                  Vector database collections and vectorization status
                </p>
              </div>

              {/* Create Collections Button */}
              {!loading && !error && (
                <button
                  onClick={handleCreateCollections}
                  disabled={creatingCollections}
                  className="px-4 py-2 rounded-lg text-white flex items-center space-x-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  style={{ background: 'var(--gradient-1-2)' }}
                  onMouseEnter={(e) => {
                    if (!creatingCollections) e.currentTarget.style.opacity = '0.9'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.opacity = '1'
                  }}
                  title="Create all necessary Qdrant collections for active tenants (checks if exists first)"
                >
                  <RefreshCw className={`h-4 w-4 ${creatingCollections ? 'animate-spin' : ''}`} />
                  <span>{creatingCollections ? 'Creating Collections...' : 'Create Collections'}</span>
                </button>
              )}
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
                    className="bg-secondary rounded-lg shadow-md border border-gray-400 p-6 transition-all duration-200"
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = 'var(--color-1)'
                      e.currentTarget.style.boxShadow = '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)'
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = '#9ca3af'
                      e.currentTarget.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
                    }}
                  >
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-sm font-medium text-secondary">Total Records</h3>
                      <Database className="w-5 h-5 text-secondary" />
                    </div>
                    <div className="text-3xl font-bold text-primary mb-1">
                      {totals.totalDatabase.toLocaleString()}
                    </div>
                    <div className="text-sm text-secondary">In Database</div>
                  </div>

                  {/* Vectorized Card */}
                  <div
                    className="bg-secondary rounded-lg shadow-md border border-gray-400 p-6 transition-all duration-200"
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = 'var(--color-1)'
                      e.currentTarget.style.boxShadow = '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)'
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = '#9ca3af'
                      e.currentTarget.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
                    }}
                  >
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-sm font-medium text-secondary">Vectorized</h3>
                      <Database className="w-5 h-5 text-secondary" />
                    </div>
                    <div className="text-3xl font-bold text-primary mb-1">
                      {totals.totalVectorized.toLocaleString()}
                    </div>
                    <div className="text-sm text-secondary">In Qdrant</div>
                  </div>

                  {/* Completion Card */}
                  <div
                    className="bg-secondary rounded-lg shadow-md border border-gray-400 p-6 transition-all duration-200"
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = 'var(--color-1)'
                      e.currentTarget.style.boxShadow = '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)'
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = '#9ca3af'
                      e.currentTarget.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
                    }}
                  >
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-sm font-medium text-secondary">Completion</h3>
                      <Database className="w-5 h-5 text-secondary" />
                    </div>
                    <div className="text-3xl font-bold text-primary mb-1">
                      {totals.overallCompletion}%
                    </div>
                    <div className="text-sm text-secondary">Overall Progress</div>
                  </div>
                </div>

                {/* Entity Breakdown by Integration */}
                <div className="space-y-6">
                  {entityGroups.map((group, groupIndex) => (
                    <div
                      key={groupIndex}
                      className="rounded-lg bg-table-container shadow-md overflow-hidden border border-gray-400"
                    >
                      {/* Group Header */}
                      <div className="px-6 py-5 bg-table-header border-b border-border flex items-center justify-between">
                        <div className="flex items-center space-x-3">
                          <div className="w-8 h-8 rounded-lg bg-primary border border-border flex items-center justify-center overflow-hidden">
                            <IntegrationLogo
                              logoFilename={group.logo_filename}
                              integrationName={group.title}
                              className="h-6 w-6 object-contain"
                            />
                          </div>
                          <h3 className="text-lg font-semibold text-white">{group.title}</h3>
                        </div>
                        <div className="text-sm text-white opacity-90">
                          {group.entities.length} {group.entities.length === 1 ? 'table' : 'tables'}
                        </div>
                      </div>

                      {/* Entity Table */}
                      <div className="overflow-x-auto">
                        <table className="w-full">
                          <thead>
                            <tr className="bg-table-column-header">
                              <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-table-column-header">
                                Table
                              </th>
                              <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-table-column-header">
                                Database
                              </th>
                              <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-table-column-header">
                                Qdrant Vectors
                              </th>
                              <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-table-column-header">
                                Collection
                              </th>
                              <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-table-column-header">
                                Completion
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {group.entities.sort((a, b) => a.name.localeCompare(b.name)).map((entity, entityIndex) => (
                              <tr
                                key={entityIndex}
                                className={`${entityIndex % 2 === 0 ? 'bg-table-row-even' : 'bg-table-row-odd'}`}
                              >
                                <td className="px-6 py-5 whitespace-nowrap">
                                  <div className="flex items-center space-x-2">
                                    <Database className="w-4 h-4 text-table-row" />
                                    <span className="text-sm font-semibold text-table-row">{entity.name}</span>
                                  </div>
                                </td>
                                <td className="px-6 py-5 whitespace-nowrap text-sm text-table-row">
                                  {entity.database_count.toLocaleString()}
                                </td>
                                <td className="px-6 py-5 whitespace-nowrap text-sm text-table-row">
                                  {entity.qdrant_count.toLocaleString()}
                                </td>
                                <td className="px-6 py-5 whitespace-nowrap text-sm">
                                  {entity.qdrant_collection_exists ? (
                                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                      ✓ {entity.qdrant_actual_vectors.toLocaleString()} vectors
                                    </span>
                                  ) : (
                                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
                                      Not created
                                    </span>
                                  )}
                                </td>
                                <td className="px-6 py-5 whitespace-nowrap">
                                  <div className="flex items-center space-x-3">
                                    <div className="flex-1 bg-gray-300 dark:bg-gray-600 rounded-full h-2 max-w-[100px]">
                                      <div
                                        className="bg-blue-600 h-2 rounded-full transition-all"
                                        style={{ width: `${entity.completion}%` }}
                                      ></div>
                                    </div>
                                    <span className="text-sm font-semibold text-table-row min-w-[45px]">
                                      {entity.completion}%
                                    </span>
                                  </div>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ))}
                </div>

              </div>
            )}
          </div>
        </main>
      </div>

      {/* Toast Notifications */}
      <ToastContainer toasts={toasts} removeToast={removeToast} />
    </div>
  )
}

export default QdrantPage

