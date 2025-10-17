import React, { useState, useEffect } from 'react'
import { Loader2 } from 'lucide-react'
import Header from '../components/Header'
import CollapsedSidebar from '../components/CollapsedSidebar'
import DependencyModal from '../components/DependencyModal'
import EditModal from '../components/EditModal'
import CreateModal from '../components/CreateModal'
import ToastContainer from '../components/ToastContainer'
import IntegrationLogo from '../components/IntegrationLogo'
import { useToast } from '../hooks/useToast'
import { witsApi, integrationsApi } from '../services/etlApiService'

interface WitHierarchy {
  id: number
  level_number: number
  level_name: string
  description?: string
  integration_id?: number
  integration_name?: string
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

interface WitsHierarchiesPageProps {
  embedded?: boolean
}

const WitsHierarchiesPage: React.FC<WitsHierarchiesPageProps> = ({ embedded = false }) => {
  const [hierarchies, setHierarchies] = useState<WitHierarchy[]>([])
  const [integrations, setIntegrations] = useState<Integration[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [queueing, setQueueing] = useState(false)
  const { toasts, removeToast, showSuccess, showError } = useToast()

  // Edit modal state
  const [editModal, setEditModal] = useState({
    isOpen: false,
    hierarchy: null as WitHierarchy | null
  })

  // Create modal state
  const [createModal, setCreateModal] = useState({
    isOpen: false
  })

  // Dependency modal state
  const [dependencyModal, setDependencyModal] = useState<{
    isOpen: boolean;
    action: 'delete' | 'deactivate';
    hierarchyId: number;
    hierarchyName: string;
    dependencies: any;
  }>({
    isOpen: false,
    action: 'delete',
    hierarchyId: 0,
    hierarchyName: '',
    dependencies: null
  })

  // Filter states
  const [levelNumberFilter, setLevelNumberFilter] = useState('')
  const [levelNameFilter, setLevelNameFilter] = useState('')
  const [integrationFilter, setIntegrationFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  // Filtered hierarchies based on filter states
  const filteredHierarchies = hierarchies.filter(hierarchy => {
    const matchesLevelNumber = !levelNumberFilter ||
      hierarchy.level_number.toString().includes(levelNumberFilter)
    const matchesLevelName = !levelNameFilter ||
      hierarchy.level_name.toLowerCase().includes(levelNameFilter.toLowerCase())
    const matchesIntegration = !integrationFilter ||
      (hierarchy.integration_name && hierarchy.integration_name.toLowerCase().includes(integrationFilter.toLowerCase()))
    // Status filter: if no filter selected, show all items (both active and inactive)
    const matchesStatus = !statusFilter ||
      (statusFilter === 'active' && hierarchy.active) ||
      (statusFilter === 'inactive' && !hierarchy.active)

    return matchesLevelNumber && matchesLevelName && matchesIntegration && matchesStatus
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
        // Load both hierarchies and integrations in parallel
        await Promise.all([
          (async () => {
            const response = await witsApi.getWitsHierarchies()
            setHierarchies(response.data)
          })(),
          loadIntegrations()
        ])
        setError(null)
      } catch (err) {
        console.error('Error fetching data:', err)
        setError('Failed to load work item type hierarchies')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [])

  // Toggle active status
  const handleToggleActive = async (hierarchyId: number, currentActive: boolean) => {
    if (currentActive) {
      // Deactivating - check for dependencies
      await checkDependencies(hierarchyId, 'deactivate')
    } else {
      // Activating - no dependency check needed
      await performActivate(hierarchyId)
    }
  }

  const performActivate = async (hierarchyId: number) => {
    try {
      const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001'
      const response = await fetch(`${API_BASE_URL}/app/etl/wits-hierarchies/${hierarchyId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('pulse_token')}`
        },
        body: JSON.stringify({ active: true })
      })

      if (!response.ok) {
        throw new Error('Failed to activate hierarchy')
      }

      // Update local state
      setHierarchies(prev => prev.map(hierarchy =>
        hierarchy.id === hierarchyId
          ? { ...hierarchy, active: true }
          : hierarchy
      ))

      showSuccess('Hierarchy Activated', 'The hierarchy has been activated successfully.')
    } catch (err) {
      console.error('Error activating hierarchy:', err)
      showError('Activation Failed', 'Failed to activate hierarchy. Please try again.')
    }
  }

  // Handle edit
  const handleEdit = (hierarchyId: number) => {
    const hierarchy = hierarchies.find(h => h.id === hierarchyId)
    if (hierarchy) {
      setEditModal({
        isOpen: true,
        hierarchy
      })
    }
  }

  // Handle edit save
  const handleEditSave = async (formData: Record<string, any>) => {
    if (!editModal.hierarchy) return

    try {
      const updateData = {
        level_name: formData.level_name,
        level_number: parseInt(formData.level_number),
        description: formData.description || null,
        integration_id: formData.integration_id ? parseInt(formData.integration_id) : null
      }

      const response = await witsApi.updateWitHierarchy(editModal.hierarchy.id, updateData)

      // Get integration info from the frontend state (already loaded)
      const selectedIntegration = integrations.find(i => i.id === updateData.integration_id)

      // Update local state with response data plus integration info from frontend
      const updatedHierarchy = {
        ...(response.data || response),
        integration_name: selectedIntegration?.name || null,
        integration_logo: selectedIntegration?.logo_filename || null
      }

      setHierarchies(prev => prev.map(h =>
        h.id === editModal.hierarchy!.id
          ? updatedHierarchy
          : h
      ))

      showSuccess('Hierarchy Updated', 'The hierarchy has been updated successfully.')
      setEditModal({ isOpen: false, hierarchy: null })
    } catch (error) {
      console.error('Error updating hierarchy:', error)
      showError('Update Failed', 'Failed to update hierarchy. Please try again.')
    }
  }

  // Handle create save
  const handleCreateSave = async (formData: Record<string, any>) => {
    try {
      const createData = {
        level_name: formData.level_name,
        level_number: parseInt(formData.level_number),
        description: formData.description || null,
        integration_id: formData.integration_id ? parseInt(formData.integration_id) : null
      }

      const response = await witsApi.createWitHierarchy(createData)

      // Get integration info from the frontend state (already loaded)
      const selectedIntegration = integrations.find(i => i.id === createData.integration_id)

      // Add new hierarchy to local state with integration info from frontend
      const newHierarchy = {
        ...(response.data || response),
        integration_name: selectedIntegration?.name || null,
        integration_logo: selectedIntegration?.logo_filename || null
      }

      setHierarchies(prev => [...prev, newHierarchy])

      showSuccess('Hierarchy Created', 'The hierarchy has been created successfully.')
      setCreateModal({ isOpen: false })
    } catch (error) {
      console.error('Error creating hierarchy:', error)
      showError('Create Failed', 'Failed to create hierarchy. Please try again.')
    }
  }

  // Handle delete
  const checkDependencies = async (hierarchyId: number, action: 'delete' | 'deactivate') => {
    try {
      const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001'
      const response = await fetch(`${API_BASE_URL}/app/etl/wits-hierarchies/${hierarchyId}/dependencies`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('pulse_token')}`
        }
      })

      if (!response.ok) {
        throw new Error('Failed to check dependencies')
      }

      const dependencies = await response.json()
      const hierarchy = hierarchies.find(h => h.id === hierarchyId)

      if (!dependencies.has_dependencies) {
        // No dependencies, proceed directly
        if (action === 'delete') {
          await performDelete(hierarchyId)
        } else {
          await performDeactivate(hierarchyId)
        }
      } else {
        // Show dependency modal
        setDependencyModal({
          isOpen: true,
          action,
          hierarchyId,
          hierarchyName: hierarchy?.level_name || 'Unknown',
          dependencies
        })
      }
    } catch (err) {
      console.error('Error checking dependencies:', err)
      showError('Dependency Check Failed', 'Failed to check dependencies. Please try again.')
    }
  }

  const handleDelete = async (hierarchyId: number) => {
    await checkDependencies(hierarchyId, 'delete')
  }

  const performDelete = async (hierarchyId: number, targetId?: number) => {
    try {
      const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001'
      const response = await fetch(`${API_BASE_URL}/app/etl/wits-hierarchies/${hierarchyId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('pulse_token')}`,
          'Content-Type': 'application/json'
        },
        body: targetId ? JSON.stringify({ target_hierarchy_id: targetId }) : undefined
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to delete hierarchy' }))
        throw new Error(errorData.detail || 'Failed to delete hierarchy')
      }

      // Update local state only after successful API call
      setHierarchies(prev => prev.filter(hierarchy => hierarchy.id !== hierarchyId))
      setDependencyModal(prev => ({ ...prev, isOpen: false }))
      showSuccess('Hierarchy Deleted', 'The hierarchy has been deleted successfully.')
    } catch (err) {
      console.error('Error deleting hierarchy:', err)
      showError('Deletion Failed', err instanceof Error ? err.message : 'Failed to delete hierarchy. Please try again.')
    }
  }

  const performDeactivate = async (hierarchyId: number, targetId?: number) => {
    try {
      const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001'
      const response = await fetch(`${API_BASE_URL}/app/etl/wits-hierarchies/${hierarchyId}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('pulse_token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          active: false,
          target_hierarchy_id: targetId
        })
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to deactivate hierarchy' }))
        throw new Error(errorData.detail || 'Failed to deactivate hierarchy')
      }

      // Update local state
      setHierarchies(prev => prev.map(hierarchy =>
        hierarchy.id === hierarchyId
          ? { ...hierarchy, active: false }
          : hierarchy
      ))
      setDependencyModal(prev => ({ ...prev, isOpen: false }))
      showSuccess('Hierarchy Deactivated', 'The hierarchy has been deactivated successfully.')
    } catch (err) {
      console.error('Error deactivating hierarchy:', err)
      showError('Deactivation Failed', err instanceof Error ? err.message : 'Failed to deactivate hierarchy. Please try again.')
    }
  }

