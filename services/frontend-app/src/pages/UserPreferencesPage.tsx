import axios from 'axios'
import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import CollapsedSidebar from '../components/CollapsedSidebar'
import Header from '../components/Header'
import { useAuth } from '../contexts/AuthContext'
import useDocumentTitle from '../hooks/useDocumentTitle'
import clientLogger from '../utils/clientLogger'

interface ProfileData {
  id: number
  email: string
  first_name?: string
  last_name?: string
  role: string
  auth_provider: string
  theme_mode: string
  profile_image_filename?: string
  last_login_at?: string
}

export default function UserPreferencesPage() {
  const { user } = useAuth()
  const [profileData, setProfileData] = useState<ProfileData | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'profile' | 'password'>('profile')

  // Profile form state
  const [profileForm, setProfileForm] = useState({
    first_name: '',
    last_name: ''
  })
  const [profileLoading, setProfileLoading] = useState(false)
  const [profileMessage, setProfileMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)

  // Password form state
  const [passwordForm, setPasswordForm] = useState({
    current_password: '',
    new_password: '',
    confirm_password: ''
  })
  const [passwordLoading, setPasswordLoading] = useState(false)
  const [passwordMessage, setPasswordMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)

  // Image upload state
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [imageMessage, setImageMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)

  // Set document title
  useDocumentTitle('Profile')

  // Helper function to get user initials from first and last name
  const getUserInitials = (profileData: ProfileData | null) => {
    if (!profileData) return 'U'

    // Try to use first_name and last_name if available
    if (profileData.first_name && profileData.last_name) {
      return (profileData.first_name[0] + profileData.last_name[0]).toUpperCase()
    } else if (profileData.first_name) {
      return profileData.first_name[0].toUpperCase()
    } else if (profileData.last_name) {
      return profileData.last_name[0].toUpperCase()
    } else {
      // Fallback to email
      return profileData.email?.[0]?.toUpperCase() || 'U'
    }
  }

  // Helper function to get profile image URL
  const getProfileImageUrl = (profileData: ProfileData | null) => {
    if (profileData?.profile_image_filename && profileData?.email) {
      // Generate user folder using exact email (sanitized for filesystem)
      const userFolder = profileData.email.toLowerCase().replace('@', '_at_').replace(/\./g, '_').replace(/-/g, '_')
      // Use cache busting to ensure fresh images
      const timestamp = Date.now()
      // Use client-specific folder structure: /assets/[client]/users/[email]/[filename]
      return `/assets/wex/users/${userFolder}/${profileData.profile_image_filename}?t=${timestamp}`
    }
    return null
  }

  // Load profile data on component mount
  useEffect(() => {
    loadProfileData()
  }, [])

  const getAuthToken = () => {
    // Check localStorage first
    let token = localStorage.getItem('pulse_token')
    if (token) return token

    // Check cookies as fallback
    const cookies = document.cookie.split(';')
    for (let cookie of cookies) {
      const [name, value] = cookie.trim().split('=')
      if (name === 'pulse_token') {
        return value
      }
    }
    return null
  }

  const loadProfileData = async () => {
    try {
      setLoading(true)
      const token = getAuthToken()

      if (!token) {
        throw new Error('No authentication token found')
      }

      const response = await axios.get('/api/v1/user/profile', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      const data = response.data
      setProfileData(data)
      setProfileForm({
        first_name: data.first_name || '',
        last_name: data.last_name || ''
      })

      clientLogger.info('Profile data loaded successfully')
    } catch (error) {
      clientLogger.error('Failed to load profile data:', error)
      setProfileMessage({ type: 'error', text: 'Failed to load profile data' })
    } finally {
      setLoading(false)
    }
  }



  const handleProfileSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setProfileLoading(true)
    setProfileMessage(null)
    setImageMessage(null)

    try {
      const token = getAuthToken()
      if (!token) {
        throw new Error('No authentication token found')
      }

      // First, update profile data
      await axios.put('/api/v1/user/profile', profileForm, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      // Then, upload image if one is selected
      if (selectedFile) {
        const formData = new FormData()
        formData.append('profile_image', selectedFile)

        await axios.post('/api/v1/user/profile-image', formData, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'multipart/form-data'
          },
          onUploadProgress: (progressEvent) => {
            if (progressEvent.total) {
              const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total)
              setUploadProgress(progress)
            }
          }
        })

        // Clear selected file after successful upload
        setSelectedFile(null)
        setUploadProgress(0)

        // Dispatch custom event to notify header of image update
        const imageUpdateEvent = new CustomEvent('profileImageUpdated', {
          detail: { userId: profileData?.id }
        })
        window.dispatchEvent(imageUpdateEvent)
      }

      setProfileMessage({ type: 'success', text: selectedFile ? 'Profile and image updated successfully!' : 'Profile updated successfully!' })
      await loadProfileData() // Reload profile data
      clientLogger.info('Profile updated successfully')
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || 'Failed to update profile'
      setProfileMessage({ type: 'error', text: errorMessage })
      clientLogger.error('Failed to update profile:', error)
    } finally {
      setProfileLoading(false)
    }
  }

  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setPasswordLoading(true)
    setPasswordMessage(null)

    // Client-side validation
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      setPasswordMessage({ type: 'error', text: 'New password and confirmation do not match' })
      setPasswordLoading(false)
      return
    }

    if (passwordForm.new_password.length < 8) {
      setPasswordMessage({ type: 'error', text: 'Password must be at least 8 characters long' })
      setPasswordLoading(false)
      return
    }

    try {
      const token = getAuthToken()
      if (!token) {
        throw new Error('No authentication token found')
      }

      await axios.post('/api/v1/user/change-password', passwordForm, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      setPasswordMessage({ type: 'success', text: 'Password changed successfully!' })
      setPasswordForm({
        current_password: '',
        new_password: '',
        confirm_password: ''
      })
      clientLogger.info('Password changed successfully')
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || 'Failed to change password'
      setPasswordMessage({ type: 'error', text: errorMessage })
      clientLogger.error('Failed to change password:', error)
    } finally {
      setPasswordLoading(false)
    }
  }

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]

    // Clear any previous errors
    setImageMessage(null)

    if (file) {
      // Validate file type - only image files allowed
      if (!file.type.startsWith('image/')) {
        setImageMessage({ type: 'error', text: 'Please select an image file only' })
        setSelectedFile(null)
        // Clear the input
        event.target.value = ''
        return
      }

      // Validate file size (max 5MB)
      if (file.size > 5 * 1024 * 1024) {
        setImageMessage({ type: 'error', text: 'File size must be less than 5MB' })
        setSelectedFile(null)
        // Clear the input
        event.target.value = ''
        return
      }

      setSelectedFile(file)
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
              <div className="text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
                <p className="text-secondary">Loading profile...</p>
              </div>
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
            <div className="space-y-2">
              <h1 className="text-3xl font-bold text-primary">
                Profile Settings
              </h1>
              <p className="text-secondary">
                Manage your personal account settings and preferences
              </p>
            </div>

            {/* User Information Card */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="card p-6"
            >
              <div className="flex items-center space-x-4 mb-6">
                {getProfileImageUrl(profileData) ? (
                  <img
                    src={getProfileImageUrl(profileData)!}
                    alt="Profile"
                    className="w-16 h-16 rounded-full object-cover border-2 border-tertiary"
                  />
                ) : (
                  <div className="w-16 h-16 rounded-full flex items-center justify-center" style={{ background: 'linear-gradient(135deg, var(--color-3), var(--color-4))' }}>
                    <span className="text-white text-2xl font-medium">
                      {getUserInitials(profileData)}
                    </span>
                  </div>
                )}
                <div>
                  <h2 className="text-xl font-semibold text-primary">
                    {profileData?.first_name && profileData?.last_name
                      ? `${profileData.first_name} ${profileData.last_name}`
                      : profileData?.email || 'User'}
                  </h2>
                  <p className="text-secondary">{profileData?.email}</p>
                  <div className="flex items-center space-x-2 mt-1">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200">
                      {profileData?.role}
                    </span>
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
                      {profileData?.auth_provider === 'local' ? 'Local Account' : 'OKTA'}
                    </span>
                  </div>
                </div>
              </div>
            </motion.div>

            {/* Tabs */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="card"
            >
              <div className="border-b border-tertiary">
                <nav className="flex space-x-8 px-6">
                  {[
                    { id: 'profile', label: 'Profile Information', icon: '👤' },
                    { id: 'password', label: 'Password', icon: '🔒' }
                  ].map((tab) => (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id as any)}
                      className={`py-4 px-1 border-b-2 font-medium text-sm flex items-center space-x-2 ${activeTab === tab.id
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

              <div className="p-6">
                {/* Profile Information Tab */}
                {activeTab === 'profile' && (
                  <motion.div
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.3 }}
                  >
                    <h3 className="text-lg font-semibold text-primary mb-4">Profile Information</h3>

                    {profileMessage && (
                      <div className={`mb-4 p-3 rounded-md ${profileMessage.type === 'success'
                        ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                        : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                        }`}>
                        {profileMessage.text}
                      </div>
                    )}

                    {imageMessage && (
                      <div className={`mb-4 p-3 rounded-md ${imageMessage.type === 'success'
                        ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                        : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                        }`}>
                        {imageMessage.text}
                      </div>
                    )}

                    <form onSubmit={handleProfileSubmit} className="space-y-4">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                          <label htmlFor="first_name" className="block text-sm font-medium text-primary mb-1">
                            First Name
                          </label>
                          <input
                            type="text"
                            id="first_name"
                            value={profileForm.first_name}
                            onChange={(e) => setProfileForm({ ...profileForm, first_name: e.target.value })}
                            className="w-full px-3 py-2 border border-default rounded-md bg-secondary text-primary focus:outline-none focus:ring-2 focus:ring-blue-500"
                            placeholder="Enter your first name"
                          />
                        </div>

                        <div>
                          <label htmlFor="last_name" className="block text-sm font-medium text-primary mb-1">
                            Last Name
                          </label>
                          <input
                            type="text"
                            id="last_name"
                            value={profileForm.last_name}
                            onChange={(e) => setProfileForm({ ...profileForm, last_name: e.target.value })}
                            className="w-full px-3 py-2 border border-default rounded-md bg-secondary text-primary focus:outline-none focus:ring-2 focus:ring-blue-500"
                            placeholder="Enter your last name"
                          />
                        </div>
                      </div>

                      <div>
                        <label htmlFor="email" className="block text-sm font-medium text-primary mb-1">
                          Email Address
                        </label>
                        <input
                          type="email"
                          id="email"
                          value={profileData?.email || ''}
                          disabled
                          className="w-full px-3 py-2 border border-default rounded-md bg-tertiary text-muted cursor-not-allowed"
                          placeholder="Enter your email address"
                        />
                        <p className="text-xs text-secondary mt-1">Email address cannot be changed</p>
                      </div>

                      {/* Profile Image Upload */}
                      <div className="p-4 border border-tertiary rounded-md bg-secondary">
                        <h4 className="text-md font-medium text-primary mb-3">Profile Image</h4>

                        <div className="space-y-4">
                          {/* File Upload */}
                          <div>
                            <label className="block text-sm font-medium text-secondary mb-2">
                              {getProfileImageUrl(profileData) ? 'Replace Profile Image' : 'Upload Profile Image'}
                            </label>
                            <input
                              type="file"
                              accept="image/*"
                              onChange={handleFileSelect}
                              className="w-full px-3 py-2 border border-tertiary rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                            <p className="text-xs text-secondary mt-1">
                              Supported formats: JPG, PNG, GIF, WebP. Max size: 5MB
                            </p>
                          </div>

                          {/* File Preview */}
                          {selectedFile && (
                            <div>
                              <label className="block text-sm font-medium text-secondary mb-2">Selected Image</label>
                              <div className="flex items-center space-x-3">
                                <img
                                  src={URL.createObjectURL(selectedFile)}
                                  alt="Profile preview"
                                  className="h-16 w-16 rounded-full object-cover border border-tertiary"
                                />
                                <div className="text-sm text-secondary">
                                  <p>Name: {selectedFile.name}</p>
                                  <p>Size: {(selectedFile.size / 1024 / 1024).toFixed(2)} MB</p>
                                  <p className="text-blue-600">Ready to upload with profile update</p>
                                </div>
                              </div>
                            </div>
                          )}

                          {/* Upload Progress */}
                          {profileLoading && uploadProgress > 0 && (
                            <div>
                              <div className="flex justify-between text-sm text-secondary mb-1">
                                <span>Uploading image...</span>
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
                      </div>

                      <div className="flex justify-end">
                        <button
                          type="submit"
                          disabled={profileLoading}
                          className="btn-crud-create flex items-center space-x-2"
                        >
                          {profileLoading && <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>}
                          <span>
                            {profileLoading
                              ? (selectedFile ? 'Updating Profile & Image...' : 'Updating Profile...')
                              : (selectedFile ? 'Update Profile & Image' : 'Update Profile')
                            }
                          </span>
                        </button>
                      </div>
                    </form>
                  </motion.div>
                )}

                {/* Password Tab */}
                {activeTab === 'password' && (
                  <motion.div
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.3 }}
                  >
                    <h3 className="text-lg font-semibold text-primary mb-4">Change Password</h3>

                    {profileData?.auth_provider !== 'local' ? (
                      <div className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200 p-4 rounded-md">
                        <p className="font-medium">Password change not available</p>
                        <p className="text-sm mt-1">
                          Your account uses {profileData?.auth_provider === 'okta' ? 'OKTA' : 'external'} authentication.
                          Please change your password through your organization's identity provider.
                        </p>
                      </div>
                    ) : (
                      <>
                        {passwordMessage && (
                          <div className={`mb-4 p-3 rounded-md ${passwordMessage.type === 'success'
                            ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                            : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                            }`}>
                            {passwordMessage.text}
                          </div>
                        )}

                        <form onSubmit={handlePasswordSubmit} className="space-y-4">
                          <div>
                            <label htmlFor="current_password" className="block text-sm font-medium text-primary mb-1">
                              Current Password
                            </label>
                            <input
                              type="password"
                              id="current_password"
                              value={passwordForm.current_password}
                              onChange={(e) => setPasswordForm({ ...passwordForm, current_password: e.target.value })}
                              className="w-full px-3 py-2 border border-default rounded-md bg-secondary text-primary focus:outline-none focus:ring-2 focus:ring-blue-500"
                              placeholder="Enter your current password"
                              required
                            />
                          </div>

                          <div>
                            <label htmlFor="new_password" className="block text-sm font-medium text-primary mb-1">
                              New Password
                            </label>
                            <input
                              type="password"
                              id="new_password"
                              value={passwordForm.new_password}
                              onChange={(e) => setPasswordForm({ ...passwordForm, new_password: e.target.value })}
                              className="w-full px-3 py-2 border border-default rounded-md bg-secondary text-primary focus:outline-none focus:ring-2 focus:ring-blue-500"
                              placeholder="Enter your new password"
                              required
                              minLength={8}
                            />
                            <p className="text-xs text-secondary mt-1">Password must be at least 8 characters long</p>
                          </div>

                          <div>
                            <label htmlFor="confirm_password" className="block text-sm font-medium text-primary mb-1">
                              Confirm New Password
                            </label>
                            <input
                              type="password"
                              id="confirm_password"
                              value={passwordForm.confirm_password}
                              onChange={(e) => setPasswordForm({ ...passwordForm, confirm_password: e.target.value })}
                              className="w-full px-3 py-2 border border-default rounded-md bg-secondary text-primary focus:outline-none focus:ring-2 focus:ring-blue-500"
                              placeholder="Confirm your new password"
                              required
                            />
                          </div>

                          <div className="flex justify-end">
                            <button
                              type="submit"
                              disabled={passwordLoading}
                              className="btn-crud-create flex items-center space-x-2"
                            >
                              {passwordLoading && <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>}
                              <span>{passwordLoading ? 'Changing...' : 'Change Password'}</span>
                            </button>
                          </div>
                        </form>
                      </>
                    )}
                  </motion.div>
                )}


              </div>
            </motion.div>
          </motion.div>
        </main>
      </div>
    </div>
  )
}
