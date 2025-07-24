import { motion } from 'framer-motion'
import ColorSchemaPanel from '../components/ColorSchemaPanel'
import DashboardGrid from '../components/DashboardGrid'
import Header from '../components/Header'
import StaticSidebarWithHighlights from '../components/StaticSidebarWithHighlights'
import { useAuth } from '../contexts/AuthContext'

export default function HomePageOptionB() {
  const { user } = useAuth()

  return (
    <div className="min-h-screen bg-primary">
      {/* Header */}
      <Header />

      <div className="flex">
        {/* Static Sidebar with Highlights */}
        <StaticSidebarWithHighlights />

        {/* Main Content */}
        <main className="flex-1 p-6 ml-64">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="space-y-6"
          >
            {/* Welcome Section */}
            <div className="space-y-2">
              <h1 className="text-3xl font-bold text-primary">
                Welcome back, {user?.name || user?.email}! 👋
              </h1>
              <p className="text-secondary">
                Here's your analytics dashboard with interactive highlighting (Option B)
              </p>
            </div>

            {/* Dashboard Grid */}
            <DashboardGrid />

            {/* Color Schema Panel */}
            <ColorSchemaPanel />
          </motion.div>
        </main>
      </div>
    </div>
  )
}
