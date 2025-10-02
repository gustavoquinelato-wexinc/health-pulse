import React, { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { X } from 'lucide-react'

interface CreateField {
  name: string
  label: string
  type: 'text' | 'number' | 'select' | 'checkbox' | 'textarea'
  required?: boolean
  placeholder?: string
  options?: { value: string | number; label: string }[]
  defaultValue?: any
  customRender?: (
    field: CreateField,
    formData: Record<string, any>,
    handleInputChange: (name: string, value: any) => void,
    errors: Record<string, string>
  ) => React.ReactNode
}

interface CreateModalProps {
  isOpen: boolean
  onClose: () => void
  onSave: (formData: Record<string, any>) => Promise<void>
  title: string
  fields: CreateField[]
}

const CreateModal: React.FC<CreateModalProps> = ({
  isOpen,
  onClose,
  onSave,
  title,
  fields
}) => {
  const [formData, setFormData] = useState<Record<string, any>>({})
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [isLoading, setIsLoading] = useState(false)

  // Initialize form data with default values
  useEffect(() => {
    if (isOpen) {
      const initialData: Record<string, any> = {}
      fields.forEach(field => {
        initialData[field.name] = field.defaultValue || (field.type === 'checkbox' ? false : '')
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

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {}

    fields.forEach(field => {
      if (field.required) {
        const value = formData[field.name]
        if (!value && value !== 0 && value !== false) {
          newErrors[field.name] = `${field.label} is required`
        }
      }
    })

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!validateForm()) {
      return
    }

    setIsLoading(true)
    try {
      await onSave(formData)
      onClose()
    } catch (error) {
      console.error('Error creating item:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      onClose()
    } else if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      handleSubmit(e)
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
          className="relative w-full max-w-2xl bg-primary rounded-xl shadow-2xl border border-tertiary overflow-hidden"
          onKeyDown={handleKeyDown}
        >
          {/* Header */}
          <div className="flex items-center justify-between p-6 bg-table-header border-b border-tertiary">
            <div className="flex items-center space-x-3">
              <div className="h-8 w-8 bg-blue-600 rounded-lg flex items-center justify-center">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-white">
                  <path d="M5 12h14"></path>
                  <path d="M12 5v14"></path>
                </svg>
              </div>
              <h3 className="text-xl font-semibold text-table-header">{title}</h3>
            </div>
            <button
              onClick={onClose}
              className="p-1 rounded-lg text-secondary hover:bg-tertiary hover:text-primary transition-colors"
              aria-label="Close modal"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Content */}
          <div className="p-8 space-y-6 max-h-[70vh] overflow-y-auto bg-secondary">
            {fields.map((field) => (
              <div key={field.name} className="space-y-3">
                <label htmlFor={field.name} className="block text-sm font-semibold text-primary">
                  {field.label}
                  {field.required && <span className="text-red-500 ml-1">*</span>}
                </label>

              {field.customRender ? (
                field.customRender(field, formData, handleInputChange, errors)
              ) : field.type === 'text' ? (
                <input
                  type="text"
                  id={field.name}
                  value={formData[field.name] || ''}
                  onChange={(e) => handleInputChange(field.name, e.target.value)}
                  placeholder={field.placeholder}
                  className={`input w-full ${errors[field.name] ? 'border-red-500' : ''}`}
                />
              ) : field.type === 'number' ? (
                <input
                  type="number"
                  id={field.name}
                  value={formData[field.name] || ''}
                  onChange={(e) => handleInputChange(field.name, e.target.value)}
                  placeholder={field.placeholder}
                  className={`input w-full ${errors[field.name] ? 'border-red-500' : ''}`}
                />
              ) : field.type === 'textarea' ? (
                <textarea
                  id={field.name}
                  value={formData[field.name] || ''}
                  onChange={(e) => handleInputChange(field.name, e.target.value)}
                  placeholder={field.placeholder}
                  rows={3}
                  className={`input w-full resize-vertical ${errors[field.name] ? 'border-red-500' : ''}`}
                />
              ) : field.type === 'select' ? (
                <select
                  id={field.name}
                  value={formData[field.name] || ''}
                  onChange={(e) => handleInputChange(field.name, e.target.value)}
                  className={`input w-full ${errors[field.name] ? 'border-red-500' : ''}`}
                >
                  {field.options?.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              ) : null}

              {field.type === 'checkbox' && (
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id={field.name}
                    checked={formData[field.name] || false}
                    onChange={(e) => handleInputChange(field.name, e.target.checked)}
                    className="h-4 w-4 text-accent focus:ring-accent border-tertiary/20 rounded"
                  />
                  <label htmlFor={field.name} className="ml-2 text-sm text-secondary">
                    {field.placeholder}
                  </label>
                </div>
              )}

              {errors[field.name] && (
                <p className="text-red-500 text-sm mt-1">{errors[field.name]}</p>
              )}
            </div>
          ))}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end space-x-4 p-6 bg-tertiary border-t border-tertiary">
            <button
              type="button"
              onClick={onClose}
              disabled={isLoading}
              className="px-6 py-2.5 text-secondary hover:text-primary hover:bg-secondary rounded-lg transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={isLoading}
              className="px-8 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2 font-medium shadow-sm"
            >
              {isLoading && (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              )}
              <span>{isLoading ? 'Creating...' : 'Create'}</span>
            </button>
          </div>
        </motion.div>
      </div>
    </div>
  )
}

export default CreateModal
