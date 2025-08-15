import { motion } from 'framer-motion'
import CollapsedSidebar from '../../../components/CollapsedSidebar'
import Header from '../../../components/Header'
import useDocumentTitle from '../../../hooks/useDocumentTitle'
import FilterToolbar from '../../../components/FilterToolbar'

export default function BranchingPage() {
  useDocumentTitle('Engineering - Branching & Merge Strategy')

  return (
    <div className="min-h-screen bg-primary">
      <Header />
      <div className="flex">
        <CollapsedSidebar />
        <main className="flex-1 p-6 ml-16">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} className="space-y-6">
            <div className="space-y-2">
              <h1 className="text-3xl font-bold text-primary">BRANCHING & MERGE STRATEGY</h1>
              <p className="text-secondary">Leading indicators for DORA Deployment Frequency</p>
            </div>

            <FilterToolbar />

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-secondary border border-default rounded-lg p-4">
                <div className="text-sm text-secondary mb-2">Default Branch</div>
                <div className="h-24 bg-tertiary rounded flex items-center justify-center text-secondary">SOON</div>
              </div>
              <div className="bg-secondary border border-default rounded-lg p-4">
                <div className="text-sm text-secondary mb-2">Merge Strategy</div>
                <div className="h-24 bg-tertiary rounded flex items-center justify-center text-secondary">SOON</div>
              </div>
            </div>
          </motion.div>
        </main>
      </div>
    </div>
  )
}

