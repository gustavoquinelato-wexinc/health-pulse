import axios from 'axios'
import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import CollapsedSidebar from '../components/CollapsedSidebar'
import Header from '../components/Header'
import useDocumentTitle from '../hooks/useDocumentTitle'

interface Tenant {
  id: number
  name: string
  website?: string
  assets_folder?: string
  logo_filename?: string
  active: boolean
  created_at: string
  last_updated_at: string
}


export default function TenantManagementPage() {
  const navigate = useNavigate()
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingTenant, setEditingTenant] = useState<Tenant | null>(null)
  const [formData, setFormData] = useState({
    name: '',
    website: '',
    assets_folder: '',
    logo_filename: '',
    active: true
  })

  // Set document title
  useDocumentTitle('Tenant Management')

  useEffect(() => {
    fetchTenants()
  }, [])

  const fetchTenants = async () => {
    try {
      setLoading(true)
      const token = localStorage.getItem('pulse_token')
      
      if (!token) {
        navigate('/login')
        return
      }

      const response = await axios.get('/api/v1/admin/tenants', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      setTenants(response.data)
      setError(null)
    } catch (err: any) {
      console.error('Error fetching tenants:', err)
      if (err.response?.status === 401) {
        navigate('/login')
      } else {
        setError('Failed to load tenants')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleCreateTenant = async (e: React.FormEvent) => {
    e.preventDefault()
    
    try {
      const token = localStorage.getItem('pulse_token')
      
      if (!token) {
        navigate('/login')
        return
      }

      await axios.post('/api/v1/admin/tenants', formData, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      setShowCreateModal(false)
      setFormData({
        name: '',
        website: '',
        assets_folder: '',
        logo_filename: '',
        active: true
      })
      fetchTenants()
    } catch (err: any) {
      console.error('Error creating tenant:', err)
      if (err.response?.status === 401) {
        navigate('/login')
      } else {
        setError('Failed to create tenant')
      }
    }
  }

  const handleUpdateTenant = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!editingTenant) return

    try {
      const token = localStorage.getItem('pulse_token')
      
      if (!token) {
        navigate('/login')
        return
      }

      await axios.put(`/api/v1/admin/tenants/${editingTenant.id}`, formData, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      setEditingTenant(null)
      setFormData({
        name: '',
        website: '',
        assets_folder: '',
        logo_filename: '',
        active: true
      })
      fetchTenants()
    } catch (err: any) {
      console.error('Error updating tenant:', err)
      if (err.response?.status === 401) {
        navigate('/login')
      } else {
        setError('Failed to update tenant')
      }
    }
  }

  const handleDeleteTenant = async (id: number) => {
    if (!confirm('Are you sure you want to delete this tenant?')) {
      return
    }

    try {
      const token = localStorage.getItem('pulse_token')
      
      if (!token) {
        navigate('/login')
        return
      }

      await axios.delete(`/api/v1/admin/tenants/${id}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      fetchTenants()
    } catch (err: any) {
      console.error('Error deleting tenant:', err)
      if (err.response?.status === 401) {
        navigate('/login')
      } else {
        setError('Failed to delete tenant')
      }
    }
  }

  const openEditModal = (tenant: Tenant) => {
    setEditingTenant(tenant)
    setFormData({
      name: tenant.name,
      website: tenant.website || '',
      assets_folder: tenant.assets_folder || '',
      logo_filename: tenant.logo_filename || '',
      active: tenant.active
    })
  }

  const closeModal = () => {
    setShowCreateModal(false)
    setEditingTenant(null)
    setFormData({
      name: '',
      website: '',
      assets_folder: '',
      logo_filename: '',
      active: true
    })
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-primary">
        <Header />
        <div className="flex">
          <CollapsedSidebar />
          <main className="flex-1 p-6 ml-16">
            <div className="flex items-center justify-center h-64">
              <div className="text-secondary">Loading tenants...</div>
            </div>
          </main>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-primary">
      <Header />
      
      <div className="flex">
        <CollapsedSidebar />
        
        <main className="flex-1 p-6 ml-16">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="space-y-6"
          >
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold text-primary">Tenant Management</h1>
                <p className="text-secondary mt-2">Manage system tenants and their configurations</p>
              </div>
              
              <button
                onClick={() => setShowCreateModal(true)}
                className="bg-accent text-white px-4 py-2 rounded-lg hover:bg-accent/90 transition-colors"
              >
                Create Tenant
              </button>
            </div>

            {error && (
              <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
                {error}
              </div>
            )}

            <div className="bg-secondary rounded-lg shadow overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Name
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Website
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Assets Folder
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Created
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {tenants.map((tenant) => (
                    <tr key={tenant.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-gray-900">{tenant.name}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-500">
                          {tenant.website ? (
                            <a href={tenant.website} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-800">
                              {tenant.website}
                            </a>
                          ) : (
                            '-'
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-500">{tenant.assets_folder || '-'}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                          tenant.active 
                            ? 'bg-green-100 text-green-800' 
                            : 'bg-red-100 text-red-800'
                        }`}>
                          {tenant.active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-500">
                          {new Date(tenant.created_at).toLocaleDateString()}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
                        <button
                          onClick={() => openEditModal(tenant)}
                          className="text-blue-600 hover:text-blue-900"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => handleDeleteTenant(tenant.id)}
                          className="text-red-600 hover:text-red-900"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              
              {tenants.length === 0 && (
                <div className="text-center py-8 text-gray-500">
                  No tenants found
                </div>
              )}
            </div>
          </motion.div>
        </main>
      </div>

      {/* Create/Edit Modal */}
      {(showCreateModal || editingTenant) && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h2 className="text-xl font-bold mb-4">
              {editingTenant ? 'Edit Tenant' : 'Create Tenant'}
            </h2>
            
            <form onSubmit={editingTenant ? handleUpdateTenant : handleCreateTenant}>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Website
                  </label>
                  <input
                    type="url"
                    value={formData.website}
                    onChange={(e) => setFormData({ ...formData, website: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Assets Folder
                  </label>
                  <input
                    type="text"
                    value={formData.assets_folder}
                    onChange={(e) => setFormData({ ...formData, assets_folder: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Logo Filename
                  </label>
                  <input
                    type="text"
                    value={formData.logo_filename}
                    onChange={(e) => setFormData({ ...formData, logo_filename: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="active"
                    checked={formData.active}
                    onChange={(e) => setFormData({ ...formData, active: e.target.checked })}
                    className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                  />
                  <label htmlFor="active" className="ml-2 block text-sm text-gray-900">
                    Active
                  </label>
                </div>
              </div>
              
              <div className="flex justify-end space-x-3 mt-6">
                <button
                  type="button"
                  onClick={closeModal}
                  className="px-4 py-2 text-gray-700 bg-gray-200 rounded-md hover:bg-gray-300 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
                >
                  {editingTenant ? 'Update' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
