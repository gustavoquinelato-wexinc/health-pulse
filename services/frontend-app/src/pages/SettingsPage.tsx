import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import CollapsedSidebar from '../components/CollapsedSidebar'
import Header from '../components/Header'

export default function SettingsPage() {
  const navigate = useNavigate()
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
                Settings
              </h1>
              <p className="text-secondary">
                Configure your Pulse platform preferences
              </p>
            </div>

            {/* Settings Overview */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
                className="card p-6 hover:shadow-lg transition-shadow cursor-pointer"
                onClick={() => navigate('/settings/color-scheme')}
              >
                <div className="flex items-center space-x-3 mb-4">
                  <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-violet-500 rounded-lg flex items-center justify-center">
                    <span className="text-white text-lg">🎨</span>
                  </div>
                  <h3 className="text-lg font-semibold text-primary">Color Scheme</h3>
                </div>
                <p className="text-secondary text-sm">
                  Customize your platform's color palette and theme preferences
                </p>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="card p-6 hover:shadow-lg transition-shadow cursor-pointer opacity-50"
              >
                <div className="flex items-center space-x-3 mb-4">
                  <div className="w-10 h-10 bg-gradient-to-br from-emerald-500 to-teal-500 rounded-lg flex items-center justify-center">
                    <span className="text-white text-lg">👤</span>
                  </div>
                  <h3 className="text-lg font-semibold text-primary">User Preferences</h3>
                </div>
                <p className="text-secondary text-sm">
                  Manage your account settings and personal preferences
                </p>
                <span className="text-xs text-muted mt-2 block">Coming Soon</span>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
                className="card p-6 hover:shadow-lg transition-shadow cursor-pointer opacity-50"
              >
                <div className="flex items-center space-x-3 mb-4">
                  <div className="w-10 h-10 bg-gradient-to-br from-orange-500 to-red-500 rounded-lg flex items-center justify-center">
                    <span className="text-white text-lg">🔔</span>
                  </div>
                  <h3 className="text-lg font-semibold text-primary">Notifications</h3>
                </div>
                <p className="text-secondary text-sm">
                  Configure alerts and notification preferences
                </p>
                <span className="text-xs text-muted mt-2 block">Coming Soon</span>
              </motion.div>
            </div>
          </motion.div>
        </main>
      </div>
    </div>
  )
}
