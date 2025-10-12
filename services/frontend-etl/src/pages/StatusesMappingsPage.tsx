import React, { useState, useEffect } from 'react'
import { Loader2 } from 'lucide-react'
import Header from '../components/Header'
import CollapsedSidebar from '../components/CollapsedSidebar'
import DependencyModal from '../components/DependencyModal'
import ConfirmationModal from '../components/ConfirmationModal'
import EditModal from '../components/EditModal'
import CreateModal from '../components/CreateModal'
import ToastContainer from '../components/ToastContainer'
import IntegrationLogo from '../components/IntegrationLogo'
import { useToast } from '../hooks/useToast'
import { useConfirmation } from '../hooks/useConfirmation'
import { statusesApi, integrationsApi } from '../services/etlApiService'

interface StatusMapping {
  id: number
  status_from: string
  status_to: string
  status_category?: string
  workflow_step_name?: string
  workflow_id?: number
  step_number?: number
  integration_name?: string
  integration_id?: number
  integration_logo?: string
  active: boolean
}

interface Integration {
  id: number
  name: string
  integration_type: string
  logo_filename?: string
  active: boolean
}

interface StatusesMappingsPageProps {
  embedded?: boolean
}

const StatusesMappingsPage: React.FC<StatusesMappingsPageProps> = ({ embedded = false }) => {
  const [mappings, setMappings] = useState<StatusMapping[]>([])
  const [integrations, setIntegrations] = useState<Integration[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [queueing, setQueueing] = useState(false)
  const { toasts, removeToast, showSuccess, showError } = useToast()
  const { confirmation, confirmDelete, hideConfirmation } = useConfirmation()

  // Filter states
  const [sourceStatusFilter, setSourceStatusFilter] = useState('')
  const [targetStatusFilter, setTargetStatusFilter] = useState('')
  const [integrationFilter, setIntegrationFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  // Edit modal state
  const [editModal, setEditModal] = useState({
    isOpen: false,
    mapping: null as StatusMapping | null
  })

  // Create modal state
  const [createModal, setCreateModal] = useState({
    isOpen: false
  })

  // Dependency modal state
  const [dependencyModal, setDependencyModal] = useState({
    isOpen: false,
    mappingId: null as number | null,
    mappingName: '',
    action: 'deactivate' as 'deactivate' | 'activate',
    dependencies: [] as any[],
    reassignmentTargets: [] as any[]
  })

  // Handler functions
  const checkDependencies = async (mappingId: number): Promise<any> => {
    try {
      // TODO: Implement actual dependency checking API call
      return {
        has_dependencies: Math.random() > 0.7,
        dependency_count: Math.floor(Math.random() * 3) + 1,
        affected_items_count: Math.floor(Math.random() * 10) + 1,
        reassignment_targets: mappings.filter(m => m.id !== mappingId && m.active).slice(0, 3)
      }
    } catch (error) {
      console.error('Error checking dependencies:', error)
      throw new Error('Failed to check dependencies')
    }
  }

  const handleToggleActive = async (mappingId: number, currentActive: boolean) => {
    try {
      const mapping = mappings.find(m => m.id === mappingId)
      if (!mapping) return

      if (currentActive) {
        // Deactivating - check for dependencies
        const dependencyData = await checkDependencies(mappingId)

        if (dependencyData.has_dependencies) {
          setDependencyModal({
            isOpen: true,
            mappingId,
            mappingName: `${mapping.status_from} → ${mapping.status_to}`,
            action: 'deactivate',
            dependencies: dependencyData.dependent_mappings || [],
            reassignmentTargets: dependencyData.reassignment_targets || []
          })
          return
        }
      }

      // No dependencies or activating - proceed directly
      await performToggle(mappingId, !currentActive)
    } catch (error) {
      console.error('Error toggling mapping:', error)
      showError('Toggle Failed', 'Failed to toggle mapping status. Please try again.')
    }
  }

  const performToggle = async (mappingId: number, newActiveState: boolean) => {
    try {
      // TODO: Implement actual API call when backend endpoint is ready
      // For now, just update local state after a small delay to simulate API call
      await new Promise(resolve => setTimeout(resolve, 100))

      // Update local state only after "API call" succeeds
      setMappings(prev => prev.map(mapping =>
        mapping.id === mappingId
          ? { ...mapping, active: newActiveState }
          : mapping
      ))

      setDependencyModal(prev => ({ ...prev, isOpen: false }))
      showSuccess(
        `Status Mapping ${newActiveState ? 'Activated' : 'Deactivated'}`,
        `The status mapping has been ${newActiveState ? 'activated' : 'deactivated'} successfully.`
      )
    } catch (error) {
      console.error('Error updating mapping:', error)
      showError('Update Failed', 'Failed to update mapping status. Please try again.')
    }
  }

  // Handle edit
  const handleEdit = (mappingId: number) => {
    const mapping = mappings.find(m => m.id === mappingId)
    if (mapping) {
      setEditModal({
        isOpen: true,
        mapping
      })
    }
  }

  // Handle edit save
  const handleEditSave = async (formData: Record<string, any>) => {
    if (!editModal.mapping) return

    try {
      const updateData = {
        status_from: formData.status_from,
        status_to: formData.status_to,
        status_category: formData.status_category,
        workflow_id: formData.workflow_id ? parseInt(formData.workflow_id) : null,
        integration_id: formData.integration_id ? parseInt(formData.integration_id) : null
      }

      const response = await statusesApi.updateStatusMapping(editModal.mapping.id, updateData)

      // Get integration info from the frontend state (already loaded)
      const selectedIntegration = integrations.find(i => i.id === updateData.integration_id)

      // Update local state with response data plus integration info from frontend
      const updatedMapping = {
        ...(response.data || response),
        integration_name: selectedIntegration?.name || null,
        integration_logo: selectedIntegration?.logo_filename || null
      }

      setMappings(prev => prev.map(m =>
        m.id === editModal.mapping!.id
          ? updatedMapping
          : m
      ))

      showSuccess('Mapping Updated', 'The status mapping has been updated successfully.')
      setEditModal({ isOpen: false, mapping: null })
    } catch (error) {
      console.error('Error updating mapping:', error)
      showError('Update Failed', 'Failed to update status mapping. Please try again.')
    }
  }

  // Handle create save
  const handleCreateSave = async (formData: Record<string, any>) => {
    try {
      const createData = {
        status_from: formData.status_from,
        status_to: formData.status_to,
        status_category: formData.status_category,
        workflow_id: formData.workflow_id ? parseInt(formData.workflow_id) : null,
        integration_id: formData.integration_id ? parseInt(formData.integration_id) : null
      }

      const response = await statusesApi.createStatusMapping(createData)

      // Get integration info from the frontend state (already loaded)
      const selectedIntegration = integrations.find(i => i.id === createData.integration_id)

      // Add new mapping to local state with integration info from frontend
      const newMapping = {
        ...(response.data || response),
        integration_name: selectedIntegration?.name || null,
        integration_logo: selectedIntegration?.logo_filename || null
      }

      setMappings(prev => [...prev, newMapping])

      showSuccess('Mapping Created', 'The status mapping has been created successfully.')
      setCreateModal({ isOpen: false })
    } catch (error) {
      console.error('Error creating mapping:', error)
      showError('Create Failed', 'Failed to create status mapping. Please try again.')
    }
  }

  // Handle delete
  const handleDelete = async (mappingId: number) => {
    const mapping = mappings.find(m => m.id === mappingId)
    if (!mapping) return

    confirmDelete(
      `${mapping.status_from} → ${mapping.status_to}`,
      async () => {
        try {
          const response = await statusesApi.deleteStatusMapping(mappingId)

          // Remove from local state
          setMappings(prev => prev.filter(m => m.id !== mappingId))

          // Show success message from backend
          const message = response.data?.message || 'Status mapping deleted successfully.'
          showSuccess('Mapping Deleted', message)
        } catch (error) {
          console.error('Error deleting mapping:', error)
          showError('Delete Failed', 'Failed to delete status mapping. Please try again.')
        }
      }
    )
  }

  // Filtered mappings based on filter states
  const filteredMappings = mappings.filter(mapping => {
    const matchesSourceStatus = !sourceStatusFilter ||
      mapping.status_from.toLowerCase().includes(sourceStatusFilter.toLowerCase())
    const matchesTargetStatus = !targetStatusFilter ||
      mapping.status_to.toLowerCase().includes(targetStatusFilter.toLowerCase())
    const matchesIntegration = !integrationFilter ||
      (mapping.integration_name && mapping.integration_name.toLowerCase().includes(integrationFilter.toLowerCase()))
    const matchesStatus = !statusFilter ||
      (statusFilter === 'active' && mapping.active) ||
      (statusFilter === 'inactive' && !mapping.active)

    return matchesSourceStatus && matchesTargetStatus && matchesIntegration && matchesStatus
  })

  // Load integrations data
  const loadIntegrations = async () => {
    try {
      const response = await integrationsApi.getIntegrations()
      // Filter to only show data-type integrations (not AI providers) - case insensitive
      const dataIntegrations = response.data.filter((integration: Integration) =>
        integration.integration_type?.toLowerCase() === 'data' && integration.active
      )
      setIntegrations(dataIntegrations)
    } catch (err) {
      console.error('Error fetching integrations:', err)
      // Set fallback integrations if API fails
      setIntegrations([])
    }
  }

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        // Load both mappings and integrations in parallel
        await Promise.all([
          (async () => {
            const response = await statusesApi.getStatusMappings()
            setMappings(response.data)
          })(),
          loadIntegrations()
        ])
        setError(null)
      } catch (err) {
        console.error('Error fetching data:', err)
        setError('Failed to load status mappings')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [])

  // Queue all status mappings for vectorization
  const handleQueueForVectorization = async () => {
    try {
      setQueueing(true)
      const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001'
      const response = await fetch(`${API_BASE_URL}/app/etl/vectorization/queue-table`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('pulse_token')}`
        },
        body: JSON.stringify({
          table_name: 'status_mappings'
        })
      })

      if (!response.ok) {
        throw new Error('Failed to queue vectorization')
      }

      const result = await response.json()
      showSuccess('Queued for Vectorization', `${result.queued_count} status mappings queued for vectorization`)
    } catch (err) {
      console.error('Error queueing vectorization:', err)
      showError('Queue Failed', 'Failed to queue status mappings for vectorization')
    } finally {
      setQueueing(false)
    }
  }

  const content = (
    <>
            {/* Queue for Vectorization Button */}
            <div className="mb-6 flex justify-end">
              <button
                onClick={handleQueueForVectorization}
                disabled={queueing}
                className="px-4 py-2 rounded-lg text-white flex items-center space-x-2 transition-colors disabled:opacity-50"
                style={{ background: 'var(--gradient-1-2)' }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.opacity = '0.9'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.opacity = '1'
                }}
              >
                {queueing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
                    <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
                    <line x1="12" y1="22.08" x2="12" y2="12"></line>
                  </svg>
                )}
                <span>{queueing ? 'Queueing...' : 'Queue for Vectorization'}</span>
              </button>
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
                    Fetching status mappings
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
            ) : mappings.length === 0 ? (
              <div className="bg-secondary rounded-lg shadow-sm p-6">
                <div className="text-center py-12">
                  <div className="text-6xl mb-4">📝</div>
                  <h2 className="text-2xl font-semibold text-primary mb-2">
                    No Mappings Found
                  </h2>
                  <p className="text-secondary">
                    No status mappings have been configured yet.
                  </p>
                </div>
              </div>
            ) : (
              <>
                  {/* Filters Section */}
                  <div className="mb-6 p-6 rounded-lg shadow-md border border-gray-400">
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                      {/* Source Status Filter */}
                      <div>
                        <label className="block text-sm font-medium mb-2 text-primary">Source Status</label>
                        <input
                          type="text"
                          placeholder="Filter by source status..."
                          value={sourceStatusFilter}
                          onChange={(e) => setSourceStatusFilter(e.target.value)}
                          className="w-full px-3 py-2 border border-tertiary/20 rounded-lg bg-primary text-primary"
                        />
                      </div>

                      {/* Target Status Filter */}
                      <div>
                        <label className="block text-sm font-medium mb-2 text-primary">Target Status</label>
                        <input
                          type="text"
                          placeholder="Filter by target status..."
                          value={targetStatusFilter}
                          onChange={(e) => setTargetStatusFilter(e.target.value)}
                          className="w-full px-3 py-2 border border-tertiary/20 rounded-lg bg-primary text-primary"
                        />
                      </div>

                      {/* Integration Filter */}
                      <div>
                        <label className="block text-sm font-medium mb-2 text-primary">Integration</label>
                        <select
                          value={integrationFilter}
                          onChange={(e) => setIntegrationFilter(e.target.value)}
                          className="w-full px-3 py-2 border border-tertiary/20 rounded-lg bg-primary text-primary"
                        >
                          <option value="">All Integrations</option>
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

                  {/* Status Mappings Table */}
                  <div className="rounded-lg bg-table-container shadow-md overflow-hidden border border-gray-400">
                      <div className="px-6 py-5 flex justify-between items-center bg-table-header">
                        <h2 className="text-lg font-semibold text-table-header">Status Mappings</h2>
                      <button
                        onClick={() => {
                          if (integrations.length === 0) {
                            showError('No Integrations Available', 'Please configure at least one data integration before creating status mappings.')
                            return
                          }
                          setCreateModal({ isOpen: true })
                        }}
                        className="px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2 font-medium shadow-sm"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M5 12h14"></path>
                          <path d="M12 5v14"></path>
                        </svg>
                        <span>Create Mapping</span>
                      </button>
                    </div>

                      <div className="overflow-x-auto">
                        <table className="w-full">
                          <thead>
                            <tr className="bg-table-column-header">
                              <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-table-column-header">From Status</th>
                              <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-table-column-header">To Status</th>
                              <th className="px-6 py-4 text-center text-xs font-semibold uppercase tracking-wider text-table-column-header">Category</th>
                              <th className="px-6 py-4 text-center text-xs font-semibold uppercase tracking-wider text-table-column-header">Workflow Step</th>
                              <th className="px-6 py-4 text-center text-xs font-semibold uppercase tracking-wider text-table-column-header">Integration</th>
                              <th className="px-6 py-4 text-center text-xs font-semibold uppercase tracking-wider text-table-column-header">Active</th>
                              <th className="px-6 py-4 text-center text-xs font-semibold uppercase tracking-wider text-table-column-header">Actions</th>
                            </tr>
                          </thead>
                          <tbody>
                            {filteredMappings.map((mapping, index) => (
                              <tr
                                key={mapping.id}
                                className={`${index % 2 === 0 ? 'bg-table-row-even' : 'bg-table-row-odd'} ${!mapping.active ? 'opacity-50' : ''}`}
                              >
                                <td className="px-6 py-5 whitespace-nowrap text-sm text-table-row font-semibold">{mapping.status_from}</td>
                                <td className="px-6 py-5 whitespace-nowrap text-sm text-table-row font-semibold">{mapping.status_to}</td>
                                <td className="px-6 py-5 whitespace-nowrap text-sm text-center text-table-row">{mapping.status_category || '-'}</td>
                                <td className="px-6 py-5 whitespace-nowrap text-sm text-center text-table-row">{mapping.workflow_step_name || '-'}</td>
                              <td className="px-6 py-5 whitespace-nowrap text-center">
                                <div className="flex items-center justify-center">
                                  <IntegrationLogo
                                    logoFilename={mapping.integration_logo}
                                    integrationName={mapping.integration_name}
                                  />
                                  {!mapping.integration_logo && (
                                    <span className="text-sm text-table-row">
                                      {mapping.integration_name || '-'}
                                    </span>
                                  )}
                                </div>
                              </td>
                              <td className="px-6 py-5 whitespace-nowrap text-center">
                                <div
                                  className="job-toggle-switch cursor-pointer"
                                  onClick={() => handleToggleActive(mapping.id, mapping.active)}
                                >
                                  <div className={`toggle-switch ${mapping.active ? 'active' : ''}`}>
                                    <div className="toggle-slider"></div>
                                  </div>
                                  <span className="toggle-label">{mapping.active ? 'On' : 'Off'}</span>
                                </div>
                              </td>
                              <td className="px-6 py-5 whitespace-nowrap text-center">
                                <div className="flex items-center justify-center space-x-2">
                                  <button
                                    onClick={() => handleEdit(mapping.id)}
                                    className="p-2 rounded bg-tertiary text-secondary hover:bg-secondary hover:text-accent shadow-sm hover:shadow-md transition-all"
                                    title="Edit"
                                  >
                                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                                      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                                    </svg>
                                  </button>
                                  <button
                                    onClick={() => handleDelete(mapping.id)}
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

      {/* Dependency Modal */}
      <DependencyModal
        isOpen={dependencyModal.isOpen}
        onClose={() => setDependencyModal(prev => ({ ...prev, isOpen: false }))}
        onConfirm={(_targetId) => performToggle(dependencyModal.mappingId!, dependencyModal.action === 'activate')}
        title={`${dependencyModal.action === 'deactivate' ? 'Deactivate' : 'Activate'} Status Mapping`}
        itemName={dependencyModal.mappingName}
        action={dependencyModal.action}
        dependencyCount={dependencyModal.dependencies.length}
        affectedItemsCount={dependencyModal.dependencies.reduce((sum: number, dep: any) => sum + (dep.affected_items_count || 0), 0)}
        dependencyType="status mapping(s)"
        affectedItemType="work item(s)"
        reassignmentTargets={dependencyModal.reassignmentTargets}
        targetDisplayField="status_to"
        allowSkipReassignment={dependencyModal.action === 'deactivate'}
        onShowError={showError}
      />

      {/* Edit Modal */}
      {editModal.mapping && (
        <EditModal
          isOpen={editModal.isOpen}
          onClose={() => setEditModal({ isOpen: false, mapping: null })}
          onSave={handleEditSave}
          title="Edit Status Mapping"
          fields={[
            {
              name: 'status_from',
              label: 'Source Status',
              type: 'text',
              value: editModal.mapping.status_from,
              required: true,
              placeholder: 'Enter source status'
            },
            {
              name: 'status_to',
              label: 'Target Status',
              type: 'text',
              value: editModal.mapping.status_to,
              required: true,
              placeholder: 'Enter target status'
            },
            {
              name: 'status_category',
              label: 'Status Category',
              type: 'select',
              value: editModal.mapping.status_category || '',
              required: true,
              options: [
                { value: 'To Do', label: 'To Do' },
                { value: 'In Progress', label: 'In Progress' },
                { value: 'Done', label: 'Done' },
                { value: 'Blocked', label: 'Blocked' }
              ]
            },
            {
              name: 'workflow_id',
              label: 'Workflow',
              type: 'select',
              value: editModal.mapping.workflow_id || '',
              options: [
                { value: '', label: 'No Workflow' },
                // TODO: Load actual workflows
                { value: '1', label: 'Development Workflow' },
                { value: '2', label: 'Support Workflow' }
              ]
            },
            {
              name: 'integration_id',
              label: 'Integration',
              type: 'select',
              value: editModal.mapping.integration_id || '',
              required: true,
              options: integrations.map(integration => ({
                value: integration.id.toString(),
                label: integration.name
              })),
              customRender: (field: any, formData: any, handleInputChange: any, errors: any) => {
                const selectedIntegrationId = formData[field.name] || field.value
                const selectedIntegration = integrations.find(i => i.id.toString() === selectedIntegrationId?.toString())

                return (
                  <div className="space-y-3">
                    <select
                      id={field.name}
                      value={formData[field.name] || field.value || ''}
                      onChange={(e) => handleInputChange(field.name, e.target.value)}
                      className={`input w-full ${errors[field.name] ? 'border-red-500' : ''}`}
                    >
                      <option value="">Select {field.label}</option>
                      {field.options?.map((option: any) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                    {selectedIntegration && (
                      <div className="flex items-center space-x-3 p-3 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg">
                        {selectedIntegration.logo_filename ? (
                          <img
                            src={`/assets/integrations/${selectedIntegration.logo_filename}`}
                            alt={selectedIntegration.name}
                            className="h-8 w-8 object-contain"
                            onError={(e) => {
                              e.currentTarget.style.display = 'none';
                            }}
                          />
                        ) : (
                          <div className="h-8 w-8 bg-blue-100 rounded-lg flex items-center justify-center">
                            <span className="text-sm text-blue-600 font-semibold">
                              {selectedIntegration.name.charAt(0)}
                            </span>
                          </div>
                        )}
                        <div>
                          <p className="text-sm font-medium text-gray-900">{selectedIntegration.name}</p>
                          <p className="text-xs text-gray-500">Integration Provider</p>
                        </div>
                      </div>
                    )}
                  </div>
                )
              }
            }
          ]}
        />
      )}

      {/* Create Modal */}
      <CreateModal
        isOpen={createModal.isOpen}
        onClose={() => setCreateModal({ isOpen: false })}
        onSave={handleCreateSave}
        title="Create Status Mapping"
        fields={[
          {
            name: 'status_from',
            label: 'Source Status',
            type: 'text',
            required: true,
            placeholder: 'Enter source status'
          },
          {
            name: 'status_to',
            label: 'Target Status',
            type: 'text',
            required: true,
            placeholder: 'Enter target status'
          },
          {
            name: 'status_category',
            label: 'Status Category',
            type: 'select',
            required: true,
            defaultValue: 'To Do',
            options: [
              { value: 'To Do', label: 'To Do' },
              { value: 'In Progress', label: 'In Progress' },
              { value: 'Done', label: 'Done' },
              { value: 'Blocked', label: 'Blocked' }
            ]
          },
          {
            name: 'workflow_id',
            label: 'Workflow',
            type: 'select',
            options: [
              { value: '', label: 'No Workflow' },
              // TODO: Load actual workflows
              { value: '1', label: 'Development Workflow' },
              { value: '2', label: 'Support Workflow' }
            ]
          },
          {
            name: 'integration_id',
            label: 'Integration',
            type: 'select',
            required: true,
            defaultValue: integrations.length > 0 ? integrations[0].id.toString() : '',
            options: integrations.map(integration => ({
              value: integration.id.toString(),
              label: integration.name
            })),
            customRender: (field: any, formData: any, handleInputChange: any, errors: any) => {
              const selectedIntegrationId = formData[field.name] || field.defaultValue
              const selectedIntegration = integrations.find(i => i.id.toString() === selectedIntegrationId)

              return (
                <div className="space-y-3">
                  <select
                    id={field.name}
                    value={formData[field.name] || ''}
                    onChange={(e) => handleInputChange(field.name, e.target.value)}
                    className={`input w-full ${errors[field.name] ? 'border-red-500' : ''}`}
                  >
                    {field.options?.map((option: any) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                  {selectedIntegration && (
                    <div className="flex items-center space-x-3 p-3 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg">
                      {selectedIntegration.logo_filename ? (
                        <img
                          src={`/assets/integrations/${selectedIntegration.logo_filename}`}
                          alt={selectedIntegration.name}
                          className="h-8 w-8 object-contain"
                          onError={(e) => {
                            e.currentTarget.style.display = 'none';
                          }}
                        />
                      ) : (
                        <div className="h-8 w-8 bg-blue-100 rounded-lg flex items-center justify-center">
                          <span className="text-sm text-blue-600 font-semibold">
                            {selectedIntegration.name.charAt(0)}
                          </span>
                        </div>
                      )}
                      <div>
                        <p className="text-sm font-medium text-gray-900">{selectedIntegration.name}</p>
                        <p className="text-xs text-gray-500">Integration Provider</p>
                      </div>
                    </div>
                  )}
                </div>
              )
            }
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

      {/* Toast Notifications - Always show, even in embedded mode */}
      <ToastContainer toasts={toasts} onRemoveToast={removeToast} />
    </>
  )

  if (embedded) {
    return content
  }

  return (
    <div className="min-h-screen">
      <Header />
      <div className="flex">
        <CollapsedSidebar />
        <main className="flex-1 ml-16 py-8">
          <div className="ml-12 mr-12">
            {content}
          </div>
        </main>
      </div>
    </div>
  )
}

export default StatusesMappingsPage
