import { motion } from 'framer-motion'
import CollapsedSidebar from '../components/CollapsedSidebar'
import Header from '../components/Header'
import { useAuth } from '../contexts/AuthContext'

export default function UserPreferencesPage() {
  const { user } = useAuth()

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
              <h1 className="text-3xl font-bold text-primary">Profile Settings</h1>
              <p className="text-secondary">Manage your account preferences</p>
            </div>

            <div className="card p-6">
              <h2 className="text-xl font-semibold text-primary mb-4">User Information</h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-secondary mb-1">Email</label>
                  <input
                    type="email"
                    value={user?.email || ''}
                    disabled
                    className="input w-full opacity-50"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-secondary mb-1">Role</label>
                  <input
                    type="text"
                    value={user?.role || ''}
                    disabled
                    className="input w-full opacity-50"
                  />
                </div>
              </div>
            </div>

            <div className="card p-6">
              <h2 className="text-xl font-semibold text-primary mb-4">Preferences</h2>
              <p className="text-secondary">User preference settings will be implemented here.</p>
            </div>
          </motion.div>
        </main>
      </div>
    </div>
  )
}
