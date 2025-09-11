import { motion } from 'framer-motion'
import { Bell } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import CollapsedSidebar from '../components/CollapsedSidebar'
import Header from '../components/Header'
import useDocumentTitle from '../hooks/useDocumentTitle'

export default function NotificationsPage() {
  const navigate = useNavigate()

  // Set document title
  useDocumentTitle('Notifications')

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
                Notifications
              </h1>
              <p className="text-secondary">
                Configure alerts and notification preferences
              </p>
            </div>

            {/* Coming Soon Message */}
            <div className="card p-8 text-center">
              <div className="w-16 h-16 bg-gradient-to-br from-color-4 to-color-5 rounded-full flex items-center justify-center mx-auto mb-4">
                <Bell className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-xl font-semibold text-primary mb-2">Coming Soon</h3>
              <p className="text-secondary mb-6">
                Notification management is currently under development. This feature will allow you to:
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-left">
                <div className="space-y-2">
                  <h4 className="font-medium text-primary">Alert Preferences</h4>
                  <ul className="text-sm text-secondary space-y-1">
                    <li>• ETL job completion alerts</li>
                    <li>• System maintenance notifications</li>
                    <li>• Error and failure alerts</li>
                  </ul>
                </div>
                <div className="space-y-2">
                  <h4 className="font-medium text-primary">Delivery Methods</h4>
                  <ul className="text-sm text-secondary space-y-1">
                    <li>• Email notifications</li>
                    <li>• In-app notifications</li>
                    <li>• Slack integration</li>
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
