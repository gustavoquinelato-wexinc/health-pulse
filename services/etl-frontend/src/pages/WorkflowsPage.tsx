import React, { useState, useEffect } from 'react'
import Header from '../components/Header'
import CollapsedSidebar from '../components/CollapsedSidebar'
import DependencyModal from '../components/DependencyModal'
import EditModal from '../components/EditModal'
import ToastContainer from '../components/ToastContainer'
import { useToast } from '../hooks/useToast'
import { statusesApi } from '../services/etlApiService'

interface Workflow {
  id: number
  step_name: string
  step_number?: number
  step_category: string
  is_commitment_point: boolean
  integration_id?: number
  integration_name?: string
  integration_logo?: string
  active: boolean
}

const WorkflowsPage: React.FC = () => {
  const [workflows, setWorkflows] = useState<Workflow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { toasts, removeToast, showSuccess, showError, showWarning } = useToast()

  // Edit modal state
  const [editModal, setEditModal] = useState({
    isOpen: false,
    workflow: null as Workflow | null
  })

  // Dependency modal state
  const [dependencyModal, setDependencyModal] = useState({
    isOpen: false,
    workflowId: null as number | null,
    workflowName: '',
    action: 'deactivate' as 'deactivate' | 'activate',
    dependencies: [] as any[],
    reassignmentTargets: [] as any[]
  })

  // Handler functions
  const checkDependencies = async (workflowId: number): Promise<any> => {
    try {
      // TODO: Implement actual dependency checking API call
      return {
        has_dependencies: Math.random() > 0.7,
        dependency_count: Math.floor(Math.random() * 3) + 1,
        affected_items_count: Math.floor(Math.random() * 10) + 1,
        reassignment_targets: workflows.filter(w => w.id !== workflowId && w.active).slice(0, 3)
      }
    } catch (error) {
      console.error('Error checking dependencies:', error)
      throw new Error('Failed to check dependencies')
    }
  }

  const handleToggleActive = async (workflowId: number, currentActive: boolean) => {
    try {
      const workflow = workflows.find(w => w.id === workflowId)
      if (!workflow) return

      if (currentActive) {
        // Deactivating - check for dependencies
        const dependencyData = await checkDependencies(workflowId)

        if (dependencyData.has_dependencies) {
          setDependencyModal({
            isOpen: true,
            workflowId,
            workflowName: workflow.step_name,
            action: 'deactivate',
            dependencies: dependencyData.dependent_mappings || [],
            reassignmentTargets: dependencyData.reassignment_targets || []
          })
          return
        }
      }

      // No dependencies or activating - proceed directly
      await performToggle(workflowId, !currentActive)
    } catch (error) {
      console.error('Error toggling workflow:', error)
      showError('Toggle Failed', 'Failed to toggle workflow status. Please try again.')
    }
  }

  const performToggle = async (workflowId: number, newActiveState: boolean) => {
    try {
      // TODO: Implement actual API call
      console.log(`Toggle workflow ${workflowId} to ${newActiveState}`)

      // Update local state
      setWorkflows(prev => prev.map(workflow =>
        workflow.id === workflowId
          ? { ...workflow, active: newActiveState }
          : workflow
      ))

      setDependencyModal(prev => ({ ...prev, isOpen: false }))
      showSuccess(
        `Workflow ${newActiveState ? 'Activated' : 'Deactivated'}`,
        `The workflow has been ${newActiveState ? 'activated' : 'deactivated'} successfully.`
      )
    } catch (error) {
      console.error('Error updating workflow:', error)
      showError('Update Failed', 'Failed to update workflow status. Please try again.')
    }
  }

  // Handle edit
  const handleEdit = (workflowId: number) => {
    const workflow = workflows.find(w => w.id === workflowId)
    if (workflow) {
      setEditModal({
        isOpen: true,
        workflow
      })
    }
  }

  // Handle edit save
  const handleEditSave = async (formData: Record<string, any>) => {
    if (!editModal.workflow) return

    try {
      const updateData = {
        step_name: formData.step_name,
        step_number: formData.step_number ? parseInt(formData.step_number) : null,
        step_category: formData.step_category,
        is_commitment_point: formData.is_commitment_point || false,
        integration_id: formData.integration_id ? parseInt(formData.integration_id) : null
      }

      await statusesApi.updateWorkflow(editModal.workflow.id, updateData)

      // Update local state
      setWorkflows(prev => prev.map(w =>
        w.id === editModal.workflow!.id
          ? { ...w, ...updateData }
          : w
      ))

      showSuccess('Workflow Updated', 'The workflow has been updated successfully.')
      setEditModal({ isOpen: false, workflow: null })
    } catch (error) {
      console.error('Error updating workflow:', error)
      showError('Update Failed', 'Failed to update workflow. Please try again.')
    }
  }

  useEffect(() => {
    const fetchWorkflows = async () => {
      try {
        setLoading(true)
        const response = await statusesApi.getWorkflows()
        setWorkflows(response.data)
        setError(null)
      } catch (err) {
        console.error('Error fetching workflows:', err)
        setError('Failed to load workflows')
      } finally {
        setLoading(false)
      }
    }

    fetchWorkflows()
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
                    Workflows
                  </h1>
                  <p className="text-lg text-secondary">
                    Manage workflow configurations and transitions
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
                    Fetching workflows
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
              ) : workflows.length === 0 ? (
                <div className="text-center py-12">
                  <div className="text-6xl mb-4">⚡</div>
                  <h2 className="text-2xl font-semibold text-primary mb-2">
                    No Workflows Found
                  </h2>
                  <p className="text-secondary">
                    No workflows have been configured yet.
                  </p>
                </div>
              ) : (
                <>
                  {/* Filters Section */}
                  <div className="mb-6 p-4 rounded-lg bg-secondary border border-tertiary/20">
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                      {/* Workflow Name Filter */}
                      <div>
                        <label className="block text-sm font-medium mb-2 text-primary">Workflow Name</label>
                        <input
                          type="text"
                          placeholder="Filter by workflow name..."
                          className="w-full px-3 py-2 border border-tertiary/20 rounded-lg bg-primary text-primary"
                        />
                      </div>

                      {/* Description Filter */}
                      <div>
                        <label className="block text-sm font-medium mb-2 text-primary">Description</label>
                        <input
                          type="text"
                          placeholder="Filter by description..."
                          className="w-full px-3 py-2 border border-tertiary/20 rounded-lg bg-primary text-primary"
                        />
                      </div>

                      {/* Integration Filter */}
                      <div>
                        <label className="block text-sm font-medium mb-2 text-primary">Integration</label>
                        <select className="w-full px-3 py-2 border border-tertiary/20 rounded-lg bg-primary text-primary">
                          <option value="">All Integrations</option>
                          <option value="GitHub">GitHub</option>
                          <option value="Jira">Jira</option>
                        </select>
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
                    </div>
                  </div>

                  {/* Workflows Table */}
                  <div className="rounded-lg overflow-hidden bg-secondary border border-tertiary/20">
                    <div className="px-6 py-4 border-b border-tertiary/20 bg-tertiary/10 flex justify-between items-center">
                      <h2 className="text-lg font-semibold text-primary">Workflows</h2>
                      <button className="px-4 py-2 bg-accent text-on-accent rounded-lg hover:bg-accent/90 transition-colors flex items-center space-x-2">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M5 12h14"></path>
                          <path d="M12 5v14"></path>
                        </svg>
                        <span>Create Workflow</span>
                      </button>
                    </div>

                    <div className="overflow-x-auto">
                      <table className="w-full">
                        <thead className="bg-tertiary/10">
                          <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-secondary">Step Name</th>
                            <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-secondary">Step #</th>
                            <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-secondary">Category</th>
                            <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-secondary">Commitment Point</th>
                            <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-secondary">Integration</th>
                            <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-secondary">Active</th>
                            <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-secondary">Actions</th>
                          </tr>
                        </thead>
                        <tbody className="bg-secondary">
                          {workflows.map((workflow) => (
                            <tr key={workflow.id} className="border-b hover:bg-gray-50" style={{borderColor: 'var(--border-color)'}}>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-primary font-medium">{workflow.step_name}</td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-center text-primary">{workflow.step_number || '-'}</td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-center text-primary">{workflow.step_category}</td>
                              <td className="px-6 py-4 whitespace-nowrap text-center">
                                <div className="job-toggle-switch">
                                  <div className={`toggle-switch ${workflow.is_commitment_point ? 'active' : ''}`}>
                                    <div className="toggle-slider"></div>
                                  </div>
                                  <span className="toggle-label">{workflow.is_commitment_point ? 'Yes' : 'No'}</span>
                                </div>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-center">
                                <div className="flex items-center justify-center">
                                  {workflow.integration_logo ? (
                                    <img
                                      src={`/assets/integrations/${workflow.integration_logo}`}
                                      alt={workflow.integration_name}
                                      className="h-6 w-auto max-w-16 object-contain"
                                      onError={(e) => {
                                        e.currentTarget.style.display = 'none';
                                        if (e.currentTarget.nextElementSibling) {
                                          (e.currentTarget.nextElementSibling as HTMLElement).style.display = 'inline';
                                        }
                                      }}
                                    />
                                  ) : null}
                                  <span className="text-sm text-primary" style={{ display: workflow.integration_logo ? 'none' : 'inline' }}>
                                    {workflow.integration_name || '-'}
                                  </span>
                                </div>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-center">
                                <div
                                  className="job-toggle-switch cursor-pointer"
                                  onClick={() => handleToggleActive(workflow.id, workflow.active)}
                                >
                                  <div className={`toggle-switch ${workflow.active ? 'active' : ''}`}>
                                    <div className="toggle-slider"></div>
                                  </div>
                                  <span className="toggle-label">{workflow.active ? 'On' : 'Off'}</span>
                                </div>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-center">
                                <div className="flex items-center justify-center space-x-2">
                                  <button
                                    onClick={() => handleEdit(workflow.id)}
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

      {/* Dependency Modal */}
      <DependencyModal
        isOpen={dependencyModal.isOpen}
        onClose={() => setDependencyModal(prev => ({ ...prev, isOpen: false }))}
        onConfirm={(targetId) => performToggle(dependencyModal.workflowId!, dependencyModal.action === 'activate')}
        title={`${dependencyModal.action === 'deactivate' ? 'Deactivate' : 'Activate'} Workflow`}
        itemName={dependencyModal.workflowName}
        action={dependencyModal.action}
        dependencyCount={dependencyModal.dependencies.length}
        affectedItemsCount={dependencyModal.dependencies.reduce((sum: number, dep: any) => sum + (dep.affected_items_count || 0), 0)}
        dependencyType="workflow step(s)"
        affectedItemType="work item(s)"
        reassignmentTargets={dependencyModal.reassignmentTargets}
        targetDisplayField="step_name"
        allowSkipReassignment={dependencyModal.action === 'deactivate'}
        onShowError={showError}
      />

      {/* Edit Modal */}
      {editModal.workflow && (
        <EditModal
          isOpen={editModal.isOpen}
          onClose={() => setEditModal({ isOpen: false, workflow: null })}
          onSave={handleEditSave}
          title="Edit Workflow"
          fields={[
            {
              name: 'step_name',
              label: 'Step Name',
              type: 'text',
              value: editModal.workflow.step_name,
              required: true,
              placeholder: 'Enter step name'
            },
            {
              name: 'step_number',
              label: 'Step Number',
              type: 'number',
              value: editModal.workflow.step_number || '',
              placeholder: 'Enter step number (optional)'
            },
            {
              name: 'step_category',
              label: 'Step Category',
              type: 'select',
              value: editModal.workflow.step_category,
              required: true,
              options: [
                { value: 'To Do', label: 'To Do' },
                { value: 'In Progress', label: 'In Progress' },
                { value: 'Done', label: 'Done' },
                { value: 'Blocked', label: 'Blocked' }
              ]
            },
            {
              name: 'is_commitment_point',
              label: 'Commitment Point',
              type: 'checkbox',
              value: editModal.workflow.is_commitment_point,
              placeholder: 'Mark as commitment point'
            },
            {
              name: 'integration_id',
              label: 'Integration',
              type: 'select',
              value: editModal.workflow.integration_id || '',
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

export default WorkflowsPage
