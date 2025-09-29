import React, { useState, useEffect } from 'react'
import Header from '../components/Header'
import CollapsedSidebar from '../components/CollapsedSidebar'
import DependencyModal from '../components/DependencyModal'
import ConfirmationModal from '../components/ConfirmationModal'
import EditModal from '../components/EditModal'
import ToastContainer from '../components/ToastContainer'
import { useToast } from '../hooks/useToast'
import { useConfirmation } from '../hooks/useConfirmation'
import { witsApi } from '../services/etlApiService'

interface WitMapping {
  id: number
  wit_from: string
  wit_to: string
  hierarchy_level?: number
  integration_id?: number
  integration_name?: string
  integration_logo?: string
  active: boolean
}

const WitsMappingsPage: React.FC = () => {
  const [mappings, setMappings] = useState<WitMapping[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { toasts, removeToast, showSuccess, showError, showWarning } = useToast()
  const { confirmation, confirmDelete, hideConfirmation } = useConfirmation()

  // Filter states
  const [sourceTypeFilter, setSourceTypeFilter] = useState('')
  const [targetTypeFilter, setTargetTypeFilter] = useState('')
  const [hierarchyLevelFilter, setHierarchyLevelFilter] = useState('')
  const [integrationFilter, setIntegrationFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  // Edit modal state
  const [editModal, setEditModal] = useState({
    isOpen: false,
    mapping: null as WitMapping | null
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
      // For now, return mock data
      return {
        has_dependencies: Math.random() > 0.7, // 30% chance of having dependencies
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
            mappingName: `${mapping.wit_from} → ${mapping.wit_to}`,
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
      console.log(`Toggle mapping ${mappingId} to ${newActiveState}`)

      // Update local state
      setMappings(prev => prev.map(mapping =>
        mapping.id === mappingId
          ? { ...mapping, active: newActiveState }
          : mapping
      ))

      setDependencyModal(prev => ({ ...prev, isOpen: false }))
      showSuccess(
        `Mapping ${newActiveState ? 'Activated' : 'Deactivated'}`,
        `The mapping has been ${newActiveState ? 'activated' : 'deactivated'} successfully.`
      )
    } catch (error) {
      console.error('Error updating mapping:', error)
      showError('Update Failed', 'Failed to update mapping status. Please try again.')
    }
  }

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
        wit_from: formData.wit_from,
        wit_to: formData.wit_to,
        hierarchy_level: parseInt(formData.hierarchy_level),
        integration_id: formData.integration_id ? parseInt(formData.integration_id) : null
      }

      await witsApi.updateWitMapping(editModal.mapping.id, updateData)

      // Update local state
      setMappings(prev => prev.map(m =>
        m.id === editModal.mapping!.id
          ? { ...m, ...updateData }
          : m
      ))

      showSuccess('Mapping Updated', 'The mapping has been updated successfully.')
      setEditModal({ isOpen: false, mapping: null })
    } catch (error) {
      console.error('Error updating mapping:', error)
      showError('Update Failed', 'Failed to update mapping. Please try again.')
    }
  }

  const handleDelete = async (mappingId: number) => {
    const mapping = mappings.find(m => m.id === mappingId)
    if (!mapping) return

    confirmDelete(
      `${mapping.wit_from} → ${mapping.wit_to}`,
      async () => {
        try {
          // TODO: Implement delete functionality
          console.log(`Delete mapping ${mappingId}`)
          showWarning('Feature Coming Soon', 'Delete functionality will be implemented soon.')
        } catch (error) {
          console.error('Error deleting mapping:', error)
          showError('Delete Failed', 'Failed to delete mapping. Please try again.')
        }
      }
    )
  }

  const handleCreateMapping = () => {
    // TODO: Implement create mapping functionality
    console.log('Create new mapping')
    showWarning('Feature Coming Soon', 'Create mapping functionality will be implemented soon.')
  }

  const handleVectorizationDetails = () => {
    // TODO: Implement vectorization details functionality
    console.log('Show vectorization details')
    showWarning('Feature Coming Soon', 'Vectorization details will be implemented soon.')
  }

  const handleVectorizationExecute = () => {
    // TODO: Implement vectorization execute functionality
    console.log('Execute vectorization')
    showWarning('Feature Coming Soon', 'Vectorization execution will be implemented soon.')
  }

  // Filtered mappings based on filter states
  const filteredMappings = mappings.filter(mapping => {
    const matchesSourceType = !sourceTypeFilter ||
      mapping.wit_from.toLowerCase().includes(sourceTypeFilter.toLowerCase())
    const matchesTargetType = !targetTypeFilter ||
      mapping.wit_to.toLowerCase().includes(targetTypeFilter.toLowerCase())
    const matchesHierarchyLevel = !hierarchyLevelFilter ||
      (mapping.hierarchy_level !== null && mapping.hierarchy_level !== undefined &&
       mapping.hierarchy_level.toString() === hierarchyLevelFilter)
    const matchesIntegration = !integrationFilter ||
      (mapping.integration_name && mapping.integration_name.toLowerCase().includes(integrationFilter.toLowerCase()))
    const matchesStatus = !statusFilter ||
      (statusFilter === 'active' && mapping.active) ||
      (statusFilter === 'inactive' && !mapping.active)

    return matchesSourceType && matchesTargetType && matchesHierarchyLevel && matchesIntegration && matchesStatus
  })

  useEffect(() => {
    const fetchMappings = async () => {
      try {
        setLoading(true)
        const response = await witsApi.getWitMappings()
        setMappings(response.data)
        setError(null)
      } catch (err) {
        console.error('Error fetching WIT mappings:', err)
        setError('Failed to load work item type mappings')
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
                    Work Item Type Mappings
                  </h1>
                  <p className="text-lg text-secondary">
                    Manage work item type mappings between integrations
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
                  <button
                    onClick={handleVectorizationDetails}
                    className="px-3 py-1.5 text-xs rounded-md border border-tertiary/20 text-secondary bg-primary hover:bg-tertiary transition-colors"
                  >
                    Details
                  </button>
                  <button
                    onClick={handleVectorizationExecute}
                    className="px-3 py-1.5 text-xs rounded-md text-white bg-blue-500 hover:bg-blue-600 transition-colors"
                  >
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
                    Fetching work item type mappings
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
                    No work item type mappings have been configured yet.
                  </p>
                </div>
              ) : (
                <>
                  {/* Filters Section */}
                  <div className="mb-6 p-4 rounded-lg bg-secondary border border-tertiary/20">
                    <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
                      {/* From Filter */}
                      <div>
                        <label className="block text-sm font-medium mb-2 text-primary">From</label>
                        <input
                          type="text"
                          placeholder="Filter by from..."
                          value={sourceTypeFilter}
                          onChange={(e) => setSourceTypeFilter(e.target.value)}
                          className="w-full px-3 py-2 border border-tertiary/20 rounded-lg bg-primary text-primary"
                        />
                      </div>

                      {/* To Filter */}
                      <div>
                        <label className="block text-sm font-medium mb-2 text-primary">To</label>
                        <input
                          type="text"
                          placeholder="Filter by to..."
                          value={targetTypeFilter}
                          onChange={(e) => setTargetTypeFilter(e.target.value)}
                          className="w-full px-3 py-2 border border-tertiary/20 rounded-lg bg-primary text-primary"
                        />
                      </div>

                      {/* Hierarchy Level Filter */}
                      <div>
                        <label className="block text-sm font-medium mb-2 text-primary">Hierarchy Level</label>
                        <select
                          value={hierarchyLevelFilter}
                          onChange={(e) => setHierarchyLevelFilter(e.target.value)}
                          className="w-full px-3 py-2 border border-tertiary/20 rounded-lg bg-primary text-primary"
                        >
                          <option value="">All Levels</option>
                          <option value="4">Level 4 (Capital Investment)</option>
                          <option value="3">Level 3 (Product Objective)</option>
                          <option value="2">Level 2 (Milestone)</option>
                          <option value="1">Level 1 (Epic)</option>
                          <option value="0">Level 0 (Story/Task/Bug)</option>
                          <option value="-1">Level -1 (Sub-task)</option>
                        </select>
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

                  {/* Work Item Type Mappings Table */}
                  <div className="rounded-lg overflow-hidden bg-secondary border border-tertiary/20">
                  <div className="px-6 py-4 border-b border-tertiary/20 bg-tertiary/10 flex justify-between items-center">
                    <h2 className="text-lg font-semibold text-primary">Work Item Type Mappings</h2>
                    <button
                      onClick={handleCreateMapping}
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
                      <thead style={{backgroundColor: 'var(--bg-tertiary)'}}>
                        <tr>
                          <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-secondary">From</th>
                          <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-secondary">To</th>
                          <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-secondary">Hierarchy Level</th>
                          <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-secondary">Integration</th>
                          <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-secondary">Active</th>
                          <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-secondary">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="bg-secondary">
                        {filteredMappings.length > 0 ? (
                          filteredMappings.map((mapping) => (
                            <tr key={mapping.id} className="border-b hover:bg-gray-50" style={{borderColor: 'var(--border-color)'}}>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-primary">{mapping.wit_from}</td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-primary">{mapping.wit_to}</td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-center text-primary">{mapping.hierarchy_level}</td>
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
                              <td className="px-6 py-4 whitespace-nowrap text-center text-sm font-medium">
                                <div className="flex justify-center space-x-1">
                                  <button
                                    onClick={() => handleEdit(mapping.id)}
                                    className="p-1.5 bg-tertiary border border-tertiary/20 rounded text-secondary hover:bg-primary hover:text-primary transition-all"
                                    aria-label="Edit mapping"
                                  >
                                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                                      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                                    </svg>
                                  </button>
                                  <button
                                    onClick={() => handleDelete(mapping.id)}
                                    className="p-1.5 bg-tertiary border border-tertiary/20 rounded text-secondary hover:bg-red-500 hover:text-white transition-all"
                                    aria-label="Delete mapping"
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
                          ))
                        ) : (
                          <tr>
                            <td colSpan={6} className="px-6 py-12 text-center">
                              <div className="flex flex-col items-center justify-center space-y-3">
                                <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" className="text-tertiary">
                                  <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"></path>
                                </svg>
                                <div className="text-secondary">
                                  <p className="text-lg font-medium">No mappings match your filters</p>
                                  <p className="text-sm text-tertiary mt-1">Try adjusting your filter criteria to see more results</p>
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
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
        title={`${dependencyModal.action === 'deactivate' ? 'Deactivate' : 'Activate'} WIT Mapping`}
        itemName={dependencyModal.mappingName}
        action={dependencyModal.action}
        dependencyCount={dependencyModal.dependencies.length}
        affectedItemsCount={dependencyModal.dependencies.reduce((sum: number, dep: any) => sum + (dep.affected_items_count || 0), 0)}
        dependencyType="work item(s)"
        affectedItemType="work item(s)"
        reassignmentTargets={dependencyModal.reassignmentTargets}
        targetDisplayField="wit_to"
        allowSkipReassignment={dependencyModal.action === 'deactivate'}
        onShowError={showError}
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

      {/* Edit Modal */}
      {editModal.mapping && (
        <EditModal
          isOpen={editModal.isOpen}
          onClose={() => setEditModal({ isOpen: false, mapping: null })}
          onSave={handleEditSave}
          title="Edit Mapping"
          fields={[
            {
              name: 'wit_from',
              label: 'Source Type',
              type: 'text',
              value: editModal.mapping.wit_from,
              required: true,
              placeholder: 'Enter source work item type'
            },
            {
              name: 'wit_to',
              label: 'Target Type',
              type: 'text',
              value: editModal.mapping.wit_to,
              required: true,
              placeholder: 'Enter target work item type'
            },
            {
              name: 'hierarchy_level',
              label: 'Hierarchy Level',
              type: 'number',
              value: editModal.mapping.hierarchy_level,
              required: true,
              placeholder: 'Enter hierarchy level'
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

      {/* Toast Notifications */}
      <ToastContainer toasts={toasts} onRemoveToast={removeToast} />
    </div>
  )
}

export default WitsMappingsPage
