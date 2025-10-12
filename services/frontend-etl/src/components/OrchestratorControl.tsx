import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Play, Power, Clock, Activity, Settings } from 'lucide-react'
import { useTheme } from '../contexts/ThemeContext'

interface OrchestratorControlProps {
  status: {
    enabled: boolean
    interval_minutes: number
    status: string
    last_run?: string
    next_run?: string
  }
  onToggle: (enabled: boolean) => void
  onStart: () => void
  onSettings: () => void
}

export default function OrchestratorControl({ status, onToggle, onStart, onSettings }: OrchestratorControlProps) {
  const { theme } = useTheme()
  const [isToggling, setIsToggling] = useState(false)
  const [countdown, setCountdown] = useState<string>('Calculating...')

  const handleToggle = async () => {
    setIsToggling(true)
    try {
      await onToggle(!status.enabled)
    } finally {
      setIsToggling(false)
    }
  }

  // Calculate countdown timer
  useEffect(() => {
    if (!status.next_run) {
      setCountdown('Calculating...')
      return
    }

    const updateCountdown = () => {
      const now = new Date()
      const nextRun = new Date(status.next_run!)
      const diff = nextRun.getTime() - now.getTime()

      if (diff <= 0) {
        setCountdown('Ready to run')
        return
      }

      const minutes = Math.floor(diff / 60000)
      const seconds = Math.floor((diff % 60000) / 1000)

      if (minutes > 60) {
        const hours = Math.floor(minutes / 60)
        const remainingMinutes = minutes % 60
        setCountdown(`${hours}h ${remainingMinutes}m`)
      } else if (minutes > 0) {
        setCountdown(`${minutes}m ${seconds}s`)
      } else {
        setCountdown(`${seconds}s`)
      }
    }

    // Update immediately
    updateCountdown()

    // Update every second
    const interval = setInterval(updateCountdown, 1000)

    return () => clearInterval(interval)
  }, [status.next_run])

  // Get status color and icon
  const getStatusInfo = () => {
    if (!status.enabled) {
      return {
        color: 'text-gray-500',
        bgColor: 'bg-gray-100',
        label: 'Stopped',
        icon: <Power className="w-5 h-5" />
      }
    }

    switch (status.status) {
      case 'running':
        return {
          color: 'text-blue-500',
          bgColor: 'bg-blue-100',
          label: 'Running',
          icon: <Activity className="w-5 h-5 animate-pulse" />
        }
      case 'paused':
        return {
          color: 'text-yellow-500',
          bgColor: 'bg-yellow-100',
          label: 'Idle',
          icon: <Clock className="w-5 h-5" />
        }
      default:
        return {
          color: 'text-green-500',
          bgColor: 'bg-green-100',
          label: 'Active',
          icon: <Activity className="w-5 h-5" />
        }
    }
  }

  const statusInfo = getStatusInfo()

  return (
    <motion.div
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = 'var(--color-1)'
        e.currentTarget.style.boxShadow = theme === 'dark'
          ? '0 -4px 6px -1px rgba(255, 255, 255, 0.12), 4px 0 6px -1px rgba(255, 255, 255, 0.12), 0 4px 6px -1px rgba(255, 255, 255, 0.12)'
          : '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = theme === 'dark' ? '#3e3e42' : '#9ca3af'
        e.currentTarget.style.boxShadow = theme === 'dark'
          ? '0 -4px 6px -1px rgba(255, 255, 255, 0.08), 4px 0 6px -1px rgba(255, 255, 255, 0.08), 0 4px 6px -1px rgba(255, 255, 255, 0.08)'
          : ''
      }}
      className="card p-6 mb-6 transition-all duration-200"
    >
      <div className="flex items-center justify-between">
        {/* Left: Orchestrator Info */}
        <div className="flex items-center space-x-4">
          {/* Icon */}
          <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${statusInfo.bgColor}`}>
            <div className={statusInfo.color}>
              {statusInfo.icon}
            </div>
          </div>

          {/* Status Info */}
          <div>
            <h2 className="text-xl font-semibold text-primary">
              Orchestrator
            </h2>
            <div className="flex items-center space-x-3 mt-1">
              <span className={`text-sm font-medium ${statusInfo.color}`}>
                {statusInfo.label}
              </span>
              <span className="text-sm text-secondary">
                Interval: {status.interval_minutes}m
              </span>
            </div>
          </div>
        </div>

        {/* Right: Controls */}
        <div className="flex items-center space-x-4">
          {/* Manual Start Button */}
          {status.enabled && (
            <button
              onClick={onStart}
              className="btn-crud-create px-4 py-2 rounded-lg flex items-center space-x-2"
              title="Manually trigger orchestrator"
            >
              <Play className="w-4 h-4" />
              <span>Run Now</span>
            </button>
          )}

          {/* Settings Button */}
          <button
            onClick={onSettings}
            className="p-2 rounded-lg hover:bg-tertiary transition-colors"
            title="Orchestrator Settings"
          >
            <Settings className="w-5 h-5 text-secondary" />
          </button>

          {/* On/Off Toggle */}
          <div className="flex items-center space-x-2">
            <button
              onClick={handleToggle}
              disabled={isToggling}
              className={`relative inline-flex h-5 w-10 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 ${
                status.enabled
                  ? 'bg-gradient-to-r from-green-500 to-green-600 focus:ring-green-500'
                  : 'bg-gray-300 focus:ring-gray-400'
              } ${isToggling ? 'opacity-50 cursor-not-allowed' : ''}`}
              title={status.enabled ? 'Turn off orchestrator' : 'Turn on orchestrator'}
            >
              <span className="sr-only">Toggle orchestrator</span>
              <motion.span
                className={`inline-block h-3 w-3 transform rounded-full bg-white shadow-lg transition-transform ${
                  status.enabled ? 'translate-x-6' : 'translate-x-1'
                }`}
                animate={{ x: status.enabled ? 24 : 4 }}
                transition={{ type: 'spring', stiffness: 500, damping: 30 }}
              />
            </button>
            <span className="text-sm text-secondary w-8">
              {status.enabled ? 'On' : 'Off'}
            </span>
          </div>
        </div>
      </div>

      {/* Additional Info Row */}
      {status.enabled && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="mt-4 pt-4 border-t border-border"
        >
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <span className="text-secondary">Last Run:</span>
              <span className="ml-2 text-primary font-medium">
                {status.last_run ? new Date(status.last_run).toLocaleString() : 'Never'}
              </span>
            </div>
            <div>
              <span className="text-secondary">Next Run:</span>
              <span className="ml-2 text-primary font-medium">
                {status.next_run ? new Date(status.next_run).toLocaleString() : 'Calculating...'}
              </span>
            </div>
            <div>
              <span className="text-secondary">Countdown:</span>
              <span className="ml-2 text-primary font-medium font-mono">
                {countdown}
              </span>
            </div>
          </div>
        </motion.div>
      )}
    </motion.div>
  )
}

