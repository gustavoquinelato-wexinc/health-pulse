import React, { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { X } from 'lucide-react'

interface EditField {
  name: string
  label: string
  type: 'text' | 'number' | 'select' | 'checkbox' | 'textarea'
  value: any
  required?: boolean
  options?: { value: any; label: string }[]
  placeholder?: string
  disabled?: boolean
}

interface EditModalProps {
  isOpen: boolean
  onClose: () => void
  onSave: (data: Record<string, any>) => Promise<void>
  title: string
  fields: EditField[]
  loading?: boolean
}

export default function EditModal({
  isOpen,
  onClose,
  onSave,
  title,
  fields,
  loading = false
}: EditModalProps) {
  const [formData, setFormData] = useState<Record<string, any>>({})
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)

  // Initialize form data when modal opens or fields change
  useEffect(() => {
    if (isOpen) {
      const initialData: Record<string, any> = {}
      fields.forEach(field => {
        initialData[field.name] = field.value
      })
      setFormData(initialData)
      setErrors({})
    }
  }, [isOpen, fields])

  const handleInputChange = (name: string, value: any) => {
    setFormData(prev => ({ ...prev, [name]: value }))
    // Clear error when user starts typing
    if (errors[name]) {
      setErrors(prev => ({ ...prev, [name]: '' }))
    }
  }

  const validateForm = () => {
    const newErrors: Record<string, string> = {}
    
    fields.forEach(field => {
      if (field.required && (!formData[field.name] || formData[field.name] === '')) {
        newErrors[field.name] = `${field.label} is required`
      }
    })

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSave = async () => {
    if (!validateForm()) return

    try {
      setSaving(true)
      await onSave(formData)
      onClose()
    } catch (error) {
      console.error('Error saving:', error)
    } finally {
      setSaving(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      onClose()
    } else if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      handleSave()
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-[9999] overflow-y-auto">
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      
      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          className="relative w-full max-w-md bg-secondary rounded-lg shadow-xl border border-default"
          onKeyDown={handleKeyDown}
        >
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b border-default">
            <h3 className="text-lg font-semibold text-primary">{title}</h3>
            <button
              onClick={onClose}
              className="p-1 rounded-lg text-secondary hover:bg-tertiary hover:text-primary transition-colors"
              aria-label="Close modal"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Content */}
          <div className="p-6 space-y-4 max-h-96 overflow-y-auto">
            {fields.map((field) => (
              <div key={field.name}>
                <label className="block text-sm font-medium text-primary mb-1">
                  {field.label}
                  {field.required && <span className="text-red-500 ml-1">*</span>}
                </label>
                
                {field.type === 'text' && (
                  <input
                    type="text"
                    value={formData[field.name] || ''}
                    onChange={(e) => handleInputChange(field.name, e.target.value)}
                    placeholder={field.placeholder}
                    disabled={field.disabled || loading}
                    className={`input w-full ${errors[field.name] ? 'border-red-500' : ''}`}
                  />
                )}

                {field.type === 'number' && (
                  <input
                    type="number"
                    value={formData[field.name] || ''}
                    onChange={(e) => handleInputChange(field.name, parseInt(e.target.value) || '')}
                    placeholder={field.placeholder}
                    disabled={field.disabled || loading}
                    className={`input w-full ${errors[field.name] ? 'border-red-500' : ''}`}
                  />
                )}

                {field.type === 'textarea' && (
                  <textarea
                    value={formData[field.name] || ''}
                    onChange={(e) => handleInputChange(field.name, e.target.value)}
                    placeholder={field.placeholder}
                    disabled={field.disabled || loading}
                    rows={3}
                    className={`input w-full resize-none ${errors[field.name] ? 'border-red-500' : ''}`}
                  />
                )}

                {field.type === 'select' && (
                  <select
                    value={formData[field.name] || ''}
                    onChange={(e) => handleInputChange(field.name, e.target.value)}
                    disabled={field.disabled || loading}
                    className={`input w-full ${errors[field.name] ? 'border-red-500' : ''}`}
                  >
                    <option value="">Select {field.label}</option>
                    {field.options?.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                )}

                {field.type === 'checkbox' && (
                  <label className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={formData[field.name] || false}
                      onChange={(e) => handleInputChange(field.name, e.target.checked)}
                      disabled={field.disabled || loading}
                      className="rounded border-default"
                    />
                    <span className="text-sm text-secondary">{field.placeholder}</span>
                  </label>
                )}

                {errors[field.name] && (
                  <p className="text-sm text-red-500 mt-1">{errors[field.name]}</p>
                )}
              </div>
            ))}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end space-x-3 p-6 border-t border-default">
            <button
              onClick={onClose}
              disabled={saving}
              className="px-4 py-2 text-sm font-medium text-secondary hover:text-primary transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving || loading}
              className="px-4 py-2 bg-accent text-on-accent rounded-lg hover:bg-accent/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
            >
              {saving && (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              )}
              <span>{saving ? 'Saving...' : 'Save Changes'}</span>
            </button>
          </div>
        </motion.div>
      </div>
    </div>
  )
}
