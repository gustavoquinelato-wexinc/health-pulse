import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import CollapsedSidebar from '../components/CollapsedSidebar'
import ColorSchemaPanel from '../components/ColorSchemaPanel'
import Header from '../components/Header'
import useDocumentTitle from '../hooks/useDocumentTitle'

export default function ColorSchemeSettingsPage() {
  const navigate = useNavigate()

  // Set document title
  useDocumentTitle('Color Scheme Settings')

  return (
    <div className="min-h-screen bg-primary">
      <Header />

      <div className="flex">
        <CollapsedSidebar />

        <main className="flex-1 p-6 ml-16">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="space-y-6"
          >
            <div className="space-y-2">
              <div className="flex items-center space-x-3">
                <button
                  onClick={() => navigate('/admin')}
                  className="text-secondary hover:text-primary transition-colors"
                >
                  ← Back to Admin Settings
                </button>
              </div>
              <h1 className="text-3xl font-bold text-primary">
                Color Scheme Settings
              </h1>
              <p className="text-secondary">
                Customize your platform's color palette and theme preferences
              </p>
            </div>

            {/* Color Schema Panel */}
            <ColorSchemaPanel />
          </motion.div>
        </main>
      </div>
    </div>
  )
}
