import { motion } from 'framer-motion'
import { useState } from 'react'
import { useTheme } from '../contexts/ThemeContext'

export default function ColorSchemaPanel() {
  const { colorSchema, updateColorSchema, resetToDefault } = useTheme()
  const [isExpanded, setIsExpanded] = useState(false)

  const colorInputs = [
    { key: 'color1', label: 'Color 1', description: 'Primary accent color' },
    { key: 'color2', label: 'Color 2', description: 'Secondary dark color' },
    { key: 'color3', label: 'Color 3', description: 'Success/teal color' },
    { key: 'color4', label: 'Color 4', description: 'Info/light blue color' },
    { key: 'color5', label: 'Color 5', description: 'Warning/yellow color' }
  ]

  const handleColorChange = (colorKey: string, value: string) => {
    updateColorSchema({ [colorKey]: value })
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.8 }}
      className="card p-6 space-y-6"
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-primary">Design System Showcase</h2>
          <p className="text-sm text-secondary">
            Customizable color schema and modern UI components
          </p>
        </div>
        <motion.button
          onClick={() => setIsExpanded(!isExpanded)}
          className="btn btn-secondary px-4 py-2 text-sm"
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
        >
          {isExpanded ? 'Collapse' : 'Customize Colors'}
        </motion.button>
      </div>

      {/* Color Showcase */}
      <div className="grid grid-cols-5 gap-4">
        {colorInputs.map((color, index) => (
          <motion.div
            key={color.key}
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.9 + index * 0.1 }}
            className="text-center space-y-2"
          >
            <div
              className={`w-16 h-16 mx-auto rounded-xl shadow-md bg-${color.key} cursor-pointer transition-transform hover:scale-110`}
              style={{ backgroundColor: colorSchema[color.key as keyof typeof colorSchema] }}
            />
            <div>
              <p className="text-sm font-medium text-primary">{color.label}</p>
              <p className="text-xs text-muted">{colorSchema[color.key as keyof typeof colorSchema]}</p>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Color Customization Panel */}
      {isExpanded && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          className="space-y-4 border-t border-default pt-6"
        >
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-medium text-primary">Customize Colors</h3>
            <button
              onClick={resetToDefault}
              className="text-sm text-blue-600 hover:text-blue-700 transition-colors"
            >
              Reset to Default
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {colorInputs.map((color) => (
              <div key={color.key} className="space-y-2">
                <label className="block text-sm font-medium text-primary">
                  {color.label}
                </label>
                <p className="text-xs text-muted">{color.description}</p>
                <div className="flex space-x-2">
                  <input
                    type="color"
                    value={colorSchema[color.key as keyof typeof colorSchema]}
                    onChange={(e) => handleColorChange(color.key, e.target.value)}
                    className="w-12 h-10 rounded-lg border border-default cursor-pointer"
                  />
                  <input
                    type="text"
                    value={colorSchema[color.key as keyof typeof colorSchema]}
                    onChange={(e) => handleColorChange(color.key, e.target.value)}
                    className="input flex-1 text-sm"
                    placeholder="#000000"
                  />
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* Component Showcase */}
      <div className="space-y-4 border-t border-default pt-6">
        <h3 className="text-lg font-medium text-primary">Component Examples</h3>

        {/* Button Showcase */}
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-secondary">Buttons</h4>
          <div className="flex flex-wrap gap-3">
            <button className="btn btn-primary px-4 py-2">Primary Button</button>
            <button className="btn btn-secondary px-4 py-2">Secondary Button</button>
            <button className="btn btn-accent px-4 py-2">Accent Button</button>
            <button className="btn bg-color-1 text-white hover:opacity-90 px-4 py-2 rounded-lg transition-all">
              Custom Color 1
            </button>
            <button className="btn bg-color-3 text-white hover:opacity-90 px-4 py-2 rounded-lg transition-all">
              Custom Color 3
            </button>
          </div>
        </div>

        {/* Card Showcase */}
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-secondary">Cards & Elements</h4>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="card p-4 space-y-2">
              <div className="w-4 h-4 bg-color-1 rounded-full"></div>
              <h5 className="font-medium text-primary">Clean Card</h5>
              <p className="text-sm text-secondary">Minimalist design with subtle shadows</p>
            </div>
            <div className="card p-4 space-y-2">
              <div className="w-4 h-4 bg-color-3 rounded-full"></div>
              <h5 className="font-medium text-primary">Professional</h5>
              <p className="text-sm text-secondary">Enterprise-ready aesthetics</p>
            </div>
            <div className="card p-4 space-y-2">
              <div className="w-4 h-4 bg-color-5 rounded-full"></div>
              <h5 className="font-medium text-primary">Accessible</h5>
              <p className="text-sm text-secondary">WCAG compliant components</p>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  )
}
