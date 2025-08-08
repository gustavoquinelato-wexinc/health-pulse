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
  assets_folder?: string
  logo_filename?: string
  active: boolean
  created_at: string
  last_updated_at: string
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
  const [showEditModal, setShowEditModal] = useState(false)
  const [editingClient, setEditingClient] = useState<Client | null>(null)

  // Form states
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
      setClients(response.data)
    } catch (error: any) {
      console.error('Error loading clients:', error)
      setError(error.response?.data?.detail || 'Failed to load clients')
    } finally {
      setLoading(false)
    }
  }



  const handleUpdateClient = async () => {
    if (!editingClient) return

    try {
      let hasChanges = false

      // Handle logo upload first if there's a selected file
      if (selectedFile) {
        await handleLogoUpload()
        hasChanges = true
      }

      // Clean the update form to only send non-empty values
      const cleanedForm: any = {}

      // Only include name if it's different from current and not empty
      if (updateForm.name !== undefined && updateForm.name.trim() !== editingClient.name) {
        cleanedForm.name = updateForm.name.trim()
      }

      // Only include website if it's different from current
      if (updateForm.website !== undefined && updateForm.website !== editingClient.website) {
        cleanedForm.website = updateForm.website || null
      }

      // Only include active if it's different from current
      if (updateForm.active !== undefined && updateForm.active !== editingClient.active) {
        cleanedForm.active = updateForm.active
      }



      // Update profile fields if there are changes
      if (Object.keys(cleanedForm).length > 0) {
        await axios.put(`/api/v1/admin/clients/${editingClient.id}`, cleanedForm)
        hasChanges = true
      }

      // If no changes were made at all, just close the modal
      if (!hasChanges) {
        setShowEditModal(false)
        setEditingClient(null)
        setUpdateForm({})
        return
      }

      // Success - close modal and refresh
      setShowEditModal(false)
      setEditingClient(null)
      setUpdateForm({})
      await loadClients()
    } catch (error: any) {
      console.error('Update client error:', error.response?.data)
      if (error.response?.status === 403) {
        setError('You do not have permission to update clients. Admin privileges required.')
      } else if (error.response?.status === 400) {
        setError(error.response?.data?.detail || 'Invalid data provided')
      } else {
        setError(error.response?.data?.detail || 'Failed to update client')
      }
    }
  }



  const handleLogoUpload = async () => {
    if (!selectedFile || !editingClient) return

    try {
      setUploading(true)
      setUploadProgress(0)

      const formData = new FormData()
      formData.append('logo', selectedFile)

      const response = await axios.post(
        `/api/v1/admin/clients/${editingClient.id}/logo`,
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
      // Update the editing client with new logo info - use both assets_folder and logo_filename
      const updatedClient = {
        ...editingClient,
        assets_folder: response.data.assets_folder,
        logo_filename: response.data.logo_filename
      }
      setEditingClient(updatedClient)

      // Also update the client in the main clients list for immediate UI update
      setClients(prevClients =>
        prevClients.map(client =>
          client.id === editingClient.id
            ? { ...client, assets_folder: response.data.assets_folder, logo_filename: response.data.logo_filename }
            : client
        )
      )

      // Dispatch custom event to notify other components (like Header) of logo update
      const logoUpdateEvent = new CustomEvent('logoUpdated', {
        detail: {
          clientId: editingClient.id,
          assets_folder: response.data.assets_folder,
          logo_filename: response.data.logo_filename
        }
      })
      window.dispatchEvent(logoUpdateEvent)

      setSelectedFile(null)
      setUploadProgress(0)
      // Note: Don't close modal or reload clients here - let the calling function handle that
    } catch (error: any) {
      console.error('Logo upload error details:', {
        status: error.response?.status,
        data: error.response?.data,
        message: error.message
      })
      setError(error.response?.data?.detail || 'Failed to upload logo')
      throw error // Re-throw so the calling function knows it failed
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
    // Reset logo upload state and clear any errors
    setSelectedFile(null)
    setUploadProgress(0)
    setError(null)
    setShowEditModal(true)
  }







  const getLogoUrl = (client: Client) => {
    if (client.assets_folder && client.logo_filename) {
      // Use the client-specific assets folder path with cache busting
      const timestamp = Date.now()
      return `/assets/${client.assets_folder}/${client.logo_filename}?t=${timestamp}`
    }
    return null
  }

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]

    // Clear any previous errors
    setError(null)

    if (file) {
      // Validate file type - only PNG files allowed
      if (file.type !== 'image/png') {
        setError('Please select a PNG file only')
        setSelectedFile(null)
        // Clear the input
        event.target.value = ''
        return
      }

      // Validate file size (max 5MB)
      if (file.size > 5 * 1024 * 1024) {
        setError('File size must be less than 5MB')
        setSelectedFile(null)
        // Clear the input
        event.target.value = ''
        return
      }

      setSelectedFile(file)
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
                  Client Profile
                </h1>
                <p className="text-secondary">
                  Manage your organization's profile, branding, and settings
                </p>
              </div>

            </div>

            {/* Client Profile */}
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                <span className="ml-3 text-secondary">Loading client information...</span>
              </div>
            ) : clients.length > 0 ? (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-6"
              >
                {/* Client Profile Card */}
                <div className="card p-8">
                  <div className="flex items-start justify-between mb-6">
                    <div className="flex items-center space-x-6">
                      {/* Logo */}
                      <div className="flex-shrink-0">
                        {getLogoUrl(clients[0]) ? (
                          <img
                            src={getLogoUrl(clients[0])!}
                            alt={`${clients[0].name} logo`}
                            className="h-20 w-20 rounded-lg object-contain border border-tertiary"
                          />
                        ) : (
                          <div className="h-20 w-20 rounded-lg bg-tertiary flex items-center justify-center">
                            <span className="text-secondary text-2xl font-bold">
                              {clients[0].name.charAt(0).toUpperCase()}
                            </span>
                          </div>
                        )}
                      </div>

                      {/* Client Info */}
                      <div className="flex-1">
                        <h2 className="text-2xl font-bold text-primary mb-2">{clients[0].name}</h2>
                        <div className="space-y-2">
                          {clients[0].website && (
                            <div className="flex items-center space-x-2">
                              <span className="text-sm text-secondary">Website:</span>
                              <a
                                href={clients[0].website}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-blue-600 hover:text-blue-800 hover:underline text-sm"
                              >
                                {clients[0].website}
                              </a>
                            </div>
                          )}
                          <div className="flex items-center space-x-2">
                            <span className="text-sm text-secondary">Status:</span>
                            <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${clients[0].active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                              }`}>
                              {clients[0].active ? 'Active' : 'Inactive'}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Edit Button */}
                    <button
                      onClick={() => openEditModal(clients[0])}
                      className="btn-crud-edit flex items-center space-x-2"
                    >
                      <span>✎</span>
                      <span>Edit Profile</span>
                    </button>
                  </div>
                </div>
              </motion.div>
            ) : (
              <div className="text-center py-12">
                <p className="text-secondary">No client information available.</p>
              </div>
            )}
          </motion.div>
        </main>
      </div>



      {/* Edit Client Modal */}
      {showEditModal && editingClient && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-primary rounded-lg p-6 w-full max-w-md mx-4"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-primary">Edit Profile</h3>
              <button
                onClick={() => setShowEditModal(false)}
                className="text-secondary hover:text-primary transition-colors"
                title="Close"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Error Display in Modal */}
            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="text-red-500">⚠️</span>
                    <span className="text-red-700 text-sm">{error}</span>
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

              {/* Current Logo */}
              {getLogoUrl(editingClient) && (
                <div>
                  <label className="block text-sm font-medium text-secondary mb-2">Current Logo</label>
                  <div className="flex items-center space-x-3">
                    <img
                      src={getLogoUrl(editingClient)!}
                      alt={`${editingClient.name} current logo`}
                      className="h-16 w-16 rounded object-contain border border-tertiary"
                    />
                    <div className="text-sm text-secondary">
                      <p>Filename: {editingClient.logo_filename}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* File Upload */}
              <div>
                <label className="block text-sm font-medium text-secondary mb-2">
                  {getLogoUrl(editingClient) ? 'Replace Logo' : 'Upload Logo'}
                </label>
                <input
                  type="file"
                  accept="image/png"
                  onChange={handleFileSelect}
                  className="w-full px-3 py-2 border border-tertiary rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <p className="text-xs text-secondary mt-1">
                  Supported format: PNG only. Max size: 5MB
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

              {/* Active Status */}
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
                className="btn-crud-cancel"
                disabled={uploading}
              >
                Cancel
              </button>
              <button
                onClick={handleUpdateClient}
                className="btn-crud-edit"
                disabled={!updateForm.name?.trim() || uploading}
              >
                {uploading ? 'Saving...' : selectedFile ? 'Save Profile & Logo' : 'Save Changes'}
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </div>
  )
}
