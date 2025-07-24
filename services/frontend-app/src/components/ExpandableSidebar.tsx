import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

const navigationItems = [
  {
    id: 'home',
    label: 'Home',
    icon: '🏠',
    path: '/home-option-b'
  },
  {
    id: 'dora',
    label: 'DORA Metrics',
    icon: '📊',
    path: '/dora',
    subItems: [
      { id: 'deployment-frequency', label: 'Deployment Frequency', path: '/dora/deployment-frequency' },
      { id: 'lead-time', label: 'Lead Time for Changes', path: '/dora/lead-time' },
      { id: 'time-to-restore', label: 'Time to Restore', path: '/dora/time-to-restore' },
      { id: 'change-failure-rate', label: 'Change Failure Rate', path: '/dora/change-failure-rate' }
    ]
  },
  {
    id: 'engineering',
    label: 'Engineering Analytics',
    icon: '⚙️',
    path: '/engineering'
  }
]

const quickActions = [
  { name: 'Run ETL Job', icon: '🚀', action: () => console.log('Run ETL Job') },
  { name: 'Generate Report', icon: '📊', action: () => console.log('Generate Report') }
]

const recentItems = [
  'Q4 Performance Review',
  'Team Velocity Analysis',
  'Deployment Frequency Report'
]

export default function ExpandableSidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const [isExpanded, setIsExpanded] = useState(false)
  const [isPinned, setIsPinned] = useState(false)

  const sidebarWidth = isExpanded || isPinned ? '16rem' : '4rem'

  useEffect(() => {
    document.documentElement.style.setProperty('--sidebar-width', sidebarWidth)
  }, [sidebarWidth])

  const handleNavClick = (path: string) => {
    console.log('Navigating to:', path)
    navigate(path)
  }

  const isActive = (item: any) => {
    if (item.path === '/home' && location.pathname === '/home') return true
    if (item.path !== '/home' && location.pathname.startsWith(item.path)) return true
    if (item.subItems) {
      return item.subItems.some((subItem: any) => location.pathname === subItem.path)
    }
    return false
  }

  return (
    <motion.aside
      className="fixed left-0 top-16 h-[calc(100vh-4rem)] bg-secondary border-r border-default shadow-lg z-40 overflow-hidden"
      animate={{ width: sidebarWidth }}
      transition={{ duration: 0.3, ease: 'easeInOut' }}
    >
      <div className="flex flex-col h-full">
        {/* Main Content */}
        <div className="flex-1 p-4 space-y-6">
          {/* Header */}
          {(isExpanded || isPinned) && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-xs font-semibold text-muted uppercase tracking-wider text-center"
            >
              Navigation
            </motion.div>
          )}

          {/* Navigation */}
          <div className="space-y-2">
            {navigationItems.map((item) => (
              <div key={item.id}>
                <motion.button
                  onClick={() => handleNavClick(item.path)}
                  className={`w-full flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${isActive(item)
                    ? 'bg-gradient-to-br from-blue-600 to-violet-600 text-white shadow-lg'
                    : 'text-secondary hover:bg-tertiary hover:text-primary'
                    }`}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                >
                  <span className="text-lg mr-3">{item.icon}</span>
                  {(isExpanded || isPinned) && (
                    <motion.span
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: 0.1 }}
                    >
                      {item.label}
                    </motion.span>
                  )}
                </motion.button>

                {/* Sub-items */}
                {item.subItems && (isExpanded || isPinned) && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    className="ml-6 mt-1 space-y-1"
                  >
                    {item.subItems.map(subItem => (
                      <motion.button
                        key={subItem.id}
                        onClick={() => handleNavClick(subItem.path)}
                        className={`w-full text-left px-3 py-1 rounded text-xs transition-colors ${location.pathname === subItem.path
                          ? 'bg-gradient-to-br from-blue-600 to-violet-600 text-white shadow-sm'
                          : 'text-muted hover:bg-tertiary hover:text-secondary'
                          }`}
                        whileHover={{ x: 4 }}
                      >
                        {subItem.label}
                      </motion.button>
                    ))}
                  </motion.div>
                )}
              </div>
            ))}
          </div>



          {/* Recent Items - Only show when expanded */}
          {(isExpanded || isPinned) && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.2 }}
              className="space-y-2"
            >
              <h2 className="text-xs font-semibold text-muted uppercase tracking-wider">
                Recent
              </h2>
              <div className="space-y-1">
                {recentItems.map((item) => (
                  <motion.button
                    key={item}
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
            </motion.div>
          )}

          {/* Quick Actions - Only show when expanded */}
          {(isExpanded || isPinned) && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.3 }}
              className="space-y-2"
            >
              <h2 className="text-xs font-semibold text-muted uppercase tracking-wider">
                Quick Actions
              </h2>
              <div className="space-y-2">
                {quickActions.map((action, index) => (
                  <motion.button
                    key={index}
                    onClick={action.action}
                    className="btn btn-primary w-full text-sm py-2"
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                  >
                    <span className="mr-2">{action.icon}</span>
                    {action.name}
                  </motion.button>
                ))}
              </div>
            </motion.div>
          )}
        </div>

        {/* Bottom Section */}
        <div className="p-4 border-t border-default space-y-3">
          {/* Settings */}
          <motion.button
            onClick={() => handleNavClick('/settings')}
            className={`w-full flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${location.pathname === '/settings'
              ? 'bg-gradient-to-br from-blue-600 to-violet-600 text-white shadow-lg'
              : 'text-secondary hover:bg-tertiary hover:text-primary'
              }`}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <span className="text-lg mr-3">🔧</span>
            {(isExpanded || isPinned) && (
              <motion.span
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.1 }}
              >
                Settings
              </motion.span>
            )}
          </motion.button>

          {/* Expand/Collapse Toggle */}
          <motion.button
            onClick={() => setIsExpanded(!isExpanded)}
            className="w-full flex items-center justify-center px-3 py-2 rounded-lg bg-tertiary hover:bg-primary transition-colors"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            title={isExpanded ? 'Collapse sidebar' : 'Expand sidebar'}
          >
            <span className="text-lg">
              {isExpanded ? '◀' : '▶'}
            </span>
            {(isExpanded || isPinned) && (
              <motion.span
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="ml-2 text-sm"
              >
                {isExpanded ? 'Collapse' : 'Expand'}
              </motion.span>
            )}
          </motion.button>

          {/* Pin Toggle - Only show when expanded */}
          {(isExpanded || isPinned) && (
            <motion.button
              onClick={() => setIsPinned(!isPinned)}
              className="w-full flex items-center justify-center px-3 py-2 rounded-lg bg-tertiary hover:bg-primary transition-colors"
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              title={isPinned ? 'Unpin sidebar' : 'Pin sidebar'}
            >
              <span className="text-lg mr-2">{isPinned ? '📌' : '📍'}</span>
              <span className="text-sm">{isPinned ? 'Unpin' : 'Pin'}</span>
            </motion.button>
          )}
        </div>
      </div>
    </motion.aside>
  )
}
