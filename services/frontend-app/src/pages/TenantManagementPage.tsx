import axios from 'axios'
import { motion } from 'framer-motion'
import { Edit, X, Upload } from 'lucide-react'
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
  const [selectedFile, setSelectedFile] = useState<File | null>(null)

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

      let updatedFormData = { ...formData }
      let uploadedFilename: string | null = null  // Declare outside the if block

      // Upload file if one is selected
      if (selectedFile) {
        try {
          uploadedFilename = await uploadSelectedFile()
          if (uploadedFilename) {
            updatedFormData.logo_filename = uploadedFilename
          }
        } catch (uploadErr: any) {
          alert('Failed to upload logo: ' + uploadErr.message)
          return // Don't proceed with tenant update if file upload fails
        }
      }

      await axios.put(`/api/v1/admin/tenants/${editingTenant.id}`, updatedFormData, {
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
      setSelectedFile(null)
      fetchTenants()

      // Notify header and other components about logo update
      if (selectedFile && uploadedFilename) {
        const logoUpdateEvent = new CustomEvent('logoUpdated', {
          detail: {
            tenantId: editingTenant.id,
            assets_folder: updatedFormData.assets_folder,
            logo_filename: uploadedFilename
          }
        })
        window.dispatchEvent(logoUpdateEvent)

        // Show success message
        alert(`Tenant updated successfully! Logo "${selectedFile.name}" has been uploaded.`)
      } else {
        // Show success message for tenant update without logo
        alert('Tenant updated successfully!')
      }
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
    setSelectedFile(null) // Clear any previously selected file
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
    setSelectedFile(null)
  }

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) {
      setSelectedFile(null)
      return
    }

    // Validate file type
    const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/svg+xml']
    if (!allowedTypes.includes(file.type)) {
      alert('Please select a valid image file (PNG, JPG, JPEG, or SVG)')
      event.target.value = '' // Clear the input
      setSelectedFile(null)
      return
    }

    // Validate file size (max 5MB)
    if (file.size > 5 * 1024 * 1024) {
      alert('File size must be less than 5MB')
      event.target.value = '' // Clear the input
      setSelectedFile(null)
      return
    }

    // Store the file for later upload
    setSelectedFile(file)
  }

  const uploadSelectedFile = async () => {
    if (!selectedFile || !editingTenant) return null

    try {
      const token = localStorage.getItem('pulse_token')
      if (!token) {
        navigate('/login')
        return null
      }

      // Create FormData for file upload
      const uploadFormData = new FormData()
      uploadFormData.append('logo', selectedFile)

      const response = await axios.post(`/api/v1/admin/tenants/${editingTenant.id}/logo`, uploadFormData, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'multipart/form-data'
        }
      })

      if (response.data.message) {
        return response.data.logo_filename
      } else {
        throw new Error(response.data.message || 'Upload failed')
      }
    } catch (err: any) {
      console.error('Error uploading logo:', err)
      if (err.response?.status === 401) {
        navigate('/login')
      } else {
        throw new Error(err.response?.data?.message || 'Network error')
      }
    }
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
              <div className="space-y-2">
                <div className="flex items-center space-x-3">
                  <button
                    onClick={() => navigate('/settings')}
                    className="text-secondary hover:text-primary transition-colors"
                  >
                    ← Back to Settings
                  </button>
                </div>
                <h1 className="text-3xl font-bold text-primary">Tenant Management</h1>
                <p className="text-secondary">Manage system tenants and their configurations</p>
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

            <div className="card overflow-hidden">
              <table className="min-w-full divide-y divide-border">
                <thead className="bg-muted">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-secondary uppercase tracking-wider">
                      Name
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-secondary uppercase tracking-wider">
                      Website
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-secondary uppercase tracking-wider">
                      Assets Folder
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-secondary uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-secondary uppercase tracking-wider">
                      Created
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-secondary uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-primary divide-y divide-border">
                  {tenants.map((tenant) => (
                    <tr key={tenant.id} className="hover:bg-muted">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-primary">{tenant.name}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-secondary">
                          {tenant.website ? (
                            <a href={tenant.website} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-700 transition-colors duration-150">
                              {tenant.website}
                            </a>
                          ) : (
                            '-'
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-secondary">{tenant.assets_folder || '-'}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                          tenant.active
                            ? 'bg-green-100 text-green-800'
                            : 'bg-gray-100 text-gray-800'
                        }`}>
                          {tenant.active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-secondary">
                          {new Date(tenant.created_at).toLocaleDateString()}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                        <div className="flex items-center justify-end space-x-2">
                          <button
                            onClick={() => openEditModal(tenant)}
                            className="text-blue-600 hover:text-blue-700 transition-colors duration-150"
                            title="Edit"
                          >
                            <Edit className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDeleteTenant(tenant.id)}
                            className="text-red-600 hover:text-red-700 transition-colors duration-150"
                            title="Delete"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
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
          <div className="card w-full max-w-md mx-4">
            <div className="flex items-center justify-between p-6 pb-4">
              <h2 className="text-xl font-bold text-primary">
                {editingTenant ? 'Edit Tenant' : 'Create Tenant'}
              </h2>
              <button
                type="button"
                onClick={closeModal}
                className="text-gray-400 hover:text-gray-500 transition-colors duration-150"
                title="Close"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <form onSubmit={editingTenant ? handleUpdateTenant : handleCreateTenant} className="px-6 pb-6">
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-primary mb-1">
                    Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full px-3 py-2 border border-border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-primary text-primary"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-primary mb-1">
                    Website
                  </label>
                  <input
                    type="url"
                    value={formData.website}
                    onChange={(e) => setFormData({ ...formData, website: e.target.value })}
                    className="w-full px-3 py-2 border border-border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-primary text-primary"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-primary mb-1">
                    Assets Folder
                  </label>
                  <input
                    type="text"
                    value={formData.assets_folder}
                    onChange={(e) => setFormData({ ...formData, assets_folder: e.target.value })}
                    className="w-full px-3 py-2 border border-border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-primary text-primary"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-primary mb-1">
                    Logo Upload
                  </label>
                  <div className="space-y-2">
                    <div className="space-y-2">
                      <div className="flex items-center space-x-2">
                        <input
                          type="text"
                          value={formData.logo_filename}
                          onChange={(e) => setFormData({ ...formData, logo_filename: e.target.value })}
                          placeholder="Logo filename (e.g., company-logo.png)"
                          className="flex-1 px-3 py-2 border border-border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-primary text-primary"
                        />
                        <div className="relative">
                          <input
                            type="file"
                            accept="image/png,image/jpeg,image/jpg,image/svg+xml"
                            onChange={handleFileSelect}
                            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                            disabled={!editingTenant}
                          />
                          <button
                            type="button"
                            disabled={!editingTenant}
                            className="px-3 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 transition-colors duration-150 flex items-center space-x-1 disabled:bg-gray-400 disabled:cursor-not-allowed"
                            title={!editingTenant ? "Save tenant first to select logo" : "Select Logo File"}
                          >
                            <Upload className="w-4 h-4" />
                            <span className="text-sm">Select</span>
                          </button>
                        </div>
                      </div>
                      {selectedFile && (
                        <div className="text-sm text-blue-600 bg-blue-50 px-3 py-2 rounded-md">
                          📁 Selected: {selectedFile.name} ({(selectedFile.size / 1024).toFixed(1)} KB)
                        </div>
                      )}
                    </div>
                    <p className="text-xs text-secondary">
                      {!editingTenant
                        ? "Save the tenant first, then edit to select and upload a logo file. Supported formats: PNG, JPG, JPEG, SVG"
                        : selectedFile
                          ? "Logo file selected. Click 'Update' to save tenant and upload the logo."
                          : "Select a logo file or enter the filename manually. File will be uploaded when you click 'Update'. Supported formats: PNG, JPG, JPEG, SVG"
                      }
                    </p>
                  </div>
                </div>

                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="active"
                    checked={formData.active}
                    onChange={(e) => setFormData({ ...formData, active: e.target.checked })}
                    className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-border rounded"
                  />
                  <label htmlFor="active" className="ml-2 block text-sm text-primary">
                    Active
                  </label>
                </div>
              </div>
              
              <div className="flex justify-end space-x-3 mt-6">
                <button
                  type="button"
                  onClick={closeModal}
                  className="px-4 py-2 text-gray-700 bg-gray-200 rounded-md hover:bg-gray-300 transition-colors duration-150"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors duration-150"
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
