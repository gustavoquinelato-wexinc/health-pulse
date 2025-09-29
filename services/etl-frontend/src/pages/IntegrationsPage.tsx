import React, { useState, useEffect } from 'react'
import Header from '../components/Header'
import CollapsedSidebar from '../components/CollapsedSidebar'
import { integrationsApi } from '../services/etlApiService'

interface Integration {
  id: number
  name: string
  integration_type: string
  base_url?: string
  username?: string
  ai_model?: string
  logo_filename?: string
  active: boolean
  last_sync_at?: string
}

const IntegrationsPage: React.FC = () => {
  const [integrations, setIntegrations] = useState<Integration[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Filtered integrations based on filter states
  const filteredIntegrations = integrations.filter(integration => {
    const matchesName = !integrationNameFilter ||
      integration.name.toLowerCase().includes(integrationNameFilter.toLowerCase())
    const matchesType = !typeFilter ||
      integration.integration_type.toLowerCase().includes(typeFilter.toLowerCase())
    const matchesProvider = !providerFilter ||
      integration.name.toLowerCase().includes(providerFilter.toLowerCase())
    const matchesStatus = !statusFilter ||
      (statusFilter === 'active' && integration.active) ||
      (statusFilter === 'inactive' && !integration.active)

    return matchesName && matchesType && matchesProvider && matchesStatus
  })

  useEffect(() => {
    const fetchIntegrations = async () => {
      try {
        setLoading(true)
        const response = await integrationsApi.getIntegrations()
        setIntegrations(response.data)
        setError(null)
      } catch (err) {
        console.error('Error fetching integrations:', err)
        setError('Failed to load integrations')
      } finally {
        setLoading(false)
      }
    }

    fetchIntegrations()
  }, [])

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
                    Integrations
                  </h1>
                  <p className="text-lg text-secondary">
                    Manage data source integrations and connections
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
            <div className="bg-secondary rounded-lg shadow-sm p-6">
              {loading ? (
                <div className="text-center py-12">
                  <div className="text-6xl mb-4">⏳</div>
                  <h2 className="text-2xl font-semibold text-primary mb-2">
                    Loading...
                  </h2>
                  <p className="text-secondary">
                    Fetching integrations
                  </p>
                </div>
              ) : error ? (
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
              ) : integrations.length === 0 ? (
                <div className="text-center py-12">
                  <div className="text-6xl mb-4">🔗</div>
                  <h2 className="text-2xl font-semibold text-primary mb-2">
                    No Integrations Found
                  </h2>
                  <p className="text-secondary">
                    No integrations have been configured yet.
                  </p>
                </div>
              ) : (
                <>
                  {/* Filters Section */}
                  <div className="mb-6 p-4 rounded-lg bg-secondary border border-tertiary/20">
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                      {/* Integration Name Filter */}
                      <div>
                        <label className="block text-sm font-medium mb-2 text-primary">Integration Name</label>
                        <input
                          type="text"
                          placeholder="Filter by integration name..."
                          value={integrationNameFilter}
                          onChange={(e) => setIntegrationNameFilter(e.target.value)}
                          className="w-full px-3 py-2 border border-tertiary/20 rounded-lg bg-primary text-primary"
                        />
                      </div>

                      {/* Type Filter */}
                      <div>
                        <label className="block text-sm font-medium mb-2 text-primary">Type</label>
                        <select
                          value={typeFilter}
                          onChange={(e) => setTypeFilter(e.target.value)}
                          className="w-full px-3 py-2 border border-tertiary/20 rounded-lg bg-primary text-primary"
                        >
                          <option value="">All Types</option>
                          <option value="data">Data</option>
                          <option value="ai">AI</option>
                          <option value="embedding">Embedding</option>
                        </select>
                      </div>

                      {/* Provider Filter */}
                      <div>
                        <label className="block text-sm font-medium mb-2 text-primary">Provider</label>
                        <select
                          value={providerFilter}
                          onChange={(e) => setProviderFilter(e.target.value)}
                          className="w-full px-3 py-2 border border-tertiary/20 rounded-lg bg-primary text-primary"
                        >
                          <option value="">All Providers</option>
                          <option value="GitHub">GitHub</option>
                          <option value="Jira">Jira</option>
                        </select>
                      </div>

                      {/* Status Filter */}
                      <div>
                        <label className="block text-sm font-medium mb-2 text-primary">Status</label>
                        <select
                          value={statusFilter}
                          onChange={(e) => setStatusFilter(e.target.value)}
                          className="w-full px-3 py-2 border border-tertiary/20 rounded-lg bg-primary text-primary"
                        >
                          <option value="">All Statuses</option>
                          <option value="active">Active</option>
                          <option value="inactive">Inactive</option>
                        </select>
                      </div>
                    </div>
                  </div>

                  {/* Integrations Table */}
                  <div className="rounded-lg overflow-hidden bg-secondary border border-tertiary/20">
                    <div className="px-6 py-4 border-b border-tertiary/20 bg-tertiary/10 flex justify-between items-center">
                      <h2 className="text-lg font-semibold text-primary">Integrations</h2>
                      <button className="px-4 py-2 bg-accent text-on-accent rounded-lg hover:bg-accent/90 transition-colors flex items-center space-x-2">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M5 12h14"></path>
                          <path d="M12 5v14"></path>
                        </svg>
                        <span>Create Integration</span>
                      </button>
                    </div>

                    <div className="overflow-x-auto">
                      <table className="w-full">
                        <thead className="bg-tertiary/10">
                          <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-secondary">Name</th>
                            <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-secondary">Type</th>
                            <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-secondary">Provider</th>
                            <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-secondary">URL</th>
                            <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-secondary">Active</th>
                            <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-secondary">Actions</th>
                          </tr>
                        </thead>
                        <tbody className="bg-secondary">
                          {filteredIntegrations.map((integration) => (
                            <tr key={integration.id} className="border-b hover:bg-gray-50" style={{borderColor: 'var(--border-color)'}}>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-primary">
                                <div className="flex items-center space-x-3">
                                  {integration.logo_filename ? (
                                    <img
                                      src={`/assets/integrations/${integration.logo_filename}`}
                                      alt={integration.name}
                                      className="h-6 w-auto max-w-16 object-contain"
                                      onError={(e) => {
                                        e.currentTarget.style.display = 'none';
                                        if (e.currentTarget.nextElementSibling) {
                                          (e.currentTarget.nextElementSibling as HTMLElement).style.display = 'flex';
                                        }
                                      }}
                                    />
                                  ) : null}
                                  <div className="w-6 h-6 bg-accent rounded flex items-center justify-center text-on-accent font-semibold text-xs" style={{ display: integration.logo_filename ? 'none' : 'flex' }}>
                                    {integration.name.charAt(0).toUpperCase()}
                                  </div>
                                  <span className="font-medium">{integration.name}</span>
                                </div>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-center text-primary">{integration.integration_type}</td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-center text-primary">{integration.name}</td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-center text-primary">
                                {integration.base_url ? (
                                  <a href={integration.base_url} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">
                                    {integration.base_url.length > 30 ? `${integration.base_url.substring(0, 30)}...` : integration.base_url}
                                  </a>
                                ) : '-'}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-center">
                                <div className="job-toggle-switch">
                                  <div className={`toggle-switch ${integration.active ? 'active' : ''}`}>
                                    <div className="toggle-slider"></div>
                                  </div>
                                  <span className="toggle-label">{integration.active ? 'On' : 'Off'}</span>
                                </div>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-center">
                                <div className="flex items-center justify-center space-x-2">
                                  <button
                                    className="p-2 bg-tertiary border border-tertiary/20 rounded-lg text-secondary hover:bg-primary hover:text-primary transition-colors"
                                    title="Edit"
                                  >
                                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                                      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                                    </svg>
                                  </button>
                                  <button
                                    className="p-2 bg-tertiary border border-tertiary/20 rounded-lg text-secondary hover:bg-red-500 hover:text-white transition-colors"
                                    title="Delete"
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
                </>
              )}
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}

export default IntegrationsPage
