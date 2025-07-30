import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import Header from '../components/Header'
import CollapsedSidebar from '../components/CollapsedSidebar'

export default function UserPreferencesPage() {
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
              <div className="flex items-center space-x-3">
                <button
                  onClick={() => navigate('/settings')}
                  className="text-secondary hover:text-primary transition-colors"
                >
                  ← Back to Settings
                </button>
              </div>
              <h1 className="text-3xl font-bold text-primary">
                User Preferences
              </h1>
              <p className="text-secondary">
                Manage your account settings and personal preferences
              </p>
            </div>

            {/* Coming Soon Message */}
            <div className="card p-8 text-center">
              <div className="w-16 h-16 bg-gradient-to-br from-emerald-500 to-teal-500 rounded-full flex items-center justify-center mx-auto mb-4">
                <span className="text-white text-2xl">👤</span>
              </div>
              <h3 className="text-xl font-semibold text-primary mb-2">Coming Soon</h3>
              <p className="text-secondary mb-6">
                User preferences management is currently under development. This feature will allow you to:
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-left">
                <div className="space-y-2">
                  <h4 className="font-medium text-primary">Account Settings</h4>
                  <ul className="text-sm text-secondary space-y-1">
                    <li>• Update profile information</li>
                    <li>• Change password</li>
                    <li>• Manage email preferences</li>
                  </ul>
                </div>
                <div className="space-y-2">
                  <h4 className="font-medium text-primary">Display Preferences</h4>
                  <ul className="text-sm text-secondary space-y-1">
                    <li>• Default dashboard view</li>
                    <li>• Date and time format</li>
                    <li>• Language settings</li>
                  </ul>
                </div>
              </div>
            </div>
          </motion.div>
        </main>
      </div>
    </div>
  )
}
