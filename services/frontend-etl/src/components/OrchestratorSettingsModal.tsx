import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Settings, Save } from 'lucide-react'

interface OrchestratorSettingsModalProps {
  isOpen: boolean
  onClose: () => void
  onSave: (settings: OrchestratorSettings) => Promise<void>
  currentSettings: OrchestratorSettings
}

export interface OrchestratorSettings {
  interval_minutes: number
  retry_enabled: boolean
  retry_interval_minutes: number
  max_retry_attempts: number
}

export default function OrchestratorSettingsModal({
  isOpen,
  onClose,
  onSave,
  currentSettings
}: OrchestratorSettingsModalProps) {
  const [settings, setSettings] = useState<OrchestratorSettings>(currentSettings)
  const [isSaving, setIsSaving] = useState(false)

  // Update local state when currentSettings change
  useEffect(() => {
    setSettings(currentSettings)
  }, [currentSettings])

  const handleSave = async () => {
    setIsSaving(true)
    try {
      await onSave(settings)
      onClose()
    } finally {
      setIsSaving(false)
    }
  }

  const handleCancel = () => {
    setSettings(currentSettings) // Reset to original
    onClose()
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="card max-w-md w-full"
          >
            {/* Header */}
            <div className="flex justify-between items-center px-6 py-4 border-b border-tertiary">
              <div className="flex items-center space-x-2">
                <Settings className="w-5 h-5 text-primary" />
                <h3 className="text-lg font-semibold text-primary">
                  Orchestrator Settings
                </h3>
              </div>
              <button
                onClick={handleCancel}
                className="text-secondary hover:text-primary transition-colors"
                title="Close"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Body */}
            <div className="px-6 py-4 space-y-4">
              {/* Run Interval */}
              <div>
                <label className="block text-sm font-medium text-primary mb-2">
                  Run Interval
                </label>
                <select
                  value={settings.interval_minutes}
                  onChange={(e) => setSettings({ ...settings, interval_minutes: parseInt(e.target.value) })}
                  className="w-full px-3 py-2 rounded-md bg-tertiary border border-tertiary text-primary focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="60">Every 1 hour</option>
                  <option value="120">Every 2 hours</option>
                  <option value="240">Every 4 hours</option>
                  <option value="480">Every 8 hours</option>
                  <option value="720">Every 12 hours</option>
                  <option value="1440">Every 24 hours</option>
                </select>
              </div>

              {/* Fast Retry Section */}
              <div className="space-y-3">
                {/* Retry Enabled Checkbox */}
                <div>
                  <label className="flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={settings.retry_enabled}
                      onChange={(e) => setSettings({ ...settings, retry_enabled: e.target.checked })}
                      className="mr-2 h-4 w-4 rounded text-blue-500 focus:ring-2 focus:ring-blue-500"
                    />
                    <span className="text-sm font-medium text-primary">
                      Enable Fast Retry for Failed Jobs
                    </span>
                  </label>
                  <p className="text-xs text-secondary mt-1 ml-6">
                    Automatically retry failed jobs at a faster interval before falling back to normal schedule
                  </p>
                </div>

                {/* Retry Settings (only shown when enabled) */}
                {settings.retry_enabled && (
                  <div className="ml-6 space-y-3 border-l-2 border-tertiary pl-4">
                    {/* Retry Interval */}
                    <div>
                      <label className="block text-sm font-medium text-primary mb-2">
                        Retry Interval
                      </label>
                      <select
                        value={settings.retry_interval_minutes}
                        onChange={(e) => setSettings({ ...settings, retry_interval_minutes: parseInt(e.target.value) })}
                        className="w-full px-3 py-2 rounded-md bg-tertiary border border-tertiary text-primary focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="5">Every 5 minutes</option>
                        <option value="10">Every 10 minutes</option>
                        <option value="15">Every 15 minutes</option>
                        <option value="30">Every 30 minutes</option>
                        <option value="60">Every 1 hour</option>
                      </select>
                    </div>

                    {/* Max Retry Attempts */}
                    <div>
                      <label className="block text-sm font-medium text-primary mb-2">
                        Max Retry Attempts
                      </label>
                      <select
                        value={settings.max_retry_attempts}
                        onChange={(e) => setSettings({ ...settings, max_retry_attempts: parseInt(e.target.value) })}
                        className="w-full px-3 py-2 rounded-md bg-tertiary border border-tertiary text-primary focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="3">3 attempts</option>
                        <option value="5">5 attempts</option>
                        <option value="10">10 attempts</option>
                        <option value="0">Unlimited</option>
                      </select>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Footer */}
            <div className="px-6 py-4 border-t border-tertiary flex justify-end space-x-3">
              <button
                onClick={handleCancel}
                className="btn-neutral-secondary px-4 py-2 rounded-lg"
                title="Cancel changes"
                disabled={isSaving}
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                className="btn-crud-create px-4 py-2 rounded-lg flex items-center space-x-2"
                title="Save settings"
                disabled={isSaving}
              >
                <Save className="w-4 h-4" />
                <span>{isSaving ? 'Saving...' : 'Save'}</span>
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}

