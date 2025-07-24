import { motion } from 'framer-motion'
import Header from '../components/Header'
import CollapsedSidebar from '../components/CollapsedSidebar'

export default function EngineeringAnalyticsPage() {
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
              <h1 className="text-3xl font-bold text-primary">
                Engineering Analytics
              </h1>
              <p className="text-secondary">
                Comprehensive engineering performance metrics and insights
              </p>
            </div>
          </motion.div>
        </main>
      </div>
    </div>
  )
}
