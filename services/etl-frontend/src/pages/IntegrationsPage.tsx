import React, { useState, useEffect } from 'react'
import { Loader2 } from 'lucide-react'
import Header from '../components/Header'
import CollapsedSidebar from '../components/CollapsedSidebar'
import IntegrationLogo from '../components/IntegrationLogo'
import EditModal from '../components/EditModal'
import CreateModal from '../components/CreateModal'
import ConfirmationModal from '../components/ConfirmationModal'
import ToastContainer from '../components/ToastContainer'
import { integrationsApi } from '../services/etlApiService'
import { useToast } from '../hooks/useToast'
import { useConfirmation } from '../hooks/useConfirmation'

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
  const { toasts, removeToast, showSuccess, showError } = useToast()
  const { confirmation, confirmDelete, hideConfirmation } = useConfirmation()

  // Edit modal state
  const [editModal, setEditModal] = useState({
    isOpen: false,
    integration: null as Integration | null
  })

  // Create modal state
  const [createModal, setCreateModal] = useState({
    isOpen: false
  })

  // Logo file state
  const [selectedLogoFile, setSelectedLogoFile] = useState<File | null>(null)

  // Filter states
  const [integrationNameFilter, setIntegrationNameFilter] = useState('')
  const [providerFilter, setProviderFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  // Filtered integrations based on filter states
  const filteredIntegrations = integrations.filter(integration => {
    const matchesName = !integrationNameFilter ||
      integration.name.toLowerCase().includes(integrationNameFilter.toLowerCase())
    const matchesProvider = !providerFilter ||
      integration.name.toLowerCase().includes(providerFilter.toLowerCase())
    const matchesStatus = !statusFilter ||
      (statusFilter === 'active' && integration.active) ||
      (statusFilter === 'inactive' && !integration.active)

    return matchesName && matchesProvider && matchesStatus
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

  // Handle logo file selection
  const handleLogoFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) {
      setSelectedLogoFile(null)
      return
    }

    // Validate file type - only SVG allowed
    if (file.type !== 'image/svg+xml') {
      showError('Invalid File Type', 'Please select an SVG file only')
      event.target.value = ''
      setSelectedLogoFile(null)
      return
    }

    // Validate file size (max 1MB for SVG)
    if (file.size > 1 * 1024 * 1024) {
      showError('File Too Large', 'SVG file size must be less than 1MB')
      event.target.value = ''
      setSelectedLogoFile(null)
      return
    }

    setSelectedLogoFile(file)
  }

  // Handle edit
  const handleEdit = (integrationId: number) => {
    const integration = integrations.find(i => i.id === integrationId)
    if (integration) {
      setSelectedLogoFile(null) // Reset logo file
      setEditModal({
        isOpen: true,
        integration
      })
    }
  }

  // Handle edit save
  const handleEditSave = async (formData: Record<string, any>) => {
    if (!editModal.integration) return

    try {
      let logoFilename = editModal.integration.logo_filename || null

      // If a new logo file was selected, upload it with the provider name
      if (selectedLogoFile) {
        // Rename file to provider name (lowercase) + .svg
        const providerName = formData.provider || editModal.integration.name
        const newFileName = `${providerName.toLowerCase()}.svg`

        // Create a new file with the correct name
        const renamedFile = new File([selectedLogoFile], newFileName, { type: selectedLogoFile.type })

        const uploadResponse = await integrationsApi.uploadLogo(renamedFile)
        logoFilename = uploadResponse.data.filename
      }

      const updateData: any = {
        base_url: formData.base_url || null,
        username: formData.username || null,
        ai_model: formData.ai_model || null,
        logo_filename: logoFilename
      }

      // Only include password if it was provided
      if (formData.password && formData.password.trim() !== '') {
        updateData.password = formData.password
      }

      await integrationsApi.updateIntegration(editModal.integration.id, updateData)

      // Refresh the integrations list to get updated data
      const refreshResponse = await integrationsApi.getIntegrations()

      // Force image cache refresh by updating the state with new timestamp
      const updatedIntegrations = refreshResponse.data.map((integration: Integration) => ({
        ...integration,
        // Add timestamp to force logo reload if it was updated
        logo_filename: integration.logo_filename && integration.id === editModal.integration?.id && selectedLogoFile
          ? `${integration.logo_filename}?t=${Date.now()}`
          : integration.logo_filename
      }))

      setIntegrations(updatedIntegrations)

      showSuccess('Integration Updated', 'The integration has been updated successfully.')
      setEditModal({ isOpen: false, integration: null })
      setSelectedLogoFile(null)
    } catch (error: any) {
      console.error('Error updating integration:', error)
      const errorMessage = error.response?.data?.detail || 'Failed to update integration. Please try again.'
      showError('Update Failed', errorMessage)
    }
  }

  // Handle create save
  const handleCreateSave = async (formData: Record<string, any>) => {
    try {
      let logoFilename = null

      // If a logo file was selected, upload it with the provider name
      if (selectedLogoFile) {
        // Rename file to provider name (lowercase) + .svg
        const providerName = formData.provider
        const newFileName = `${providerName.toLowerCase()}.svg`

        // Create a new file with the correct name
        const renamedFile = new File([selectedLogoFile], newFileName, { type: selectedLogoFile.type })

        const uploadResponse = await integrationsApi.uploadLogo(renamedFile)
        logoFilename = uploadResponse.data.filename
      }

      const createData: any = {
        provider: formData.provider,
        type: formData.type,
        base_url: formData.base_url || null,
        username: formData.username || null,
        password: formData.password || null,
        ai_model: formData.ai_model || null,
        logo_filename: logoFilename,
        active: true
      }

      await integrationsApi.createIntegration(createData)

      // Refresh the integrations list
      const refreshResponse = await integrationsApi.getIntegrations()

      // Add timestamp to new logo to force cache refresh
      const updatedIntegrations = refreshResponse.data.map((integration: Integration) => ({
        ...integration,
        logo_filename: integration.logo_filename && integration.name.toLowerCase() === formData.provider.toLowerCase() && selectedLogoFile
          ? `${integration.logo_filename}?t=${Date.now()}`
          : integration.logo_filename
      }))

      setIntegrations(updatedIntegrations)

      showSuccess('Integration Created', 'The integration has been created successfully.')
      setCreateModal({ isOpen: false })
      setSelectedLogoFile(null)
    } catch (error: any) {
      console.error('Error creating integration:', error)
      const errorMessage = error.response?.data?.detail || 'Failed to create integration. Please try again.'
      showError('Create Failed', errorMessage)
    }
  }

  // Handle toggle active/inactive
  const handleToggleActive = async (integrationId: number, currentActive: boolean) => {
    try {
      const integration = integrations.find(i => i.id === integrationId)
      if (!integration) return

      const updateData = {
        base_url: integration.base_url || null,
        username: integration.username || null,
        ai_model: integration.ai_model || null,
        logo_filename: integration.logo_filename || null,
        active: !currentActive
      }

      await integrationsApi.updateIntegration(integrationId, updateData)

      // Update local state
      setIntegrations(prev => prev.map(i =>
        i.id === integrationId ? { ...i, active: !currentActive } : i
      ))

      showSuccess(
        'Integration Updated',
        `Integration ${!currentActive ? 'activated' : 'deactivated'} successfully.`
      )
    } catch (error: any) {
      console.error('Error toggling integration:', error)
      const errorMessage = error.response?.data?.detail || 'Failed to update integration. Please try again.'
      showError('Update Failed', errorMessage)
    }
  }

  // Handle delete
  const handleDelete = async (integrationId: number) => {
    const integration = integrations.find(i => i.id === integrationId)
    if (!integration) return

    confirmDelete(
      integration.name,
      async () => {
        try {
          await integrationsApi.deleteIntegration(integrationId)
          setIntegrations(prev => prev.filter(i => i.id !== integrationId))
          showSuccess('Integration Deleted', 'The integration has been deleted successfully.')
        } catch (error) {
          console.error('Error deleting integration:', error)
          showError('Delete Failed', 'Failed to delete integration. Please try again.')
        }
      }
    )
  }

  return (
    <div className="min-h-screen">
      <Header />
      <div className="flex">
        <CollapsedSidebar />
        <main className="flex-1 ml-16 py-8">
          <div className="ml-12 mr-12">
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
            {loading ? (
              <div className="bg-secondary rounded-lg shadow-sm p-6">
                <div className="text-center py-12">
                  <Loader2 className="h-12 w-12 animate-spin mx-auto mb-4 text-primary" />
                  <h2 className="text-2xl font-semibold text-primary mb-2">
                    Loading...
                  </h2>
                  <p className="text-secondary">
                    Fetching integrations
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
            ) : integrations.length === 0 ? (
              <div className="bg-secondary rounded-lg shadow-sm p-6">
                <div className="text-center py-12">
                  <div className="text-6xl mb-4">🔗</div>
                  <h2 className="text-2xl font-semibold text-primary mb-2">
                    No Integrations Found
                  </h2>
                  <p className="text-secondary">
                    No integrations have been configured yet.
                  </p>
                </div>
              </div>
            ) : (
              <>
                  {/* Filters Section */}
                  <div className="mb-6 p-6 rounded-lg shadow-md border border-transparent"
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = 'var(--color-1)'
                      e.currentTarget.style.boxShadow = '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)'
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = 'transparent'
                      e.currentTarget.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
                    }}
                  >
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
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
                  <div className="rounded-lg bg-table-container shadow-md overflow-hidden border border-transparent"
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = 'var(--color-1)'
                      e.currentTarget.style.boxShadow = '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)'
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = 'transparent'
                      e.currentTarget.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
                    }}
                  >
                      <div className="px-6 py-5 flex justify-between items-center bg-table-header">
                        <h2 className="text-lg font-semibold text-table-header">Integrations</h2>
                      <button
                        onClick={() => setCreateModal({ isOpen: true })}
                        className="px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2 font-medium shadow-sm"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M5 12h14"></path>
                          <path d="M12 5v14"></path>
                        </svg>
                        <span>Create Integration</span>
                      </button>
                    </div>

                      <div className="overflow-x-auto">
                        <table className="w-full">
                          <thead>
                            <tr className="bg-table-column-header">
                              <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-table-column-header">Name</th>
                              <th className="px-6 py-4 text-center text-xs font-semibold uppercase tracking-wider text-table-column-header">Logo</th>
                              <th className="px-6 py-4 text-center text-xs font-semibold uppercase tracking-wider text-table-column-header">Provider</th>
                              <th className="px-6 py-4 text-center text-xs font-semibold uppercase tracking-wider text-table-column-header">URL</th>
                              <th className="px-6 py-4 text-center text-xs font-semibold uppercase tracking-wider text-table-column-header">Active</th>
                              <th className="px-6 py-4 text-center text-xs font-semibold uppercase tracking-wider text-table-column-header">Actions</th>
                            </tr>
                          </thead>
                          <tbody>
                            {filteredIntegrations.map((integration, index) => (
                              <tr
                                key={integration.id}
                                className={`${index % 2 === 0 ? 'bg-table-row-even' : 'bg-table-row-odd'}`}
                              >
                                <td className="px-6 py-5 whitespace-nowrap text-sm text-table-row">
                                  <span className="font-semibold">{integration.name}</span>
                                </td>
                                <td className="px-6 py-5 whitespace-nowrap text-center">
                                  <div className="flex items-center justify-center">
                                    {integration.logo_filename ? (
                                      <IntegrationLogo
                                        logoFilename={integration.logo_filename}
                                        integrationName={integration.name}
                                        className="h-8 w-auto max-w-20 object-contain"
                                      />
                                    ) : (
                                      <div className="w-8 h-8 bg-accent rounded flex items-center justify-center text-on-accent font-semibold text-sm">
                                        {integration.name.charAt(0).toUpperCase()}
                                      </div>
                                    )}
                                  </div>
                                </td>
                                <td className="px-6 py-5 whitespace-nowrap text-sm text-center text-table-row">{integration.name}</td>
                              <td className="px-6 py-5 whitespace-nowrap text-sm text-center text-table-row">
                                {integration.base_url ? (
                                  <a href={integration.base_url} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">
                                    {integration.base_url.length > 30 ? `${integration.base_url.substring(0, 30)}...` : integration.base_url}
                                  </a>
                                ) : '-'}
                              </td>
                              <td className="px-6 py-5 whitespace-nowrap text-center">
                                <div
                                  className="job-toggle-switch cursor-pointer"
                                  onClick={() => handleToggleActive(integration.id, integration.active)}
                                >
                                  <div className={`toggle-switch ${integration.active ? 'active' : ''}`}>
                                    <div className="toggle-slider"></div>
                                  </div>
                                  <span className="toggle-label">{integration.active ? 'On' : 'Off'}</span>
                                </div>
                              </td>
                              <td className="px-6 py-5 whitespace-nowrap text-center">
                                <div className="flex items-center justify-center space-x-2">
                                  <button
                                    onClick={() => handleEdit(integration.id)}
                                    className="p-2 rounded bg-tertiary text-secondary hover:bg-secondary hover:text-accent shadow-sm hover:shadow-md transition-all"
                                    title="Edit"
                                  >
                                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                                      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                                    </svg>
                                  </button>
                                  <button
                                    onClick={() => handleDelete(integration.id)}
                                    className="p-2 rounded bg-tertiary text-secondary hover:bg-secondary hover:text-red-500 shadow-sm hover:shadow-md transition-all"
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
        </main>
      </div>

      {/* Edit Modal */}
      {editModal.integration && (
        <EditModal
          isOpen={editModal.isOpen}
          onClose={() => {
            setEditModal({ isOpen: false, integration: null })
            setSelectedLogoFile(null)
          }}
          onSave={handleEditSave}
          title="Edit Integration"
          fields={[
            {
              name: 'provider',
              label: 'Provider',
              type: 'text',
              value: editModal.integration.name,
              disabled: true
            },
            {
              name: 'type',
              label: 'Type',
              type: 'text',
              value: editModal.integration.integration_type,
              disabled: true
            },
            {
              name: 'base_url',
              label: 'Base URL',
              type: 'text',
              value: editModal.integration.base_url || '',
              placeholder: 'https://example.com'
            },
            {
              name: 'logo_file',
              label: 'Integration Logo',
              type: 'text',
              value: editModal.integration.logo_filename || '',
              placeholder: 'Upload SVG logo',
              customRender: (_field: any, _formData: any, _handleInputChange: any, _errors: any) => {
                const currentLogo = selectedLogoFile
                  ? URL.createObjectURL(selectedLogoFile)
                  : editModal.integration?.logo_filename
                    ? `/assets/integrations/${editModal.integration.logo_filename}`
                    : null

                return (
                  <div className="space-y-3">
                    {/* Logo Preview */}
                    <div className="flex items-center space-x-4">
                      <div className="w-16 h-16 rounded-lg border-2 border-border bg-tertiary flex items-center justify-center overflow-hidden">
                        {currentLogo ? (
                          <img
                            src={currentLogo}
                            alt="Integration logo"
                            className="w-12 h-12 object-contain"
                            onError={(e) => {
                              e.currentTarget.style.display = 'none'
                              e.currentTarget.parentElement!.innerHTML = '<span class="text-2xl text-muted">?</span>'
                            }}
                          />
                        ) : (
                          <span className="text-2xl text-muted">?</span>
                        )}
                      </div>

                      {/* Upload Button */}
                      <div className="relative">
                        <input
                          type="file"
                          accept="image/svg+xml"
                          onChange={(e) => {
                            handleLogoFileSelect(e)
                          }}
                          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                        />
                        <button
                          type="button"
                          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                            <polyline points="17 8 12 3 7 8"></polyline>
                            <line x1="12" x2="12" y1="3" y2="15"></line>
                          </svg>
                          <span>{currentLogo ? 'Change Logo' : 'Upload Logo'}</span>
                        </button>
                      </div>
                    </div>

                    {/* Status Message */}
                    {selectedLogoFile && (
                      <p className="text-xs text-green-600">
                        ✓ New logo selected
                      </p>
                    )}
                    <p className="text-xs text-secondary">
                      SVG format only, max 1MB
                    </p>
                  </div>
                )
              }
            },
            {
              name: 'username',
              label: 'Username',
              type: 'text',
              value: editModal.integration.username || '',
              placeholder: 'Enter username'
            },
            {
              name: 'password',
              label: 'Password/Token',
              type: 'text',
              value: '',
              placeholder: 'Leave blank to keep current password'
            },
            {
              name: 'ai_model',
              label: 'Model',
              type: 'text',
              value: editModal.integration.ai_model || '',
              placeholder: 'e.g., all-MiniLM-L6-v2, gpt-4o-mini'
            }
          ]}
        />
      )}

      {/* Create Modal */}
      <CreateModal
        isOpen={createModal.isOpen}
        onClose={() => {
          setCreateModal({ isOpen: false })
          setSelectedLogoFile(null)
        }}
        onSave={handleCreateSave}
        title="Create Integration"
        fields={[
          {
            name: 'provider',
            label: 'Provider',
            type: 'text',
            required: true,
            placeholder: 'e.g., jira, github, local_embeddings'
          },
          {
            name: 'type',
            label: 'Type',
            type: 'select',
            required: true,
            defaultValue: 'Data',
            options: [
              { value: 'Data', label: 'Data' },
              { value: 'AI', label: 'AI' },
              { value: 'Embedding', label: 'Embedding' }
            ]
          },
          {
            name: 'base_url',
            label: 'Base URL',
            type: 'text',
            placeholder: 'https://example.com'
          },
          {
            name: 'logo_file',
            label: 'Integration Logo',
            type: 'text',
            placeholder: 'Upload SVG logo',
            customRender: (_field: any, _formData: any, _handleInputChange: any, _errors: any) => {
              const currentLogo = selectedLogoFile
                ? URL.createObjectURL(selectedLogoFile)
                : null

              return (
                <div className="space-y-3">
                  {/* Logo Preview */}
                  <div className="flex items-center space-x-4">
                    <div className="w-16 h-16 rounded-lg border-2 border-border bg-tertiary flex items-center justify-center overflow-hidden">
                      {currentLogo ? (
                        <img
                          src={currentLogo}
                          alt="Integration logo"
                          className="w-12 h-12 object-contain"
                        />
                      ) : (
                        <span className="text-2xl text-muted">?</span>
                      )}
                    </div>

                    {/* Upload Button */}
                    <div className="relative">
                      <input
                        type="file"
                        accept="image/svg+xml"
                        onChange={(e) => {
                          handleLogoFileSelect(e)
                        }}
                        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                      />
                      <button
                        type="button"
                        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                          <polyline points="17 8 12 3 7 8"></polyline>
                          <line x1="12" x2="12" y1="3" y2="15"></line>
                        </svg>
                        <span>Upload Logo</span>
                      </button>
                    </div>
                  </div>

                  {/* Status Message */}
                  {selectedLogoFile && (
                    <p className="text-xs text-green-600">
                      ✓ Logo selected
                    </p>
                  )}
                  <p className="text-xs text-secondary">
                    SVG format only, max 1MB
                  </p>
                </div>
              )
            }
          },
          {
            name: 'username',
            label: 'Username',
            type: 'text',
            placeholder: 'Enter username'
          },
          {
            name: 'password',
            label: 'Password/Token',
            type: 'text',
            placeholder: 'Enter password or token'
          },
          {
            name: 'ai_model',
            label: 'Model',
            type: 'text',
            placeholder: 'e.g., all-MiniLM-L6-v2, gpt-4o-mini'
          }
        ]}
      />

      {/* Confirmation Modal */}
      <ConfirmationModal
        isOpen={confirmation.isOpen}
        onClose={hideConfirmation}
        onConfirm={confirmation.onConfirm}
        title={confirmation.title}
        message={confirmation.message}
        confirmText={confirmation.confirmText}
        cancelText={confirmation.cancelText}
        type={confirmation.type}
        icon={confirmation.icon}
      />

      {/* Toast Notifications */}
      <ToastContainer toasts={toasts} onRemoveToast={removeToast} />
    </div>
  )
}

export default IntegrationsPage
