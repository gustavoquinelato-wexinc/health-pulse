import axios from 'axios'
import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import CollapsedSidebar from '../components/CollapsedSidebar'
import Header from '../components/Header'
import useDocumentTitle from '../hooks/useDocumentTitle'

interface Client {
  id: number
  name: string
  website?: string
  logo_filename?: string
  active: boolean
  created_at: string
  last_updated_at: string
}

interface CreateClientRequest {
  name: string
  website?: string
  active: boolean
}

interface UpdateClientRequest {
  name?: string
  website?: string
  active?: boolean
}

export default function ClientManagementPage() {
  const navigate = useNavigate()
  const [clients, setClients] = useState<Client[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Modal states
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [editingClient, setEditingClient] = useState<Client | null>(null)
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [deletingClient, setDeletingClient] = useState<Client | null>(null)
  const [showLogoModal, setShowLogoModal] = useState(false)
  const [logoClient, setLogoClient] = useState<Client | null>(null)

  // Form states
  const [createForm, setCreateForm] = useState<CreateClientRequest>({
    name: '',
    website: '',
    active: true
  })
  const [updateForm, setUpdateForm] = useState<UpdateClientRequest>({})

  // Logo upload states
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploading, setUploading] = useState(false)

  // Set document title
  useDocumentTitle('Client Management - Settings')

  useEffect(() => {
    loadClients()
  }, [])

  const loadClients = async () => {
    try {
      setLoading(true)
      setError(null)

      const response = await axios.get('/api/v1/admin/clients')
      console.log('Loaded clients:', response.data)
      setClients(response.data)
    } catch (error: any) {
      console.error('Error loading clients:', error)
      setError(error.response?.data?.detail || 'Failed to load clients')
    } finally {
      setLoading(false)
    }
  }

  const handleCreateClient = async () => {
    try {
      await axios.post('/api/v1/admin/clients', createForm)
      setShowCreateModal(false)
      setCreateForm({ name: '', website: '', active: true })
      await loadClients()
    } catch (error: any) {
      setError(error.response?.data?.detail || 'Failed to create client')
    }
  }

  const handleUpdateClient = async () => {
    if (!editingClient) return

    try {
      await axios.put(`/api/v1/admin/clients/${editingClient.id}`, updateForm)
      setShowEditModal(false)
      setEditingClient(null)
      setUpdateForm({})
      await loadClients()
    } catch (error: any) {
      setError(error.response?.data?.detail || 'Failed to update client')
    }
  }

  const handleDeleteClient = async () => {
    if (!deletingClient) return

    try {
      await axios.delete(`/api/v1/admin/clients/${deletingClient.id}`)
      setShowDeleteModal(false)
      setDeletingClient(null)
      await loadClients()
    } catch (error: any) {
      setError(error.response?.data?.detail || 'Failed to delete client')
    }
  }

  const handleLogoUpload = async () => {
    if (!selectedFile || !logoClient) return

    try {
      setUploading(true)
      setUploadProgress(0)

      const formData = new FormData()
      formData.append('logo', selectedFile)

      const response = await axios.post(
        `/api/v1/admin/clients/${logoClient.id}/logo`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data'
          },
          onUploadProgress: (progressEvent) => {
            if (progressEvent.total) {
              const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total)
              setUploadProgress(progress)
            }
          }
        }
      )

      setShowLogoModal(false)
      setLogoClient(null)
      setSelectedFile(null)
      setUploadProgress(0)
      await loadClients()
    } catch (error: any) {
      setError(error.response?.data?.detail || 'Failed to upload logo')
    } finally {
      setUploading(false)
    }
  }

  const openEditModal = (client: Client) => {
    setEditingClient(client)
    setUpdateForm({
      name: client.name,
      website: client.website || '',
      active: client.active
    })
    setShowEditModal(true)
  }

  const openDeleteModal = (client: Client) => {
    setDeletingClient(client)
    setShowDeleteModal(true)
  }

  const openLogoModal = (client: Client) => {
    setLogoClient(client)
    setSelectedFile(null)
    setUploadProgress(0)
    setShowLogoModal(true)
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString()
  }

  const getLogoUrl = (client: Client) => {
    if (client.logo_filename) {
      // Use the public static folder path
      const logoUrl = `/static/logos/${client.logo_filename}`
      console.log('Logo URL for client', client.name, ':', logoUrl)
      return logoUrl
    }
    return null
  }

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      // Validate file type
      if (!file.type.startsWith('image/')) {
        setError('Please select an image file')
        return
      }

      // Validate file size (max 5MB)
      if (file.size > 5 * 1024 * 1024) {
        setError('File size must be less than 5MB')
        return
      }

      setSelectedFile(file)
      setError(null)
    }
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
            {/* Header */}
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
                <h1 className="text-3xl font-bold text-primary">
                  Client Management
                </h1>
                <p className="text-secondary">
                  Manage client configurations, logos, and branding settings
                </p>
              </div>
              <div className="flex space-x-3">
                <button
                  onClick={loadClients}
                  disabled={loading}
                  className="btn-secondary flex items-center space-x-2"
                >
                  <span className={`${loading ? 'animate-spin' : ''}`}>🔄</span>
                  <span>Refresh</span>
                </button>
                <button
                  onClick={() => setShowCreateModal(true)}
                  className="btn-primary flex items-center space-x-2"
                >
                  <span>➕</span>
                  <span>Create Client</span>
                </button>
              </div>
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="text-red-500">⚠️</span>
                    <span className="text-red-700">{error}</span>
                  </div>
                  <button
                    onClick={() => setError(null)}
                    className="text-red-500 hover:text-red-700"
                  >
                    ✕
                  </button>
                </div>
              </div>
            )}

            {/* Clients Table */}
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                <span className="ml-3 text-secondary">Loading clients...</span>
              </div>
            ) : (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="card overflow-hidden"
              >
                <div className="p-6 border-b border-tertiary">
                  <h3 className="text-lg font-semibold text-primary">Clients ({clients.length})</h3>
                </div>

                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-tertiary">
                    <thead className="bg-tertiary">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-secondary uppercase tracking-wider">
                          Client
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-secondary uppercase tracking-wider">
                          Logo
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-secondary uppercase tracking-wider">
                          Status
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-secondary uppercase tracking-wider">
                          Created
                        </th>
                        <th className="px-6 py-3 text-right text-xs font-medium text-secondary uppercase tracking-wider">
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-primary divide-y divide-tertiary">
                      {clients.map((client) => (
                        <tr key={client.id} className="hover:bg-tertiary">
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div>
                              <div className="text-sm font-medium text-primary">{client.name}</div>
                              {client.website && (
                                <div className="text-sm text-secondary">{client.website}</div>
                              )}
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            {getLogoUrl(client) ? (
                              <img
                                src={getLogoUrl(client)!}
                                alt={`${client.name} logo`}
                                className="h-8 w-8 rounded object-contain"
                              />
                            ) : (
                              <div className="h-8 w-8 bg-gray-200 rounded flex items-center justify-center">
                                <span className="text-xs text-gray-500">No Logo</span>
                              </div>
                            )}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${client.active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                              }`}>
                              {client.active ? 'Active' : 'Inactive'}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-secondary">
                            {formatDate(client.created_at)}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                            <div className="flex justify-end space-x-2">
                              <button
                                onClick={() => openLogoModal(client)}
                                className="text-blue-600 hover:text-blue-900"
                                title="Upload Logo"
                              >
                                🖼️
                              </button>
                              <button
                                onClick={() => openEditModal(client)}
                                className="text-blue-600 hover:text-blue-900"
                                title="Edit Client"
                              >
                                ✏️
                              </button>
                              <button
                                onClick={() => openDeleteModal(client)}
                                className="text-red-600 hover:text-red-900"
                                title="Delete Client"
                              >
                                🗑️
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </motion.div>
            )}
          </motion.div>
        </main>
      </div>

      {/* Create Client Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-primary rounded-lg p-6 w-full max-w-md mx-4"
          >
            <h3 className="text-lg font-semibold text-primary mb-4">Create New Client</h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-secondary mb-1">Client Name *</label>
                <input
                  type="text"
                  value={createForm.name}
                  onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
                  className="w-full px-3 py-2 border border-tertiary rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Enter client name"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-secondary mb-1">Website</label>
                <input
                  type="url"
                  value={createForm.website}
                  onChange={(e) => setCreateForm({ ...createForm, website: e.target.value })}
                  className="w-full px-3 py-2 border border-tertiary rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="https://example.com"
                />
              </div>

              <div>
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={createForm.active}
                    onChange={(e) => setCreateForm({ ...createForm, active: e.target.checked })}
                    className="rounded border-tertiary focus:ring-2 focus:ring-blue-500"
                  />
                  <span className="text-sm font-medium text-secondary">Active Client</span>
                </label>
              </div>
            </div>

            <div className="flex justify-end space-x-3 mt-6">
              <button
                onClick={() => setShowCreateModal(false)}
                className="btn-secondary"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateClient}
                className="btn-primary"
                disabled={!createForm.name.trim()}
              >
                Create Client
              </button>
            </div>
          </motion.div>
        </div>
      )}

      {/* Edit Client Modal */}
      {showEditModal && editingClient && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-primary rounded-lg p-6 w-full max-w-md mx-4"
          >
            <h3 className="text-lg font-semibold text-primary mb-4">Edit Client</h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-secondary mb-1">Client Name *</label>
                <input
                  type="text"
                  value={updateForm.name || ''}
                  onChange={(e) => setUpdateForm({ ...updateForm, name: e.target.value })}
                  className="w-full px-3 py-2 border border-tertiary rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-secondary mb-1">Website</label>
                <input
                  type="url"
                  value={updateForm.website || ''}
                  onChange={(e) => setUpdateForm({ ...updateForm, website: e.target.value })}
                  className="w-full px-3 py-2 border border-tertiary rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="https://example.com"
                />
              </div>

              <div>
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={updateForm.active || false}
                    onChange={(e) => setUpdateForm({ ...updateForm, active: e.target.checked })}
                    className="rounded border-tertiary focus:ring-2 focus:ring-blue-500"
                  />
                  <span className="text-sm font-medium text-secondary">Active Client</span>
                </label>
              </div>
            </div>

            <div className="flex justify-end space-x-3 mt-6">
              <button
                onClick={() => setShowEditModal(false)}
                className="btn-secondary"
              >
                Cancel
              </button>
              <button
                onClick={handleUpdateClient}
                className="btn-primary"
                disabled={!updateForm.name?.trim()}
              >
                Update Client
              </button>
            </div>
          </motion.div>
        </div>
      )}

      {/* Delete Client Modal */}
      {showDeleteModal && deletingClient && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-primary rounded-lg p-6 w-full max-w-md mx-4"
          >
            <h3 className="text-lg font-semibold text-red-600 mb-4">Delete Client</h3>

            <div className="mb-6">
              <p className="text-secondary mb-2">
                Are you sure you want to delete this client? This action cannot be undone and will affect all associated data.
              </p>
              <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                <p className="text-sm text-red-800">
                  <strong>Client:</strong> {deletingClient.name}
                </p>
                {deletingClient.website && (
                  <p className="text-sm text-red-800">
                    <strong>Website:</strong> {deletingClient.website}
                  </p>
                )}
                <p className="text-sm text-red-800">
                  <strong>Status:</strong> {deletingClient.active ? 'Active' : 'Inactive'}
                </p>
              </div>
            </div>

            <div className="flex justify-end space-x-3">
              <button
                onClick={() => setShowDeleteModal(false)}
                className="btn-secondary"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteClient}
                className="btn-danger"
              >
                Delete Client
              </button>
            </div>
          </motion.div>
        </div>
      )}

      {/* Logo Upload Modal */}
      {showLogoModal && logoClient && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-primary rounded-lg p-6 w-full max-w-md mx-4"
          >
            <h3 className="text-lg font-semibold text-primary mb-4">Upload Logo for {logoClient.name}</h3>

            <div className="space-y-4">
              {/* Current Logo */}
              {getLogoUrl(logoClient) && (
                <div>
                  <label className="block text-sm font-medium text-secondary mb-2">Current Logo</label>
                  <div className="flex items-center space-x-3">
                    <img
                      src={getLogoUrl(logoClient)!}
                      alt={`${logoClient.name} current logo`}
                      className="h-16 w-16 rounded object-contain border border-tertiary"
                    />
                    <div className="text-sm text-secondary">
                      <p>Filename: {logoClient.logo_filename}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* File Upload */}
              <div>
                <label className="block text-sm font-medium text-secondary mb-2">
                  {getLogoUrl(logoClient) ? 'Replace Logo' : 'Upload Logo'}
                </label>
                <input
                  type="file"
                  accept="image/*"
                  onChange={handleFileSelect}
                  className="w-full px-3 py-2 border border-tertiary rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <p className="text-xs text-secondary mt-1">
                  Supported formats: PNG, JPG, GIF. Max size: 5MB
                </p>
              </div>

              {/* File Preview */}
              {selectedFile && (
                <div>
                  <label className="block text-sm font-medium text-secondary mb-2">Preview</label>
                  <div className="flex items-center space-x-3">
                    <img
                      src={URL.createObjectURL(selectedFile)}
                      alt="Logo preview"
                      className="h-16 w-16 rounded object-contain border border-tertiary"
                    />
                    <div className="text-sm text-secondary">
                      <p>Name: {selectedFile.name}</p>
                      <p>Size: {(selectedFile.size / 1024 / 1024).toFixed(2)} MB</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Upload Progress */}
              {uploading && (
                <div>
                  <div className="flex justify-between text-sm text-secondary mb-1">
                    <span>Uploading...</span>
                    <span>{uploadProgress}%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${uploadProgress}%` }}
                    ></div>
                  </div>
                </div>
              )}
            </div>

            <div className="flex justify-end space-x-3 mt-6">
              <button
                onClick={() => setShowLogoModal(false)}
                className="btn-secondary"
                disabled={uploading}
              >
                Cancel
              </button>
              <button
                onClick={handleLogoUpload}
                className="btn-primary"
                disabled={!selectedFile || uploading}
              >
                {uploading ? 'Uploading...' : 'Upload Logo'}
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </div>
  )
}
