import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import CollapsedSidebar from '../components/CollapsedSidebar'
import Header from '../components/Header'

export default function DeploymentFrequencyPage() {
  const navigate = useNavigate()
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
                Deployment Frequency
              </h1>
              <p className="text-secondary">
                How often your team deploys code to production
              </p>
            </div>
          </motion.div>
        </main>
      </div>
    </div>
  )
}
