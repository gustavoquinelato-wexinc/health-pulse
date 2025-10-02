import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import clientLogger from '../utils/clientLogger'

const navigationItems = [
  {
    name: 'Dashboard',
    icon: '📊',
    active: true,
    badge: null
  },
  {
    name: 'DORA Metrics',
    icon: '🚀',
    active: false,
    badge: 'New'
  },
  {
    name: 'GitHub Analytics',
    icon: '📈',
    active: false,
    badge: null
  },
  {
    name: 'Portfolio View',
    icon: '📋',
    active: false,
    badge: null
  },
  {
    name: 'Executive KPIs',
    icon: '👔',
    active: false,
    badge: '3'
  },
  {
    name: 'ETL Jobs',
    icon: '⚙️',
    active: false,
    badge: null
  }
]

const recentItems = [
  'Q4 Performance Review',
  'Team Velocity Analysis',
  'Deployment Frequency Report'
]

export default function Sidebar() {

  return (
    <aside className="fixed left-0 top-16 h-[calc(100vh-4rem)] w-64 sidebar-container border-r border-default overflow-y-auto">
      <div className="p-4 space-y-6">
        {/* Navigation */}
        <div className="space-y-2">
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wider">
            Navigation
          </h2>
          <nav className="space-y-1">
            {navigationItems.map((item, index) => (
              <motion.div
                key={item.name}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.1 }}
              >
                <Link
                  to={
                    item.name === 'Dashboard' ? '/home'
                      : item.name === 'DORA Metrics' ? '/dora'
                        : item.name === 'GitHub Analytics' ? '/engineering'
                          : item.name === 'Portfolio View' ? '/engineering'
                            : item.name === 'Executive KPIs' ? '/engineering'
                              : item.name === 'ETL Jobs' ? '/admin'
                                : '/home'
                  }
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${item.active
                    ? 'shadow-lg text-[color:var(--on-gradient-1-2)]'
                    : 'text-secondary hover:bg-tertiary hover:text-primary'
                    }`}
                  style={item.active ? { background: 'var(--gradient-1-2)' } : {}}
                >
                  <div className="flex items-center space-x-3">
                    <span className="text-lg">{item.icon}</span>
                    <span>{item.name}</span>
                  </div>
                  {item.badge && (
                    <span className={`px-2 py-1 text-xs rounded-full ${item.badge === 'New'
                      ? 'bg-emerald-100 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400'
                      : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400'
                      }`}>
                      {item.badge}
                    </span>
                  )}
                </Link>
              </motion.div>
            ))}
          </nav>
        </div>

        {/* Recent Items */}
        <div className="space-y-2">
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wider">
            Recent
          </h2>
          <div className="space-y-1">
            {recentItems.map((item, index) => (
              <motion.button
                key={item}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: (navigationItems.length + index) * 0.1 }}
                className="w-full text-left px-3 py-2 rounded-lg text-sm text-secondary hover:bg-tertiary hover:text-primary transition-colors"
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                <div className="flex items-center space-x-2">
                  <div className="w-2 h-2 bg-blue-400 rounded-full"></div>
                  <span className="truncate">{item}</span>
                </div>
              </motion.button>
            ))}
          </div>
        </div>

        {/* Quick Actions */}
        <div className="space-y-2">
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wider">
            Quick Actions
          </h2>
          <div className="space-y-2">
            <motion.button
              className="btn btn-primary w-full text-sm py-2"
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => clientLogger.logUserAction('run_etl_job', 'sidebar_quick_action')}
            >
              🚀 Run ETL Job
            </motion.button>
            <motion.button
              className="btn btn-secondary w-full text-sm py-2"
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => clientLogger.logUserAction('generate_report', 'sidebar_quick_action')}
            >
              📊 Generate Report
            </motion.button>
          </div>
        </div>

        {/* Settings Section */}
        <div className="space-y-2">
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wider">
            Settings
          </h2>
          <div className="space-y-1">
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.6 }}
            >
              <Link
                to="/settings"
                className="w-full flex items-center space-x-3 px-3 py-2 rounded-lg text-sm text-secondary hover:bg-tertiary hover:text-primary transition-colors"
              >
                <span className="text-lg">🔧</span>
                <span>Settings</span>
              </Link>
            </motion.div>
          </div>
        </div>

        {/* Status Card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.8 }}
          className="card p-4 space-y-3"
        >
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-primary">System Status</h3>
            <div className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse"></div>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-muted">ETL Service</span>
              <span className="text-emerald-600">Healthy</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">Database</span>
              <span className="text-emerald-600">Connected</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">Last Sync</span>
              <span className="text-secondary">2 min ago</span>
            </div>
          </div>
        </motion.div>


      </div>
    </aside>
  )
}
