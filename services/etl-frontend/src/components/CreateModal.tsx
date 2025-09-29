import React, { useState, useEffect } from 'react'

interface CreateField {
  name: string
  label: string
  type: 'text' | 'number' | 'select' | 'checkbox' | 'textarea'
  required?: boolean
  placeholder?: string
  options?: { value: string | number; label: string }[]
  defaultValue?: any
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
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onKeyDown={handleKeyDown}>
      <div className="bg-primary rounded-lg shadow-xl w-full max-w-md mx-4 max-h-[90vh] overflow-y-auto">
        <div className="px-6 py-4 border-b border-tertiary/20">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-primary">{title}</h3>
            <button
              onClick={onClose}
              className="text-secondary hover:text-primary transition-colors"
              aria-label="Close modal"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 6L6 18"></path>
                <path d="M6 6l12 12"></path>
              </svg>
            </button>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-4 space-y-4">
          {fields.map((field) => (
            <div key={field.name}>
              <label htmlFor={field.name} className="block text-sm font-medium text-primary mb-1">
                {field.label}
                {field.required && <span className="text-red-500 ml-1">*</span>}
              </label>

              {field.type === 'text' && (
                <input
                  type="text"
                  id={field.name}
                  value={formData[field.name] || ''}
                  onChange={(e) => handleInputChange(field.name, e.target.value)}
                  placeholder={field.placeholder}
                  className={`w-full px-3 py-2 border rounded-lg bg-primary text-primary placeholder-secondary/60 focus:outline-none focus:ring-2 focus:ring-accent ${
                    errors[field.name] ? 'border-red-500' : 'border-tertiary/20'
                  }`}
                />
              )}

              {field.type === 'number' && (
                <input
                  type="number"
                  id={field.name}
                  value={formData[field.name] || ''}
                  onChange={(e) => handleInputChange(field.name, e.target.value)}
                  placeholder={field.placeholder}
                  className={`w-full px-3 py-2 border rounded-lg bg-primary text-primary placeholder-secondary/60 focus:outline-none focus:ring-2 focus:ring-accent ${
                    errors[field.name] ? 'border-red-500' : 'border-tertiary/20'
                  }`}
                />
              )}

              {field.type === 'textarea' && (
                <textarea
                  id={field.name}
                  value={formData[field.name] || ''}
                  onChange={(e) => handleInputChange(field.name, e.target.value)}
                  placeholder={field.placeholder}
                  rows={3}
                  className={`w-full px-3 py-2 border rounded-lg bg-primary text-primary placeholder-secondary/60 focus:outline-none focus:ring-2 focus:ring-accent resize-vertical ${
                    errors[field.name] ? 'border-red-500' : 'border-tertiary/20'
                  }`}
                />
              )}

              {field.type === 'select' && (
                <select
                  id={field.name}
                  value={formData[field.name] || ''}
                  onChange={(e) => handleInputChange(field.name, e.target.value)}
                  className={`w-full px-3 py-2 border rounded-lg bg-primary text-primary focus:outline-none focus:ring-2 focus:ring-accent ${
                    errors[field.name] ? 'border-red-500' : 'border-tertiary/20'
                  }`}
                >
                  {field.options?.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              )}

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
        </form>

        <div className="px-6 py-4 border-t border-tertiary/20 flex justify-end space-x-3">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-secondary hover:text-primary transition-colors"
            disabled={isLoading}
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={isLoading}
            className="px-4 py-2 bg-accent text-on-accent rounded-lg hover:bg-accent/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
          >
            {isLoading && (
              <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
            )}
            <span>{isLoading ? 'Creating...' : 'Create'}</span>
          </button>
        </div>
      </div>
    </div>
  )
}

export default CreateModal
