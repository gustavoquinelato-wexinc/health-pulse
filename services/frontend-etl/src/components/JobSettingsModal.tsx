import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Clock, RefreshCw, Save } from 'lucide-react'

export interface JobSettings {
  schedule_interval_minutes: number
  retry_interval_minutes: number
}

interface JobSettingsModalProps {
  isOpen: boolean
  onClose: () => void
  onSave: (settings: JobSettings) => Promise<void>
  currentSettings: JobSettings
  jobName: string
}

export default function JobSettingsModal({
  isOpen,
  onClose,
  onSave,
  currentSettings,
  jobName
}: JobSettingsModalProps) {
  const [settings, setSettings] = useState<JobSettings>(currentSettings)
  const [isSaving, setIsSaving] = useState(false)
  const [errors, setErrors] = useState<Partial<Record<keyof JobSettings, string>>>({})

  useEffect(() => {
    if (isOpen) {
      setSettings(currentSettings)
      setErrors({})
    }
  }, [isOpen, currentSettings])

  const validateSettings = (): boolean => {
    const newErrors: Partial<Record<keyof JobSettings, string>> = {}

    if (settings.schedule_interval_minutes < 1) {
      newErrors.schedule_interval_minutes = 'Schedule interval must be at least 1 minute'
    }

    if (settings.retry_interval_minutes < 1) {
      newErrors.retry_interval_minutes = 'Retry interval must be at least 1 minute'
    }

    if (settings.retry_interval_minutes >= settings.schedule_interval_minutes) {
      newErrors.retry_interval_minutes = 'Retry interval must be less than schedule interval'
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSave = async () => {
    if (!validateSettings()) return

    setIsSaving(true)
    try {
      await onSave(settings)
      onClose()
    } catch (err) {
      // Error handled by parent component
    } finally {
      setIsSaving(false)
    }
  }

  const formatMinutesToHours = (minutes: number): string => {
    if (minutes < 60) return `${minutes} minutes`
    const hours = Math.floor(minutes / 60)
    const mins = minutes % 60
    if (mins === 0) return `${hours} hour${hours > 1 ? 's' : ''}`
    return `${hours}h ${mins}m`
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black bg-opacity-50 z-40"
          />

          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
          >
            <div className="card w-full max-w-2xl max-h-[90vh] overflow-y-auto">
              {/* Header */}
              <div className="flex items-center justify-between p-6 border-b border-border">
                <div>
                  <h2 className="text-2xl font-bold text-primary">
                    Job Settings
                  </h2>
                  <p className="text-sm text-secondary mt-1">
                    Configure schedule and retry settings for {jobName.toUpperCase()}
                  </p>
                </div>
                <button
                  onClick={onClose}
                  className="p-2 hover:bg-tertiary rounded-lg transition-colors"
                >
                  <X className="w-5 h-5 text-secondary" />
                </button>
              </div>

              {/* Content */}
              <div className="p-6 space-y-6">
                {/* Schedule Interval */}
                <div>
                  <label className="flex items-center space-x-2 text-sm font-medium text-primary mb-2">
                    <Clock className="w-4 h-4" />
                    <span>Schedule Interval</span>
                  </label>
                  <p className="text-xs text-secondary mb-3">
                    How often the job should run automatically
                  </p>
                  <div className="space-y-2">
                    <input
                      type="number"
                      min="1"
                      value={settings.schedule_interval_minutes}
                      onChange={(e) => setSettings({
                        ...settings,
                        schedule_interval_minutes: parseInt(e.target.value) || 0
                      })}
                      className="input w-full"
                      placeholder="Enter minutes"
                    />
                    {errors.schedule_interval_minutes && (
                      <p className="text-xs text-red-500">{errors.schedule_interval_minutes}</p>
                    )}
                    <p className="text-xs text-secondary">
                      = {formatMinutesToHours(settings.schedule_interval_minutes)}
                    </p>
                  </div>

                  {/* Quick Presets */}
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      onClick={() => setSettings({ ...settings, schedule_interval_minutes: 60 })}
                      className="px-3 py-1 text-xs rounded-lg bg-tertiary hover:bg-opacity-80 text-secondary"
                    >
                      1 hour
                    </button>
                    <button
                      onClick={() => setSettings({ ...settings, schedule_interval_minutes: 240 })}
                      className="px-3 py-1 text-xs rounded-lg bg-tertiary hover:bg-opacity-80 text-secondary"
                    >
                      4 hours
                    </button>
                    <button
                      onClick={() => setSettings({ ...settings, schedule_interval_minutes: 360 })}
                      className="px-3 py-1 text-xs rounded-lg bg-tertiary hover:bg-opacity-80 text-secondary"
                    >
                      6 hours
                    </button>
                    <button
                      onClick={() => setSettings({ ...settings, schedule_interval_minutes: 720 })}
                      className="px-3 py-1 text-xs rounded-lg bg-tertiary hover:bg-opacity-80 text-secondary"
                    >
                      12 hours
                    </button>
                    <button
                      onClick={() => setSettings({ ...settings, schedule_interval_minutes: 1440 })}
                      className="px-3 py-1 text-xs rounded-lg bg-tertiary hover:bg-opacity-80 text-secondary"
                    >
                      24 hours
                    </button>
                  </div>
                </div>

                {/* Retry Interval */}
                <div>
                  <label className="flex items-center space-x-2 text-sm font-medium text-primary mb-2">
                    <RefreshCw className="w-4 h-4" />
                    <span>Retry Interval (Fast Retry)</span>
                  </label>
                  <p className="text-xs text-secondary mb-3">
                    How quickly to retry when a job fails
                  </p>
                  <div className="space-y-2">
                    <input
                      type="number"
                      min="1"
                      value={settings.retry_interval_minutes}
                      onChange={(e) => setSettings({
                        ...settings,
                        retry_interval_minutes: parseInt(e.target.value) || 0
                      })}
                      className="input w-full"
                      placeholder="Enter minutes"
                    />
                    {errors.retry_interval_minutes && (
                      <p className="text-xs text-red-500">{errors.retry_interval_minutes}</p>
                    )}
                    <p className="text-xs text-secondary">
                      = {formatMinutesToHours(settings.retry_interval_minutes)}
                    </p>
                  </div>

                  {/* Quick Presets */}
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      onClick={() => setSettings({ ...settings, retry_interval_minutes: 5 })}
                      className="px-3 py-1 text-xs rounded-lg bg-tertiary hover:bg-opacity-80 text-secondary"
                    >
                      5 min
                    </button>
                    <button
                      onClick={() => setSettings({ ...settings, retry_interval_minutes: 15 })}
                      className="px-3 py-1 text-xs rounded-lg bg-tertiary hover:bg-opacity-80 text-secondary"
                    >
                      15 min
                    </button>
                    <button
                      onClick={() => setSettings({ ...settings, retry_interval_minutes: 30 })}
                      className="px-3 py-1 text-xs rounded-lg bg-tertiary hover:bg-opacity-80 text-secondary"
                    >
                      30 min
                    </button>
                    <button
                      onClick={() => setSettings({ ...settings, retry_interval_minutes: 60 })}
                      className="px-3 py-1 text-xs rounded-lg bg-tertiary hover:bg-opacity-80 text-secondary"
                    >
                      1 hour
                    </button>
                  </div>
                </div>

                {/* Info Box */}
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <p className="text-sm text-blue-800">
                    <strong>How it works:</strong> The job will run every{' '}
                    <strong>{formatMinutesToHours(settings.schedule_interval_minutes)}</strong> when successful.
                    If it fails, it will retry every{' '}
                    <strong>{formatMinutesToHours(settings.retry_interval_minutes)}</strong> until it succeeds.
                  </p>
                </div>
              </div>

              {/* Footer */}
              <div className="flex items-center justify-end space-x-3 p-6 border-t border-border">
                <button
                  onClick={onClose}
                  className="btn-crud-cancel px-4 py-2 rounded-lg"
                  disabled={isSaving}
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  disabled={isSaving}
                  className="btn-crud-create px-4 py-2 rounded-lg flex items-center space-x-2"
                >
                  {isSaving ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                      <span>Saving...</span>
                    </>
                  ) : (
                    <>
                      <Save className="w-4 h-4" />
                      <span>Save Settings</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}

