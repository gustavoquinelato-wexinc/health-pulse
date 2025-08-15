import { motion } from 'framer-motion'
import CollapsedSidebar from '../components/CollapsedSidebar'
import Header from '../components/Header'
import useDocumentTitle from '../hooks/useDocumentTitle'
import FilterToolbar from '../components/FilterToolbar'

export default function DoraCombinedPage() {
  useDocumentTitle('DORA + Flow')

  return (
    <div className="min-h-screen bg-primary">
      <Header />
      <div className="flex">
        <CollapsedSidebar />
        <main className="flex-1 p-6 ml-16">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} className="space-y-6">
            <div className="space-y-2">
              <h1 className="text-3xl font-bold text-primary">DORA + FLOW</h1>
              <p className="text-secondary">Flow leading indicators aligned to DORA outcomes</p>
            </div>

            <FilterToolbar />

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="space-y-4">
                <h2 className="text-sm font-semibold text-secondary">Flow Indicators (Leading)</h2>
                <div className="bg-secondary border border-default rounded-lg p-4">
                  <div className="text-sm text-secondary mb-2">Cumulative Flow Diagram</div>
                  <div className="h-40 bg-tertiary rounded flex items-center justify-center text-secondary">SOON</div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="bg-secondary border border-default rounded-lg p-4">
                    <div className="text-sm text-secondary mb-2">Cycle Time</div>
                    <div className="h-24 bg-tertiary rounded flex items-center justify-center text-secondary">0</div>
                  </div>
                  <div className="bg-secondary border border-default rounded-lg p-4">
                    <div className="text-sm text-secondary mb-2">Lead Time (Issues)</div>
                    <div className="h-24 bg-tertiary rounded flex items-center justify-center text-secondary">0</div>
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="bg-secondary border border-default rounded-lg p-4">
                    <div className="text-sm text-secondary mb-2">WIP</div>
                    <div className="h-24 bg-tertiary rounded flex items-center justify-center text-secondary">0</div>
                  </div>
                  <div className="bg-secondary border border-default rounded-lg p-4">
                    <div className="text-sm text-secondary mb-2">Flow Efficiency</div>
                    <div className="h-24 bg-tertiary rounded flex items-center justify-center text-secondary">SOON</div>
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                <h2 className="text-sm font-semibold text-secondary">DORA Outcomes</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="bg-secondary border border-default rounded-lg p-4">
                    <div className="text-sm text-secondary mb-2">Lead Time for Changes</div>
                    <div className="h-24 bg-tertiary rounded flex items-center justify-center text-secondary">0</div>
                  </div>
                  <div className="bg-secondary border border-default rounded-lg p-4">
                    <div className="text-sm text-secondary mb-2">Deployment Frequency</div>
                    <div className="h-24 bg-tertiary rounded flex items-center justify-center text-secondary">0</div>
                  </div>
                  <div className="bg-secondary border border-default rounded-lg p-4">
                    <div className="text-sm text-secondary mb-2">Change Failure Rate</div>
                    <div className="h-24 bg-tertiary rounded flex items-center justify-center text-secondary">SOON</div>
                  </div>
                  <div className="bg-secondary border border-default rounded-lg p-4">
                    <div className="text-sm text-secondary mb-2">Time to Restore</div>
                    <div className="h-24 bg-tertiary rounded flex items-center justify-center text-secondary">SOON</div>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </main>
      </div>
    </div>
  )
}

