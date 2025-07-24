import { motion } from 'framer-motion'
import { useState } from 'react'

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
    badge: 'New',
    subItems: [
      { name: 'Deployment Frequency', active: false },
      { name: 'Lead Time for Changes', active: false },
      { name: 'Time to Restore', active: false },
      { name: 'Change Failure Rate', active: false }
    ]
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
  },
  {
    name: 'Settings',
    icon: '🔧',
    active: false,
    badge: null
  }
]

const recentItems = [
  'Q4 Performance Review',
  'Team Velocity Analysis',
  'Deployment Frequency Report'
]

export default function StaticSidebarWithHighlights() {
  const [expandedItem, setExpandedItem] = useState<string | null>(null)
  const [highlightedItems, setHighlightedItems] = useState<Set<string>>(new Set(['Dashboard']))

  const handleItemClick = (item: any) => {
    // Toggle highlighting
    const newHighlighted = new Set(highlightedItems)
    if (newHighlighted.has(item.name)) {
      newHighlighted.delete(item.name)
    } else {
      newHighlighted.add(item.name)
    }
    setHighlightedItems(newHighlighted)

    // Handle submenu expansion
    if (item.subItems) {
      setExpandedItem(expandedItem === item.name ? null : item.name)
    }
  }

  const handleSubItemClick = (parentName: string, subItem: any) => {
    const newHighlighted = new Set(highlightedItems)
    const subItemKey = `${parentName}-${subItem.name}`

    if (newHighlighted.has(subItemKey)) {
      newHighlighted.delete(subItemKey)
    } else {
      newHighlighted.add(subItemKey)
    }
    setHighlightedItems(newHighlighted)
  }

  return (
    <aside className="fixed left-0 top-16 h-[calc(100vh-4rem)] w-64 bg-secondary border-r border-default overflow-y-auto">
      <div className="p-4 space-y-6">
        {/* Navigation */}
        <div className="space-y-2">
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wider">
            Navigation
          </h2>
          <nav className="space-y-1">
            {navigationItems.map((item, index) => (
              <div key={item.name}>
                <motion.button
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.1 }}
                  onClick={() => handleItemClick(item)}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${highlightedItems.has(item.name)
                    ? 'bg-gradient-to-br from-blue-600 to-violet-600 text-white shadow-lg'
                    : 'text-secondary hover:bg-tertiary hover:text-primary'
                    }`}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                >
                  <div className="flex items-center space-x-3">
                    <span className="text-lg">{item.icon}</span>
                    <span>{item.name}</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    {item.badge && (
                      <span className={`px-2 py-1 text-xs rounded-full ${item.badge === 'New'
                        ? 'bg-emerald-100 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400'
                        : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400'
                        }`}>
                        {item.badge}
                      </span>
                    )}
                    {item.subItems && (
                      <span className={`transform transition-transform ${expandedItem === item.name ? 'rotate-180' : ''}`}>
                        ▼
                      </span>
                    )}
                  </div>
                </motion.button>

                {/* Sub-items */}
                {item.subItems && expandedItem === item.name && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="ml-6 mt-1 space-y-1"
                  >
                    {item.subItems.map((subItem, subIndex) => (
                      <motion.button
                        key={subItem.name}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: subIndex * 0.05 }}
                        onClick={() => handleSubItemClick(item.name, subItem)}
                        className={`w-full text-left px-3 py-1 rounded text-xs transition-colors ${highlightedItems.has(`${item.name}-${subItem.name}`)
                          ? 'bg-gradient-to-br from-blue-600 to-violet-600 text-white shadow-sm'
                          : 'text-muted hover:bg-tertiary hover:text-secondary'
                          }`}
                        whileHover={{ x: 4 }}
                      >
                        {subItem.name}
                      </motion.button>
                    ))}
                  </motion.div>
                )}
              </div>
            ))}
          </nav>
        </div>

        {/* Recent Items */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6 }}
          className="space-y-2"
        >
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wider">
            Recent
          </h2>
          <div className="space-y-1">
            {recentItems.map((item, index) => (
              <motion.button
                key={item}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.7 + index * 0.1 }}
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

        {/* Quick Actions */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7 }}
          className="space-y-2"
        >
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wider">
            Quick Actions
          </h2>
          <div className="space-y-2">
            <motion.button
              className="btn btn-primary w-full text-sm py-2"
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              🚀 Run ETL Job
            </motion.button>
            <motion.button
              className="btn btn-secondary w-full text-sm py-2"
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              📊 Generate Report
            </motion.button>
          </div>
        </motion.div>

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
