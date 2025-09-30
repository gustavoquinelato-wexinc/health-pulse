import { motion } from 'framer-motion'
import CollapsedSidebar from '../components/CollapsedSidebar'
import Header from '../components/Header'
import { useAuth } from '../contexts/AuthContext'

export default function HomePage() {
  const { user } = useAuth()

  return (
    <div className="min-h-screen">
      {/* Header */}
      <Header />

      <div className="flex">
        {/* Collapsed Sidebar */}
        <CollapsedSidebar />

        {/* Main Content */}
        <main className="flex-1 p-6 ml-16">
          {/* Style Navigation Link */}
          <div className="mb-6 flex flex-wrap gap-4">
            <a
              href="/home5.html"
              target="_blank"
              rel="noopener noreferrer"
              className="px-4 py-2 bg-emerald-500 text-white rounded hover:bg-emerald-600 transition-colors"
            >
              Collapsed Sidebar Style
            </a>
          </div>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="space-y-6"
          >
            {/* Welcome Section */}
            <div className="space-y-2">
              <h1 className="text-3xl font-bold text-primary">
                Welcome to ETL Management! 🚀
              </h1>
              <p className="text-secondary">
                Your data pipeline control center
              </p>
            </div>

            {/* Quick Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
                className="card p-6"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-secondary">Active Jobs</p>
                    <p className="text-2xl font-bold text-primary">3</p>
                  </div>
                  <div className="w-12 h-12 rounded-lg flex items-center justify-center" style={{ background: 'var(--gradient-1-2)' }}>
                    <svg className="w-6 h-6" style={{ color: 'var(--on-gradient-1-2)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                  </div>
                </div>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="card p-6"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-secondary">Success Rate</p>
                    <p className="text-2xl font-bold text-primary">98.5%</p>
                  </div>
                  <div className="w-12 h-12 rounded-lg flex items-center justify-center" style={{ background: 'var(--gradient-2-3)' }}>
                    <svg className="w-6 h-6" style={{ color: 'var(--on-gradient-2-3)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </div>
                </div>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
                className="card p-6"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-secondary">Data Processed</p>
                    <p className="text-2xl font-bold text-primary">2.4TB</p>
                  </div>
                  <div className="w-12 h-12 rounded-lg flex items-center justify-center" style={{ background: 'var(--gradient-3-4)' }}>
                    <svg className="w-6 h-6" style={{ color: 'var(--on-gradient-3-4)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
                    </svg>
                  </div>
                </div>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 }}
                className="card p-6"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-secondary">Vector Queue</p>
                    <p className="text-2xl font-bold text-primary">127</p>
                  </div>
                  <div className="w-12 h-12 rounded-lg flex items-center justify-center" style={{ background: 'var(--gradient-4-5)' }}>
                    <svg className="w-6 h-6" style={{ color: 'var(--on-gradient-4-5)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                  </div>
                </div>
              </motion.div>
            </div>

            {/* Recent Activity */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 }}
              className="card p-6"
            >
              <h2 className="text-xl font-semibold text-primary mb-4">Recent Activity</h2>
              <div className="space-y-4">
                <div className="flex items-center space-x-4 p-3 bg-tertiary rounded-lg">
                  <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-primary">Jira Sync completed successfully</p>
                    <p className="text-xs text-secondary">2 minutes ago</p>
                  </div>
                </div>
                <div className="flex items-center space-x-4 p-3 bg-tertiary rounded-lg">
                  <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-primary">GitHub Sync in progress</p>
                    <p className="text-xs text-secondary">5 minutes ago</p>
                  </div>
                </div>
                <div className="flex items-center space-x-4 p-3 bg-tertiary rounded-lg">
                  <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-primary">Vectorization batch processed</p>
                    <p className="text-xs text-secondary">15 minutes ago</p>
                  </div>
                </div>
              </div>
            </motion.div>

            {/* Quick Actions */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6 }}
              className="card p-6"
            >
              <h2 className="text-xl font-semibold text-primary mb-4">Quick Actions</h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <button className="btn-crud-create p-4 rounded-lg text-left">
                  <div className="flex items-center space-x-3">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                    </svg>
                    <span className="font-medium">Run Manual Sync</span>
                  </div>
                </button>
                <button className="btn-crud-edit p-4 rounded-lg text-left">
                  <div className="flex items-center space-x-3">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                    </svg>
                    <span className="font-medium">View Analytics</span>
                  </div>
                </button>
                <button className="btn-neutral-primary p-4 rounded-lg text-left">
                  <div className="flex items-center space-x-3">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    <span className="font-medium">Manage Settings</span>
                  </div>
                </button>
              </div>
            </motion.div>
          </motion.div>
        </main>
      </div>
    </div>
  )
}