  // Queue all hierarchies for embedding
  const handleQueueForEmbedding = async () => {
    try {
      setQueueing(true)
      const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001'
      const response = await fetch(`${API_BASE_URL}/app/etl/embedding/queue-table`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('pulse_token')}`
        },
        body: JSON.stringify({
          table_name: 'wits_hierarchies'
        })
      })

      if (!response.ok) {
        throw new Error('Failed to queue embedding')
      }

      const result = await response.json()
      showSuccess('Queued for Embedding', `${result.queued_count} hierarchies queued for embedding`)
    } catch (err) {
      console.error('Error queueing embedding:', err)
      showError('Queue Failed', 'Failed to queue hierarchies for embedding')
    } finally {
      setQueueing(false)
    }
  }

  const content = (
    <>

            {/* Queue for Embedding Button */}
            <div className="mb-6 flex justify-end">
              <button
                onClick={handleQueueForEmbedding}
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
                <span>{queueing ? 'Queueing...' : 'Queue for Embedding'}</span>
              </button>
            </div>

            {/* Content */}
            <div>
              {loading ? (
                <div className="text-center py-12">
                  <Loader2 className="h-12 w-12 animate-spin mx-auto mb-4 text-primary" />
                  <h2 className="text-2xl font-semibold text-primary mb-2">
                    Loading...
                  </h2>
                  <p className="text-secondary">
                    Fetching work item type hierarchies
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
              ) : hierarchies.length === 0 ? (
                <div className="text-center py-12">
                  <div className="text-6xl mb-4">📊</div>
                  <h2 className="text-2xl font-semibold text-primary mb-2">
                    No Hierarchies Found
                  </h2>
                  <p className="text-secondary">
                    No work item type hierarchies have been configured yet.
                  </p>
                </div>
              ) : (
                <>
                  {/* Filters Section */}
                  <div className="mb-6 p-6 rounded-lg shadow-md border border-gray-400"
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = 'var(--color-1)'
                      e.currentTarget.style.boxShadow = '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)'
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = '#9ca3af'
                      e.currentTarget.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
                    }}
                  >
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                      {/* Level Number Filter */}
                      <div>
                        <label className="block text-sm font-medium mb-2 text-primary">Level Number</label>
                        <input
                          type="number"
                          placeholder="Filter by level number..."
                          value={levelNumberFilter}
                          onChange={(e) => setLevelNumberFilter(e.target.value)}
                          className="w-full px-3 py-2 border border-tertiary/20 rounded-lg bg-primary text-primary"
                        />
                      </div>

                      {/* Level Name Filter */}
                      <div>
                        <label className="block text-sm font-medium mb-2 text-primary">Level Name</label>
                        <input
                          type="text"
                          placeholder="Filter by level name..."
                          value={levelNameFilter}
                          onChange={(e) => setLevelNameFilter(e.target.value)}
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

                  {/* WIT Hierarchies Table */}
                  <div className="rounded-lg bg-table-container shadow-md overflow-hidden border border-gray-400">
                    <div className="px-6 py-5 flex justify-between items-center bg-table-header">
                      <h2 className="text-lg font-semibold text-table-header">Work Item Type Hierarchies</h2>
                      <button
                        onClick={() => {
                          if (integrations.length === 0) {
                            showError('No Integrations Available', 'Please configure at least one data integration before creating hierarchies.')
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
                        <span>Create Hierarchy</span>
                      </button>
                    </div>

                    <div className="overflow-x-auto">
                      <table className="w-full">
                        <thead>
                          <tr className="bg-table-column-header">
                            <th className="px-6 py-4 text-center text-xs font-semibold uppercase tracking-wider text-table-column-header">Level</th>
                            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-table-column-header">Name</th>
                            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-table-column-header">Description</th>
                            <th className="px-6 py-4 text-center text-xs font-semibold uppercase tracking-wider text-table-column-header">Integration</th>
                            <th className="px-6 py-4 text-center text-xs font-semibold uppercase tracking-wider text-table-column-header">Active</th>
                            <th className="px-6 py-4 text-center text-xs font-semibold uppercase tracking-wider text-table-column-header">Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {filteredHierarchies.map((hierarchy, index) => (
                            <tr
                              key={hierarchy.id}
                              className={`${index % 2 === 0 ? 'bg-table-row-even' : 'bg-table-row-odd'} ${!hierarchy.active ? 'opacity-50' : ''}`}
                            >
                              <td className="px-6 py-5 whitespace-nowrap text-sm text-center text-table-row font-semibold">{hierarchy.level_number}</td>
                              <td className="px-6 py-5 whitespace-nowrap text-sm text-table-row font-semibold">{hierarchy.level_name}</td>
                              <td className="px-6 py-5 whitespace-nowrap text-sm text-table-row">{hierarchy.description || '-'}</td>
                              <td className="px-6 py-5 whitespace-nowrap text-center">
                                <div className="flex items-center justify-center">
                                  <IntegrationLogo
                                    logoFilename={hierarchy.integration_logo}
                                    integrationName={hierarchy.integration_name}
                                  />
                                  {!hierarchy.integration_logo && (
                                    <span className="text-sm text-table-row">
                                      {hierarchy.integration_name || '-'}
                                    </span>
                                  )}
                                </div>
                              </td>
                              <td className="px-6 py-5 whitespace-nowrap text-center">
                                <div className="job-toggle-switch" onClick={() => handleToggleActive(hierarchy.id, hierarchy.active)}>
                                  <div className={`toggle-switch ${hierarchy.active ? 'active' : ''}`}>
                                    <div className="toggle-slider"></div>
                                  </div>
                                  <span className="toggle-label">{hierarchy.active ? 'On' : 'Off'}</span>
                                </div>
                              </td>
                              <td className="px-6 py-5 whitespace-nowrap text-center">
                                <div className="flex items-center justify-center space-x-3">
                                  <button
                                    onClick={() => handleEdit(hierarchy.id)}
                                    className="p-2 rounded bg-tertiary text-secondary hover:bg-secondary hover:text-accent shadow-sm hover:shadow-md transition-all"
                                    aria-label="Edit hierarchy"
                                  >
                                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                                      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                                    </svg>
                                  </button>
                                  <button
                                    onClick={() => handleDelete(hierarchy.id)}
                                    className="p-2 rounded bg-tertiary text-secondary hover:bg-secondary hover:text-red-500 shadow-sm hover:shadow-md transition-all"
                                    aria-label="Delete hierarchy"
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

      {/* Dependency Modal */}
      <DependencyModal
        isOpen={dependencyModal.isOpen}
        onClose={() => setDependencyModal(prev => ({ ...prev, isOpen: false }))}
        onConfirm={(targetId) => {
          if (dependencyModal.action === 'delete') {
            performDelete(dependencyModal.hierarchyId, targetId)
          } else {
            performDeactivate(dependencyModal.hierarchyId, targetId)
          }
        }}
        title={dependencyModal.action === 'delete' ? 'Delete Hierarchy' : 'Deactivate Hierarchy'}
        itemName={dependencyModal.hierarchyName}
        action={dependencyModal.action}
        dependencyCount={dependencyModal.dependencies?.dependency_count || 0}
        affectedItemsCount={dependencyModal.dependencies?.affected_wits_count || 0}
        dependencyType="work item type mapping(s)"
        affectedItemType="work item(s)"
        reassignmentTargets={dependencyModal.dependencies?.reassignment_targets || []}
        targetDisplayField="level_name"
        allowSkipReassignment={dependencyModal.action === 'deactivate'}
        onShowError={showError}
      />

      {/* Edit Modal */}
      {editModal.hierarchy && (
        <EditModal
          isOpen={editModal.isOpen}
          onClose={() => setEditModal({ isOpen: false, hierarchy: null })}
          onSave={handleEditSave}
          title="Edit Hierarchy"
          fields={[
            {
              name: 'level_name',
              label: 'Level Name',
              type: 'text',
              value: editModal.hierarchy.level_name,
              required: true,
              placeholder: 'Enter level name'
            },
            {
              name: 'level_number',
              label: 'Level Number',
              type: 'number',
              value: editModal.hierarchy.level_number,
              required: true,
              placeholder: 'Enter level number'
            },
            {
              name: 'description',
              label: 'Description',
              type: 'textarea',
              value: editModal.hierarchy.description || '',
              placeholder: 'Enter description (optional)'
            },
            {
              name: 'integration_id',
              label: 'Integration',
              type: 'select',
              value: editModal.hierarchy.integration_id || '',
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
        title="Create Hierarchy"
        fields={[
          {
            name: 'level_name',
            label: 'Level Name',
            type: 'text',
            required: true,
            placeholder: 'Enter level name'
          },
          {
            name: 'level_number',
            label: 'Level Number',
            type: 'number',
            required: true,
            placeholder: 'Enter level number'
          },
          {
            name: 'description',
            label: 'Description',
            type: 'textarea',
            placeholder: 'Enter description (optional)'
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

export default WitsHierarchiesPage
