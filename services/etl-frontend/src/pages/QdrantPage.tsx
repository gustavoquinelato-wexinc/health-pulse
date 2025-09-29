import React, { useState, useEffect } from 'react'
import Header from '../components/Header'
import CollapsedSidebar from '../components/CollapsedSidebar'
import { qdrantApi } from '../services/etlApiService'

interface QdrantCollection {
  name: string
  vectors_count: number
  indexed_vectors_count: number
  points_count: number
  segments_count: number
  status: string
  optimizer_status: any
  disk_data_size: number
  ram_data_size: number
}

interface QdrantData {
  collections: QdrantCollection[]
  total_collections: number
  total_vectors: number
  total_points: number
}

interface QdrantHealth {
  status: string
  version: string
  uptime_seconds: number
  memory_usage: {
    used_bytes: number
    available_bytes: number
  }
  disk_usage: {
    used_bytes: number
    available_bytes: number
  }
}

const QdrantPage: React.FC = () => {
  const [qdrantData, setQdrantData] = useState<QdrantData | null>(null)
  const [healthData, setHealthData] = useState<QdrantHealth | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchQdrantData = async () => {
      try {
        setLoading(true)
        const [collectionsResponse, healthResponse] = await Promise.all([
          qdrantApi.getCollections(),
          qdrantApi.getHealth()
        ])
        setQdrantData(collectionsResponse.data)
        setHealthData(healthResponse.data)
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

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  const formatUptime = (seconds: number) => {
    const days = Math.floor(seconds / 86400)
    const hours = Math.floor((seconds % 86400) / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    return `${days}d ${hours}h ${minutes}m`
  }

  return (
    <div className="min-h-screen bg-primary">
      <Header />
      <div className="flex">
        <CollapsedSidebar />
        <main className="flex-1 ml-16 p-8">
          <div className="max-w-7xl mx-auto">
            {/* Page Header */}
            <div className="mb-8">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h1 className="text-3xl font-bold text-primary">
                    Qdrant Database
                  </h1>
                  <p className="text-lg text-secondary">
                    Manage vector database collections and operations
                  </p>
                </div>
              </div>
            </div>

            {/* Vectorization Status Card */}
            <div className="mb-6 p-4 rounded-lg bg-secondary border border-tertiary/20">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-accent">
                      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
                      <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
                      <line x1="12" y1="22.08" x2="12" y2="12"></line>
                    </svg>
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-primary">Vectorization Status</h3>
                    <p className="text-sm text-secondary">Real-time processing status</p>
                  </div>
                </div>

                <div className="flex items-center space-x-2">
                  <button className="px-3 py-1.5 text-xs rounded-md border border-tertiary/20 text-secondary bg-primary">
                    Details
                  </button>
                  <button className="px-3 py-1.5 text-xs rounded-md text-white bg-blue-500">
                    Execute
                  </button>
                </div>
              </div>
            </div>

            {/* Content */}
            {loading ? (
              <div className="bg-secondary rounded-lg shadow-sm p-6">
                <div className="text-center py-12">
                  <div className="text-6xl mb-4">⏳</div>
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
              <>
                {/* Filters Section */}
                <div className="mb-6 p-4 rounded-lg bg-secondary border border-tertiary/20">
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    {/* Collection Name Filter */}
                    <div>
                      <label className="block text-sm font-medium mb-2 text-primary">Collection Name</label>
                      <input
                        type="text"
                        placeholder="Filter by collection name..."
                        className="w-full px-3 py-2 border border-tertiary/20 rounded-lg bg-primary text-primary"
                      />
                    </div>

                    {/* Status Filter */}
                    <div>
                      <label className="block text-sm font-medium mb-2 text-primary">Status</label>
                      <select className="w-full px-3 py-2 border border-tertiary/20 rounded-lg bg-primary text-primary">
                        <option value="">All Statuses</option>
                        <option value="active">Active</option>
                        <option value="inactive">Inactive</option>
                      </select>
                    </div>

                    {/* Vector Count Filter */}
                    <div>
                      <label className="block text-sm font-medium mb-2 text-primary">Vector Count</label>
                      <input
                        type="text"
                        placeholder="Filter by vector count..."
                        className="w-full px-3 py-2 border border-tertiary/20 rounded-lg bg-primary text-primary"
                      />
                    </div>

                    {/* Size Filter */}
                    <div>
                      <label className="block text-sm font-medium mb-2 text-primary">Size</label>
                      <input
                        type="text"
                        placeholder="Filter by size..."
                        className="w-full px-3 py-2 border border-tertiary/20 rounded-lg bg-primary text-primary"
                      />
                    </div>
                  </div>
                </div>

                {/* Database Health Status */}
                {healthData && (
                  <div className="rounded-lg overflow-hidden bg-secondary border border-tertiary/20 mb-6">
                    <div className="px-6 py-4 border-b border-tertiary/20 bg-tertiary/10">
                      <h2 className="text-lg font-semibold text-primary">Database Health</h2>
                    </div>
                    <div className="p-6">
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                        <div className="bg-primary border border-tertiary/20 rounded-lg p-4">
                          <div className="text-sm text-tertiary">Status</div>
                          <div className={`text-lg font-semibold ${
                            healthData.status === 'healthy' ? 'text-green-600' : 'text-red-600'
                          }`}>
                            {healthData.status}
                          </div>
                        </div>
                        <div className="bg-primary border border-tertiary/20 rounded-lg p-4">
                          <div className="text-sm text-tertiary">Version</div>
                          <div className="text-lg font-semibold text-primary">{healthData.version}</div>
                        </div>
                        <div className="bg-primary border border-tertiary/20 rounded-lg p-4">
                          <div className="text-sm text-tertiary">Uptime</div>
                          <div className="text-lg font-semibold text-primary">{formatUptime(healthData.uptime_seconds)}</div>
                        </div>
                        <div className="bg-primary border border-tertiary/20 rounded-lg p-4">
                          <div className="text-sm text-tertiary">Memory Usage</div>
                          <div className="text-lg font-semibold text-primary">
                            {formatBytes(healthData.memory_usage.used_bytes)}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Collections Table */}
                {qdrantData && (
                  <div className="rounded-lg overflow-hidden bg-secondary border border-tertiary/20">
                    <div className="px-6 py-4 border-b border-tertiary/20 bg-tertiary/10 flex justify-between items-center">
                      <h2 className="text-lg font-semibold text-primary">Vector Collections</h2>
                      <div className="flex items-center space-x-4">
                        <div className="text-sm text-secondary">
                          <span className="font-medium">{qdrantData.total_collections}</span> Collections •
                          <span className="font-medium">{qdrantData.total_vectors.toLocaleString()}</span> Vectors
                        </div>
                        <button className="px-4 py-2 bg-accent text-on-accent rounded-lg hover:bg-accent/90 transition-colors flex items-center space-x-2">
                          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M5 12h14"></path>
                            <path d="M12 5v14"></path>
                          </svg>
                          <span>Create Collection</span>
                        </button>
                      </div>
                    </div>

                    <div className="overflow-x-auto">
                      <table className="w-full">
                        <thead className="bg-tertiary/10">
                          <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-secondary">Collection Name</th>
                            <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-secondary">Vectors Count</th>
                            <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-secondary">Vector Size</th>
                            <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-secondary">Distance</th>
                            <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-secondary">Status</th>
                            <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-secondary">Actions</th>
                          </tr>
                        </thead>
                        <tbody className="bg-secondary">
                          {qdrantData.collections.map((collection) => (
                            <tr key={collection.name} className="border-b hover:bg-gray-50" style={{borderColor: 'var(--border-color)'}}>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-primary font-medium">{collection.name}</td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-center text-primary">{collection.vectors_count.toLocaleString()}</td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-center text-primary">{collection.config.params.vectors.size}</td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-center text-primary">{collection.config.params.vectors.distance}</td>
                              <td className="px-6 py-4 whitespace-nowrap text-center">
                                <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                                  collection.status === 'green'
                                    ? 'bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400'
                                    : collection.status === 'yellow'
                                    ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-400'
                                    : 'bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400'
                                }`}>
                                  {collection.status}
                                </span>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-center">
                                <div className="flex items-center justify-center space-x-2">
                                  <button
                                    className="p-2 bg-tertiary border border-tertiary/20 rounded-lg text-secondary hover:bg-primary hover:text-primary transition-colors"
                                    title="View Details"
                                  >
                                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                      <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"></path>
                                      <circle cx="12" cy="12" r="3"></circle>
                                    </svg>
                                  </button>
                                  <button
                                    className="p-2 bg-tertiary border border-tertiary/20 rounded-lg text-secondary hover:bg-red-500 hover:text-white transition-colors"
                                    title="Delete Collection"
                                  >
                                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                      <path d="M10 11v6"></path>
                                      <path d="M14 11v6"></path>
                                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"></path>
                                      <path d="M3 6h18"></path>
                                      <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                                    </svg>
                                  </button>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </main>
      </div>
    </div>
  )
}

export default QdrantPage
