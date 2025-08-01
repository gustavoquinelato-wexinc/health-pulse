import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import CollapsedSidebar from '../components/CollapsedSidebar'
import Header from '../components/Header'
import useDocumentTitle from '../hooks/useDocumentTitle'

export default function TimeToRestorePage() {
  const navigate = useNavigate()

  // Set document title
  useDocumentTitle('Time to Restore')
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
                  onClick={() => navigate('/dora')}
                  className="text-secondary hover:text-primary transition-colors"
                >
                  ← Back to DORA Metrics
                </button>
              </div>
              <h1 className="text-3xl font-bold text-primary">
                Time to Restore Service
              </h1>
              <p className="text-secondary">
                How quickly your team recovers from failures
              </p>
            </div>
          </motion.div>
        </main>
      </div>
    </div>
  )
}
