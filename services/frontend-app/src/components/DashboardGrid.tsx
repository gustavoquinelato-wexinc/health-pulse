
import { motion } from 'framer-motion'

const metrics = [
  {
    title: 'Lead Time',
    value: '2.3 days',
    change: '-12%',
    trend: 'down',
    color: 'emerald'
  },
  {
    title: 'Deployment Frequency',
    value: '4.2/day',
    change: '+18%',
    trend: 'up',
    color: 'blue'
  },
  {
    title: 'MTTR',
    value: '45 min',
    change: '-8%',
    trend: 'down',
    color: 'violet'
  },
  {
    title: 'Change Failure Rate',
    value: '2.1%',
    change: '+3%',
    trend: 'up',
    color: 'amber'
  }
]

const chartData = [
  { name: 'Jan', value: 65 },
  { name: 'Feb', value: 78 },
  { name: 'Mar', value: 82 },
  { name: 'Apr', value: 75 },
  { name: 'May', value: 88 },
  { name: 'Jun', value: 92 }
]

export default function DashboardGrid() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {/* DORA Metrics Cards */}
      {metrics.map((metric, index) => (
        <motion.div
          key={metric.title}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: index * 0.1 }}
          className="card p-6 space-y-4"
          whileHover={{ scale: 1.02 }}
        >
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-muted">{metric.title}</h3>
            <div className={`w-3 h-3 rounded-full ${metric.color === 'emerald' ? 'bg-emerald-400' :
                metric.color === 'blue' ? 'bg-blue-400' :
                  metric.color === 'violet' ? 'bg-violet-400' :
                    'bg-amber-400'
              }`}></div>
          </div>

          <div className="space-y-2">
            <div className="text-2xl font-bold text-primary">{metric.value}</div>
            <div className={`flex items-center space-x-1 text-sm ${metric.trend === 'up' ? 'text-emerald-600' : 'text-red-600'
              }`}>
              <span>{metric.trend === 'up' ? '↗️' : '↘️'}</span>
              <span>{metric.change}</span>
              <span className="text-muted">vs last month</span>
            </div>
          </div>
        </motion.div>
      ))}

      {/* Chart Card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="card p-6 md:col-span-2 lg:col-span-2"
      >
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-primary">Performance Trend</h3>
            <div className="flex space-x-2">
              <button className="px-3 py-1 text-xs bg-blue-100 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 rounded-full">
                6M
              </button>
              <button className="px-3 py-1 text-xs bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 rounded-full">
                1Y
              </button>
            </div>
          </div>

          {/* Simple Chart Visualization */}
          <div className="h-32 flex items-end space-x-2">
            {chartData.map((item, index) => (
              <motion.div
                key={item.name}
                initial={{ height: 0 }}
                animate={{ height: `${item.value}%` }}
                transition={{ delay: 0.5 + index * 0.1, duration: 0.5 }}
                className="flex-1 bg-gradient-to-t from-blue-500 to-violet-500 rounded-t-sm relative"
              >
                <div className="absolute -bottom-6 left-1/2 transform -translate-x-1/2 text-xs text-muted">
                  {item.name}
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </motion.div>

      {/* Activity Feed */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
        className="card p-6 md:col-span-2 lg:col-span-2"
      >
        <h3 className="text-lg font-semibold text-primary mb-4">Recent Activity</h3>
        <div className="space-y-3">
          {[
            { action: 'ETL Job completed', time: '2 min ago', status: 'success' },
            { action: 'New deployment detected', time: '15 min ago', status: 'info' },
            { action: 'Performance alert resolved', time: '1 hour ago', status: 'success' },
            { action: 'GitHub sync started', time: '2 hours ago', status: 'pending' }
          ].map((activity, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.7 + index * 0.1 }}
              className="flex items-center space-x-3 p-3 rounded-lg bg-tertiary"
            >
              <div className={`w-2 h-2 rounded-full ${activity.status === 'success' ? 'bg-emerald-400' :
                  activity.status === 'info' ? 'bg-blue-400' :
                    'bg-amber-400'
                }`}></div>
              <div className="flex-1">
                <p className="text-sm text-primary">{activity.action}</p>
                <p className="text-xs text-muted">{activity.time}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </motion.div>
    </div>
  )
}
