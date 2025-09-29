import React, { useState, useEffect } from 'react'
import Header from '../components/Header'
import CollapsedSidebar from '../components/CollapsedSidebar'
import DependencyModal from '../components/DependencyModal'
import ConfirmationModal from '../components/ConfirmationModal'
import EditModal from '../components/EditModal'
import CreateModal from '../components/CreateModal'
import ToastContainer from '../components/ToastContainer'
import { useToast } from '../hooks/useToast'
import { useConfirmation } from '../hooks/useConfirmation'
import { statusesApi } from '../services/etlApiService'

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

const StatusesMappingsPage: React.FC = () => {
  const [mappings, setMappings] = useState<StatusMapping[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { toasts, removeToast, showSuccess, showError, showWarning } = useToast()
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
      // TODO: Implement actual API call
      console.log(`Toggle status mapping ${mappingId} to ${newActiveState}`)

      // Update local state
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

      await statusesApi.updateStatusMapping(editModal.mapping.id, updateData)

      // Update local state
      setMappings(prev => prev.map(m =>
        m.id === editModal.mapping!.id
          ? { ...m, ...updateData }
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

      // Add new mapping to local state
      setMappings(prev => [...prev, response.data])

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

  useEffect(() => {
    const fetchMappings = async () => {
      try {
        setLoading(true)
        const response = await statusesApi.getStatusMappings()
        setMappings(response.data)
        setError(null)
      } catch (err) {
        console.error('Error fetching status mappings:', err)
        setError('Failed to load status mappings')
      } finally {
        setLoading(false)
      }
    }

    fetchMappings()
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
                    Status Mappings
                  </h1>
                  <p className="text-lg text-secondary">
                    Manage status mappings between integrations
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
                    Fetching status mappings
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
              ) : mappings.length === 0 ? (
                <div className="text-center py-12">
                  <div className="text-6xl mb-4">📝</div>
                  <h2 className="text-2xl font-semibold text-primary mb-2">
                    No Mappings Found
                  </h2>
                  <p className="text-secondary">
                    No status mappings have been configured yet.
                  </p>
                </div>
              ) : (
                <>
                  {/* Filters Section */}
                  <div className="mb-6 p-4 rounded-lg bg-secondary border border-tertiary/20">
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
                  <div className="rounded-lg overflow-hidden bg-secondary border border-tertiary/20">
                    <div className="px-6 py-4 border-b border-tertiary/20 bg-tertiary/10 flex justify-between items-center">
                      <h2 className="text-lg font-semibold text-primary">Status Mappings</h2>
                      <button
                        onClick={() => setCreateModal({ isOpen: true })}
                        className="px-4 py-2 bg-accent text-on-accent rounded-lg hover:bg-accent/90 transition-colors flex items-center space-x-2"
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
                        <thead className="bg-tertiary/10">
                          <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-secondary">From Status</th>
                            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-secondary">To Status</th>
                            <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-secondary">Category</th>
                            <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-secondary">Workflow Step</th>
                            <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-secondary">Integration</th>
                            <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-secondary">Active</th>
                            <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-secondary">Actions</th>
                          </tr>
                        </thead>
                        <tbody className="bg-secondary">
                          {filteredMappings.map((mapping) => (
                            <tr key={mapping.id} className="border-b hover:bg-gray-50" style={{borderColor: 'var(--border-color)'}}>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-primary font-medium">{mapping.status_from}</td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-primary">{mapping.status_to}</td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-center text-primary">{mapping.status_category || '-'}</td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-center text-primary">{mapping.workflow_step_name || '-'}</td>
                              <td className="px-6 py-4 whitespace-nowrap text-center">
                                <div className="flex items-center justify-center">
                                  {mapping.integration_logo ? (
                                    <img
                                      src={`/assets/integrations/${mapping.integration_logo}`}
                                      alt={mapping.integration_name}
                                      className="h-6 w-auto max-w-16 object-contain"
                                      onError={(e) => {
                                        e.currentTarget.style.display = 'none';
                                        if (e.currentTarget.nextElementSibling) {
                                          (e.currentTarget.nextElementSibling as HTMLElement).style.display = 'inline';
                                        }
                                      }}
                                    />
                                  ) : null}
                                  <span className="text-sm text-primary" style={{ display: mapping.integration_logo ? 'none' : 'inline' }}>
                                    {mapping.integration_name || '-'}
                                  </span>
                                </div>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-center">
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
                              <td className="px-6 py-4 whitespace-nowrap text-center">
                                <div className="flex items-center justify-center space-x-2">
                                  <button
                                    onClick={() => handleEdit(mapping.id)}
                                    className="p-2 bg-tertiary border border-tertiary/20 rounded-lg text-secondary hover:bg-primary hover:text-primary transition-colors"
                                    title="Edit"
                                  >
                                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                                      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                                    </svg>
                                  </button>
                                  <button
                                    onClick={() => handleDelete(mapping.id)}
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

      {/* Dependency Modal */}
      <DependencyModal
        isOpen={dependencyModal.isOpen}
        onClose={() => setDependencyModal(prev => ({ ...prev, isOpen: false }))}
        onConfirm={(targetId) => performToggle(dependencyModal.mappingId!, dependencyModal.action === 'activate')}
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
              options: [
                { value: '', label: 'No Integration' },
                // TODO: Load actual integrations
                { value: '1', label: 'Jira' },
                { value: '2', label: 'GitHub' }
              ]
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
            options: [
              { value: '', label: 'No Integration' },
              // TODO: Load actual integrations
              { value: '1', label: 'Jira' },
              { value: '2', label: 'GitHub' }
            ]
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

export default StatusesMappingsPage
