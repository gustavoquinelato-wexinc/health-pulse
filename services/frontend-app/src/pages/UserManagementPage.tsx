import axios from 'axios'
import { motion } from 'framer-motion'
import { LogOut, UserX } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import CollapsedSidebar from '../components/CollapsedSidebar'
import Header from '../components/Header'
import useDocumentTitle from '../hooks/useDocumentTitle'

interface User {
  id: number
  email: string
  first_name?: string
  last_name?: string
  role: string
  active: boolean
  created_at?: string
  last_login_at?: string
}

interface ActiveSession {
  id: number
  user_id: number
  user_email: string
  created_at: string
  last_activity_at: string
  ip_address?: string
  user_agent?: string
}

interface CreateUserRequest {
  email: string
  first_name?: string
  last_name?: string
  role: string
  password?: string
}

interface UpdateUserRequest {
  first_name?: string
  last_name?: string
  role?: string
  active?: boolean
  password?: string
  current_password?: string
}

export default function UserManagementPage() {
  const navigate = useNavigate()
  const [users, setUsers] = useState<User[]>([])
  const [activeSessions, setActiveSessions] = useState<ActiveSession[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'users' | 'sessions' | 'permissions'>('users')

  // Modal states
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [editingUser, setEditingUser] = useState<User | null>(null)
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [deletingUser, setDeletingUser] = useState<User | null>(null)
  const [showDeactivateModal, setShowDeactivateModal] = useState(false)
  const [deactivatingUser, setDeactivatingUser] = useState<User | null>(null)

  // Form states
  const [createForm, setCreateForm] = useState<CreateUserRequest>({
    email: '',
    first_name: '',
    last_name: '',
    role: 'user',
    password: ''
  })
  const [confirmPassword, setConfirmPassword] = useState('')
  const [updateForm, setUpdateForm] = useState<UpdateUserRequest>({})
  const [touchedFields, setTouchedFields] = useState<{ [key: string]: boolean }>({})
  const [submitAttempted, setSubmitAttempted] = useState(false)

  // Password change states for edit modal
  const [showPasswordFields, setShowPasswordFields] = useState(false)
  const [currentPassword, setCurrentPassword] = useState('')
  const [confirmPasswordEdit, setConfirmPasswordEdit] = useState('')

  // Email validation
  const isValidEmail = (email: string) => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    return emailRegex.test(email)
  }

  // Check if email already exists
  const isEmailUnique = (email: string) => {
    return !users.some(user => user.email.toLowerCase() === email.toLowerCase())
  }

  // Set document title
  useDocumentTitle('User Management - Settings')

  useEffect(() => {
    loadData()
  }, [activeTab])

  // Clear form when create modal opens
  useEffect(() => {
    if (showCreateModal) {
      setCreateForm({ email: '', first_name: '', last_name: '', role: 'user', password: '' })
      setConfirmPassword('')
      setTouchedFields({})
      setSubmitAttempted(false)
    }
  }, [showCreateModal])

  const loadData = async () => {
    try {
      setLoading(true)
      setError(null)

      if (activeTab === 'users') {
        await loadUsers()
      } else if (activeTab === 'sessions') {
        await loadActiveSessions()
      }
    } catch (error: any) {
      console.error('Error loading data:', error)
      setError(error.response?.data?.detail || 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }

  const loadUsers = async () => {
    const response = await axios.get('/api/v1/admin/users')
    setUsers(response.data)
  }

  const loadActiveSessions = async () => {
    const response = await axios.get('/api/v1/admin/active-sessions')
    setActiveSessions(response.data)
  }

  const handleCreateUser = async () => {
    // Mark that user attempted to submit
    setSubmitAttempted(true)

    // Check if form is valid
    const isFormValid = createForm.email &&
      isValidEmail(createForm.email) &&
      isEmailUnique(createForm.email) &&
      createForm.first_name?.trim() &&
      createForm.last_name?.trim() &&
      createForm.password?.trim() &&
      confirmPassword?.trim() &&
      createForm.password === confirmPassword

    if (!isFormValid) {
      // Mark all required fields as touched to show validation errors
      setTouchedFields({
        email: true,
        first_name: true,
        last_name: true,
        password: true,
        confirm_password: true
      })
      return
    }

    try {
      // Prepare request data with is_admin field
      const requestData = {
        ...createForm,
        is_admin: createForm.role === 'admin'
      }

      // Check authentication
      const token = localStorage.getItem('pulse_token')
      if (!token) {
        setError('Authentication token not found. Please log in again.')
        return
      }

      // Ensure the Authorization header is set
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`

      await axios.post('http://localhost:3001/api/v1/admin/users', requestData)
      setShowCreateModal(false)
      setCreateForm({ email: '', first_name: '', last_name: '', role: 'user', password: '' })
      setConfirmPassword('')
      await loadUsers()
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail ||
        error.response?.data?.message ||
        error.response?.data ||
        'Failed to create user'
      setError(typeof errorMessage === 'string' ? errorMessage : JSON.stringify(errorMessage))
    }
  }

  const handleUpdateUser = async () => {
    if (!editingUser) return

    try {
      // Validate password if changing
      if (showPasswordFields) {
        if (!currentPassword) {
          setError('Current password is required')
          return
        }
        if (!updateForm.password) {
          setError('New password is required')
          return
        }
        if (updateForm.password === currentPassword) {
          setError('New password must be different from current password')
          return
        }
        if (updateForm.password !== confirmPasswordEdit) {
          setError('Passwords do not match')
          return
        }
      }

      // Create update payload
      const updatePayload = { ...updateForm }
      if (showPasswordFields) {
        // Include current password for backend validation
        updatePayload.current_password = currentPassword
      } else {
        // Remove password from payload if not changing password
        delete updatePayload.password
      }

      await axios.put(`/api/v1/admin/users/${editingUser.id}`, updatePayload)
      setShowEditModal(false)
      setEditingUser(null)
      setUpdateForm({})
      setShowPasswordFields(false)
      setCurrentPassword('')
      setConfirmPasswordEdit('')
      await loadUsers()
    } catch (error: any) {
      setError(error.response?.data?.detail || 'Failed to update user')
    }
  }

  const handleDeleteUser = async () => {
    if (!deletingUser) return

    try {
      await axios.delete(`/api/v1/admin/users/${deletingUser.id}`)
      setShowDeleteModal(false)
      setDeletingUser(null)
      await loadUsers()
    } catch (error: any) {
      setError(error.response?.data?.detail || 'Failed to delete user')
    }
  }

  const handleTerminateSession = async (sessionId: string) => {
    try {
      const token = localStorage.getItem('token') || sessionStorage.getItem('token')
      if (!token) {
        setError('Authentication token not found. Please log in again.')
        return
      }

      await axios.post(`/api/v1/admin/terminate-session/${sessionId}`, {}, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      await loadActiveSessions()
      setError(null) // Clear any previous errors
    } catch (error: any) {
      setError(error.response?.data?.detail || 'Failed to terminate session')
    }
  }

  const handleTerminateAllSessions = async () => {
    if (!confirm('Are you sure you want to terminate all active sessions? This will log out all users.')) {
      return
    }

    try {
      const token = localStorage.getItem('token') || sessionStorage.getItem('token')
      if (!token) {
        setError('Authentication token not found. Please log in again.')
        return
      }

      await axios.post('/api/v1/admin/terminate-all-sessions', {}, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      await loadActiveSessions()
      setError(null) // Clear any previous errors
    } catch (error: any) {
      setError(error.response?.data?.detail || 'Failed to terminate all sessions')
    }
  }

  const openEditModal = (user: User) => {
    setEditingUser(user)
    setUpdateForm({
      first_name: user.first_name || '',
      last_name: user.last_name || '',
      role: user.role,
      active: user.active
    })
    // Reset password change states
    setShowPasswordFields(false)
    setCurrentPassword('')
    setConfirmPasswordEdit('')
    setError(null)
    setShowEditModal(true)
  }

  const openDeleteModal = (user: User) => {
    setDeletingUser(user)
    setShowDeleteModal(true)
  }

  const openDeactivateModal = (user: User) => {
    setDeactivatingUser(user)
    setShowDeactivateModal(true)
  }

  const handleDeactivateUser = async () => {
    if (!deactivatingUser) return

    try {
      await axios.put(`/api/v1/admin/users/${deactivatingUser.id}`, { active: false })
      setShowDeactivateModal(false)
      setDeactivatingUser(null)
      await loadUsers()
    } catch (error: any) {
      setError(error.response?.data?.detail || 'Failed to deactivate user')
    }
  }

  const handleActivateUser = async (user: User) => {
    try {
      await axios.put(`/api/v1/admin/users/${user.id}`, { active: true })
      await loadUsers()
    } catch (error: any) {
      setError(error.response?.data?.detail || 'Failed to activate user')
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString()
  }

  const getRoleColor = (role: string) => {
    switch (role) {
      case 'admin': return 'bg-red-100 text-red-800'
      case 'user': return 'bg-blue-100 text-blue-800'
      case 'view': return 'bg-gray-100 text-gray-800'
      default: return 'bg-gray-100 text-gray-800'
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
                  User Management
                </h1>
                <p className="text-secondary">
                  Manage users, roles, permissions, and active sessions
                </p>
              </div>
              <button
                onClick={loadData}
                disabled={loading}
                className="btn-neutral-tertiary flex items-center space-x-2"
              >
                <span className={`text-white ${loading ? 'animate-spin' : ''}`}>↻</span>
                <span>Refresh</span>
              </button>
            </div>

            {/* Tabs */}
            <div className="border-b border-tertiary">
              <nav className="flex space-x-8">
                {[
                  { id: 'users', label: 'Users', icon: '👥' },
                  { id: 'sessions', label: 'Active Sessions', icon: '🔐' },
                  { id: 'permissions', label: 'Permissions', icon: '🛡️' }
                ].map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id as any)}
                    className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center space-x-2 ${activeTab === tab.id
                      ? 'border-primary text-primary'
                      : 'border-transparent text-secondary hover:text-primary hover:border-gray-300'
                      }`}
                  >
                    <span>{tab.icon}</span>
                    <span>{tab.label}</span>
                  </button>
                ))}
              </nav>
            </div>

            {/* Tab Content */}
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                <span className="ml-3 text-secondary">Loading...</span>
              </div>
            ) : (
              <div className="space-y-6">
                {/* Users Tab */}
                {activeTab === 'users' && (
                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="space-y-4"
                  >
                    <div className="flex justify-between items-center">
                      <h3 className="text-lg font-semibold text-primary">Users ({users.length})</h3>
                      <button
                        onClick={() => {
                          setCreateForm({ email: '', first_name: '', last_name: '', role: 'user', password: '' })
                          setConfirmPassword('')
                          setError(null)
                          setTouchedFields({})
                          setSubmitAttempted(false)
                          setShowCreateModal(true)
                        }}
                        className="btn-crud-create flex items-center space-x-2"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                        </svg>
                        <span>Create User</span>
                      </button>
                    </div>

                    <div className="card overflow-hidden">
                      <div className="overflow-x-auto">
                        <table className="min-w-full divide-y divide-tertiary">
                          <thead className="bg-tertiary">
                            <tr>
                              <th className="px-6 py-3 text-left text-xs font-medium text-secondary uppercase tracking-wider">
                                User
                              </th>
                              <th className="px-6 py-3 text-left text-xs font-medium text-secondary uppercase tracking-wider">
                                Role
                              </th>
                              <th className="px-6 py-3 text-left text-xs font-medium text-secondary uppercase tracking-wider">
                                Status
                              </th>
                              <th className="px-6 py-3 text-left text-xs font-medium text-secondary uppercase tracking-wider">
                                Last Login
                              </th>
                              <th className="px-6 py-3 text-right text-xs font-medium text-secondary uppercase tracking-wider">
                                Actions
                              </th>
                            </tr>
                          </thead>
                          <tbody className="bg-primary divide-y divide-tertiary">
                            {users.map((user) => (
                              <tr key={user.id} className={`hover:bg-tertiary ${!user.active
                                ? 'bg-tertiary opacity-75 border-l-4 border-orange-400'
                                : ''
                                }`}>
                                <td className="px-6 py-4 whitespace-nowrap">
                                  <div>
                                    <div className="text-sm font-medium text-primary">
                                      {user.first_name && user.last_name
                                        ? `${user.first_name} ${user.last_name}`
                                        : user.email
                                      }
                                    </div>
                                    <div className="text-sm text-secondary">{user.email}</div>
                                  </div>
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap">
                                  <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getRoleColor(user.role)}`}>
                                    {user.role}
                                  </span>
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap">
                                  <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${user.active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                                    }`}>
                                    {user.active ? 'Active' : 'Inactive'}
                                  </span>
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-secondary">
                                  {user.last_login_at ? formatDate(user.last_login_at) : 'Never'}
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                  <div className="flex justify-end space-x-2">
                                    <button
                                      onClick={() => openEditModal(user)}
                                      className="text-blue-600 hover:text-blue-900 font-bold text-lg"
                                      title="Edit"
                                    >
                                      ✎
                                    </button>
                                    <button
                                      onClick={() => user.active ? openDeactivateModal(user) : handleActivateUser(user)}
                                      className={user.active
                                        ? "text-yellow-600 hover:text-yellow-800 font-bold text-lg"
                                        : "text-green-600 hover:text-green-900 font-bold text-lg"
                                      }
                                      title={user.active ? "Deactivate" : "Activate"}
                                    >
                                      {user.active ? "⏸" : "▶"}
                                    </button>
                                    <button
                                      onClick={() => openDeleteModal(user)}
                                      className="text-red-600 hover:text-red-900 font-bold text-lg"
                                      title="Delete"
                                    >
                                      ✕
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </motion.div>
                )}

                {/* Active Sessions Tab */}
                {activeTab === 'sessions' && (
                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="space-y-4"
                  >
                    <div className="flex justify-between items-center">
                      <h3 className="text-lg font-semibold text-primary">Active Sessions ({activeSessions.length})</h3>
                      <button
                        type="button"
                        onClick={handleTerminateAllSessions}
                        className="btn-crud-delete flex items-center space-x-2"
                      >
                        <UserX className="w-4 h-4" />
                        <span>Terminate All Sessions</span>
                      </button>
                    </div>

                    <div className="card overflow-hidden">
                      <div className="overflow-x-auto">
                        <table className="min-w-full divide-y divide-tertiary">
                          <thead className="bg-tertiary">
                            <tr>
                              <th className="px-6 py-3 text-left text-xs font-medium text-secondary uppercase tracking-wider">
                                User
                              </th>
                              <th className="px-6 py-3 text-left text-xs font-medium text-secondary uppercase tracking-wider">
                                Status
                              </th>
                              <th className="px-6 py-3 text-left text-xs font-medium text-secondary uppercase tracking-wider">
                                Session Start
                              </th>
                              <th className="px-6 py-3 text-left text-xs font-medium text-secondary uppercase tracking-wider">
                                Last Activity
                              </th>
                              <th className="px-6 py-3 text-left text-xs font-medium text-secondary uppercase tracking-wider">
                                IP Address
                              </th>
                              <th className="px-6 py-3 text-left text-xs font-medium text-secondary uppercase tracking-wider">
                                User Agent
                              </th>
                              <th className="px-6 py-3 text-right text-xs font-medium text-secondary uppercase tracking-wider">
                                Actions
                              </th>
                            </tr>
                          </thead>
                          <tbody className="bg-primary divide-y divide-tertiary">
                            {activeSessions.map((session) => (
                              <tr key={session.id} className="hover:bg-tertiary">
                                <td className="px-6 py-4 whitespace-nowrap">
                                  <div>
                                    <div className="text-sm font-medium text-primary">
                                      {users.find(u => u.id === session.user_id)?.first_name} {users.find(u => u.id === session.user_id)?.last_name || `User ${session.user_id}`}
                                    </div>
                                    <div className="text-sm text-secondary">{session.user_email}</div>
                                  </div>
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap">
                                  <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-800">
                                    Active
                                  </span>
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-secondary">
                                  {formatDate(session.created_at)}
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-secondary">
                                  {formatDate(session.last_activity_at)}
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-secondary">
                                  {session.ip_address || 'N/A'}
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-secondary max-w-xs truncate" title={session.user_agent || 'N/A'}>
                                  {session.user_agent ?
                                    (session.user_agent.length > 50 ?
                                      `${session.user_agent.substring(0, 50)}...` :
                                      session.user_agent
                                    ) : 'N/A'
                                  }
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                  <button
                                    type="button"
                                    onClick={() => handleTerminateSession(session.id.toString())}
                                    className="btn-crud-delete text-xs flex items-center space-x-1"
                                  >
                                    <LogOut className="w-3 h-3" />
                                    <span>Terminate</span>
                                  </button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </motion.div>
                )}

                {/* Permissions Tab */}
                {activeTab === 'permissions' && (
                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="space-y-4"
                  >
                    <h3 className="text-lg font-semibold text-primary">Role-Based Permissions</h3>

                    <div className="card p-6">
                      <div className="space-y-6">
                        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                          <h4 className="font-semibold text-blue-900 mb-2">🛡️ Role-Based Access Control</h4>
                          <p className="text-blue-800 text-sm mb-3">Permissions are managed through user roles:</p>
                          <ul className="space-y-2 text-sm text-blue-800">
                            <li><strong>Admin:</strong> Full system access including admin panel, user management, integration management, and all ETL operations</li>
                            <li><strong>User:</strong> Can view and use dashboards, view ETL status, download logs (no admin panel access)</li>
                            <li><strong>View:</strong> Read-only access to dashboards and basic system information (no admin panel access)</li>
                          </ul>
                        </div>

                        <div>
                          <h4 className="font-semibold text-primary mb-3">Permission Matrix</h4>
                          <div className="overflow-x-auto">
                            <table className="min-w-full divide-y divide-tertiary border border-tertiary rounded-lg">
                              <thead className="bg-tertiary">
                                <tr>
                                  <th className="px-4 py-3 text-left text-xs font-medium text-secondary uppercase">Resource</th>
                                  <th className="px-4 py-3 text-center text-xs font-medium text-secondary uppercase">Admin</th>
                                  <th className="px-4 py-3 text-center text-xs font-medium text-secondary uppercase">User</th>
                                  <th className="px-4 py-3 text-center text-xs font-medium text-secondary uppercase">View</th>
                                </tr>
                              </thead>
                              <tbody className="bg-primary divide-y divide-tertiary">
                                {[
                                  { resource: 'Admin Panel', admin: '✅', user: '❌', view: '❌' },
                                  { resource: 'User Management', admin: '✅', user: '❌', view: '❌' },
                                  { resource: 'System Settings', admin: '✅', user: '❌', view: '❌' },
                                  { resource: 'ETL Operations', admin: '✅', user: '📖', view: '📖' },
                                  { resource: 'Dashboards', admin: '✅', user: '✅', view: '📖' },
                                  { resource: 'Reports', admin: '✅', user: '✅', view: '📖' },
                                  { resource: 'Log Downloads', admin: '✅', user: '✅', view: '❌' }
                                ].map((row, index) => (
                                  <tr key={index}>
                                    <td className="px-4 py-3 text-sm font-medium text-primary">{row.resource}</td>
                                    <td className="px-4 py-3 text-center text-sm">{row.admin}</td>
                                    <td className="px-4 py-3 text-center text-sm">{row.user}</td>
                                    <td className="px-4 py-3 text-center text-sm">{row.view}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                          <div className="mt-4 text-xs text-secondary">
                            <p><strong>Legend:</strong> ✅ Full Access | 📖 Read Only | ❌ No Access</p>
                          </div>
                        </div>
                      </div>
                    </div>
                  </motion.div>
                )}
              </div>
            )}
          </motion.div>
        </main>
      </div>

      {/* Create User Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <motion.div
            key="create-user-modal"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-primary rounded-lg p-6 w-full max-w-md mx-4"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-primary">Create New User</h3>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-secondary hover:text-primary transition-colors"
              >
                ✕
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
                <label className="block text-sm font-medium text-secondary mb-1">Email *</label>
                <input
                  type="email"
                  value={createForm.email}
                  onChange={(e) => {
                    setCreateForm({ ...createForm, email: e.target.value })
                    // Mark as touched only when user starts typing
                    if (e.target.value.length > 0) {
                      setTouchedFields({ ...touchedFields, email: true })
                    }
                  }}
                  className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 bg-primary text-primary ${(touchedFields.email || submitAttempted) && (!createForm.email || !isValidEmail(createForm.email) || !isEmailUnique(createForm.email))
                    ? 'border-red-500 focus:ring-red-500'
                    : 'border-tertiary focus:ring-blue-500'
                    }`}
                  placeholder="user@example.com"
                  autoComplete="new-email"
                  required
                />
                {(touchedFields.email || submitAttempted) && (
                  <>
                    {!createForm.email && <p className="text-red-500 text-xs mt-1">Email is required</p>}
                    {createForm.email && !isValidEmail(createForm.email) && <p className="text-red-500 text-xs mt-1">Please enter a valid email address</p>}
                    {createForm.email && isValidEmail(createForm.email) && !isEmailUnique(createForm.email) && <p className="text-red-500 text-xs mt-1">This email address is already in use</p>}
                  </>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-secondary mb-1">First Name *</label>
                  <input
                    type="text"
                    value={createForm.first_name}
                    onChange={(e) => {
                      setCreateForm({ ...createForm, first_name: e.target.value })
                      // Mark as touched only when user starts typing
                      if (e.target.value.length > 0) {
                        setTouchedFields({ ...touchedFields, first_name: true })
                      }
                    }}
                    className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 bg-primary text-primary ${(touchedFields.first_name || submitAttempted) && !createForm.first_name?.trim()
                      ? 'border-red-500 focus:ring-red-500'
                      : 'border-tertiary focus:ring-blue-500'
                      }`}
                    autoComplete="new-given-name"
                    required
                  />
                  {(touchedFields.first_name || submitAttempted) && !createForm.first_name?.trim() && (
                    <p className="text-red-500 text-xs mt-1">First name is required</p>
                  )}
                </div>
                <div>
                  <label className="block text-sm font-medium text-secondary mb-1">Last Name *</label>
                  <input
                    type="text"
                    value={createForm.last_name}
                    onChange={(e) => {
                      setCreateForm({ ...createForm, last_name: e.target.value })
                      // Mark as touched only when user starts typing
                      if (e.target.value.length > 0) {
                        setTouchedFields({ ...touchedFields, last_name: true })
                      }
                    }}
                    className={`w-full px-3 py-2 border rounded-md focus:ring-2 bg-primary text-primary ${(touchedFields.last_name || submitAttempted) && !createForm.last_name?.trim()
                      ? 'border-red-500 focus:ring-red-500'
                      : 'border-tertiary focus:ring-blue-500'
                      }`}
                    autoComplete="new-family-name"
                    required
                  />
                  {(touchedFields.last_name || submitAttempted) && !createForm.last_name?.trim() && (
                    <p className="text-red-500 text-xs mt-1">Last name is required</p>
                  )}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-secondary mb-1">Role</label>
                <select
                  value={createForm.role}
                  onChange={(e) => setCreateForm({ ...createForm, role: e.target.value })}
                  className="w-full px-3 py-2 border border-tertiary rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-primary text-primary"
                >
                  <option value="view">View</option>
                  <option value="user">User</option>
                  <option value="admin">Admin</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-secondary mb-1">Password *</label>
                <input
                  type="password"
                  value={createForm.password}
                  onChange={(e) => {
                    setCreateForm({ ...createForm, password: e.target.value })
                    // Mark as touched only when user starts typing
                    if (e.target.value.length > 0) {
                      setTouchedFields({ ...touchedFields, password: true })
                    }
                  }}
                  className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 bg-primary text-primary ${(touchedFields.password || submitAttempted) && !createForm.password?.trim()
                    ? 'border-red-500 focus:ring-red-500'
                    : 'border-tertiary focus:ring-blue-500'
                    }`}
                  placeholder="Enter password"
                  autoComplete="new-password"
                  required
                />
                {(touchedFields.password || submitAttempted) && !createForm.password?.trim() && (
                  <p className="text-red-500 text-xs mt-1">Password is required</p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-secondary mb-1">Confirm Password *</label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => {
                    setConfirmPassword(e.target.value)
                    // Mark as touched only when user starts typing
                    if (e.target.value.length > 0) {
                      setTouchedFields({ ...touchedFields, confirm_password: true })
                    }
                  }}
                  className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 bg-primary text-primary ${(touchedFields.confirm_password || submitAttempted) && (!confirmPassword?.trim() || createForm.password !== confirmPassword)
                    ? 'border-red-500 focus:ring-red-500'
                    : 'border-tertiary focus:ring-blue-500'
                    }`}
                  placeholder="Confirm password"
                  autoComplete="new-password"
                  required
                />
                {(touchedFields.confirm_password || submitAttempted) && (
                  <>
                    {!confirmPassword?.trim() && <p className="text-red-500 text-xs mt-1">Please confirm your password</p>}
                    {confirmPassword?.trim() && createForm.password !== confirmPassword && <p className="text-red-500 text-xs mt-1">Passwords do not match</p>}
                  </>
                )}
              </div>
            </div>

            <div className="flex justify-end space-x-3 mt-6 p-4 bg-tertiary border-t border-tertiary rounded-b-lg">
              <button
                onClick={() => setShowCreateModal(false)}
                className="btn-crud-cancel"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateUser}
                className="btn-crud-create"
              >
                Create User
              </button>
            </div>
          </motion.div>
        </div>
      )}

      {/* Edit User Modal */}
      {showEditModal && editingUser && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-primary rounded-lg p-6 w-full max-w-md mx-4"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-primary">Edit User</h3>
              <button
                onClick={() => setShowEditModal(false)}
                className="text-secondary hover:text-primary transition-colors"
              >
                ✕
              </button>
            </div>

            {/* Error Display in Edit Modal */}
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
                <label className="block text-sm font-medium text-secondary mb-1">Email</label>
                <input
                  type="email"
                  value={editingUser.email}
                  disabled
                  className="w-full px-3 py-2 border border-tertiary rounded-md bg-tertiary text-secondary opacity-60"
                />
                <p className="text-xs text-secondary mt-1">Email cannot be changed</p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-secondary mb-1">First Name</label>
                  <input
                    type="text"
                    value={updateForm.first_name || ''}
                    onChange={(e) => setUpdateForm({ ...updateForm, first_name: e.target.value })}
                    className="w-full px-3 py-2 border border-tertiary rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-primary text-primary"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-secondary mb-1">Last Name</label>
                  <input
                    type="text"
                    value={updateForm.last_name || ''}
                    onChange={(e) => setUpdateForm({ ...updateForm, last_name: e.target.value })}
                    className="w-full px-3 py-2 border border-tertiary rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-primary text-primary"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-secondary mb-1">Role</label>
                <select
                  value={updateForm.role || ''}
                  onChange={(e) => setUpdateForm({ ...updateForm, role: e.target.value })}
                  className="w-full px-3 py-2 border border-tertiary rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-primary text-primary"
                >
                  <option value="view">View</option>
                  <option value="user">User</option>
                  <option value="admin">Admin</option>
                </select>
              </div>

              {/* Password Change Section */}
              <div className="border-t border-tertiary pt-4">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-sm font-medium text-secondary">Change Password</h4>
                  <button
                    type="button"
                    onClick={() => setShowPasswordFields(!showPasswordFields)}
                    className="text-blue-600 hover:text-blue-800 text-sm"
                  >
                    {showPasswordFields ? 'Cancel' : 'Change Password'}
                  </button>
                </div>

                {showPasswordFields && (
                  <div className="space-y-3">
                    {/* Hidden dummy field to prevent auto-fill */}
                    <input type="password" style={{ display: 'none' }} tabIndex={-1} autoComplete="off" />
                    <div>
                      <label className="block text-sm font-medium text-secondary mb-1">Current Password</label>
                      <input
                        type="password"
                        value={currentPassword}
                        onChange={(e) => setCurrentPassword(e.target.value)}
                        className="w-full px-3 py-2 border border-tertiary rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-primary text-primary"
                        placeholder="Enter current password"
                        autoComplete="off"
                        data-form-type="other"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-secondary mb-1">New Password</label>
                      <input
                        type="password"
                        value={updateForm.password || ''}
                        onChange={(e) => setUpdateForm({ ...updateForm, password: e.target.value })}
                        className="w-full px-3 py-2 border border-tertiary rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-primary text-primary"
                        placeholder="Enter new password"
                        autoComplete="off"
                        data-form-type="other"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-secondary mb-1">Confirm New Password</label>
                      <input
                        type="password"
                        value={confirmPasswordEdit}
                        onChange={(e) => setConfirmPasswordEdit(e.target.value)}
                        className="w-full px-3 py-2 border border-tertiary rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-primary text-primary"
                        placeholder="Confirm new password"
                        autoComplete="off"
                        data-form-type="other"
                      />
                    </div>
                  </div>
                )}
              </div>

              <div>
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={updateForm.active || false}
                    onChange={(e) => setUpdateForm({ ...updateForm, active: e.target.checked })}
                    className="rounded border-tertiary focus:ring-2 focus:ring-blue-500 bg-primary text-primary"
                  />
                  <span className="text-sm font-medium text-secondary">Active User</span>
                </label>
              </div>
            </div>

            <div className="flex justify-end space-x-3 mt-6 p-4 bg-tertiary border-t border-tertiary rounded-b-lg">
              <button
                onClick={() => setShowEditModal(false)}
                className="btn-crud-cancel"
              >
                Cancel
              </button>
              <button
                onClick={handleUpdateUser}
                className="btn-crud-edit"
              >
                Update User
              </button>
            </div>
          </motion.div>
        </div>
      )}

      {/* Deactivate User Modal */}
      {showDeactivateModal && deactivatingUser && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-primary rounded-lg p-6 w-full max-w-md mx-4"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-yellow-600">
                Deactivate User
              </h3>
              <button
                onClick={() => setShowDeactivateModal(false)}
                className="text-secondary hover:text-primary transition-colors"
              >
                ✕
              </button>
            </div>

            <div className="mb-6">
              <p className="text-secondary mb-2">
                Are you sure you want to deactivate this user? They will no longer be able to access the system.
              </p>
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
                {deactivatingUser.first_name && deactivatingUser.last_name ? (
                  <>
                    <p className="text-sm text-yellow-800">
                      <strong>User:</strong> {deactivatingUser.first_name} {deactivatingUser.last_name}
                    </p>
                    <p className="text-sm text-yellow-800">
                      <strong>Email:</strong> {deactivatingUser.email}
                    </p>
                  </>
                ) : (
                  <p className="text-sm text-yellow-800">
                    <strong>User:</strong> {deactivatingUser.email}
                  </p>
                )}
                <p className="text-sm text-yellow-800">
                  <strong>Role:</strong> {deactivatingUser.role}
                </p>
              </div>
            </div>

            <div className="flex justify-end space-x-3 p-4 bg-tertiary border-t border-tertiary rounded-b-lg">
              <button
                onClick={() => setShowDeactivateModal(false)}
                className="btn-crud-cancel"
              >
                Cancel
              </button>
              <button
                onClick={handleDeactivateUser}
                className="btn-status-warning"
              >
                Deactivate
              </button>
            </div>
          </motion.div>
        </div>
      )}

      {/* Delete User Modal */}
      {showDeleteModal && deletingUser && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-primary rounded-lg p-6 w-full max-w-md mx-4"
          >
            <h3 className="text-lg font-semibold text-red-600 mb-4">Delete User</h3>

            <div className="mb-6">
              <p className="text-secondary mb-2">
                Are you sure you want to delete this user? This action cannot be undone.
              </p>
              <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                {deletingUser.first_name && deletingUser.last_name ? (
                  <>
                    <p className="text-sm text-red-800">
                      <strong>User:</strong> {deletingUser.first_name} {deletingUser.last_name}
                    </p>
                    <p className="text-sm text-red-800">
                      <strong>Email:</strong> {deletingUser.email}
                    </p>
                  </>
                ) : (
                  <p className="text-sm text-red-800">
                    <strong>User:</strong> {deletingUser.email}
                  </p>
                )}
                <p className="text-sm text-red-800">
                  <strong>Role:</strong> {deletingUser.role}
                </p>
              </div>
            </div>

            <div className="flex justify-end space-x-3">
              <button
                onClick={() => setShowDeleteModal(false)}
                className="btn-crud-cancel"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteUser}
                className="btn-crud-delete"
              >
                Delete User
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </div>
  )
}
