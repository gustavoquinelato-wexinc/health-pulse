import { useState, useEffect, lazy, Suspense } from 'react'
import { useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { List, RefreshCw, Sliders, GitBranch, Workflow, Loader2 } from 'lucide-react'
import Header from '../components/Header'
import CollapsedSidebar from '../components/CollapsedSidebar'

// Lazy load page components to use as tabs
const WitsHierarchiesPage = lazy(() => import('./WitsHierarchiesPage'))
const WitsMappingsPage = lazy(() => import('./WitsMappingsPage'))
const StatusesMappingsPage = lazy(() => import('./StatusesMappingsPage'))
const WorkflowsPage = lazy(() => import('./WorkflowsPage'))
const CustomFieldMappingPage = lazy(() => import('./CustomFieldMappingPage'))

type Tab = 'wits-hierarchies' | 'wits-mappings' | 'statuses-mappings' | 'workflows' | 'custom-fields'

export default function MappingsPage() {
  const [searchParams, setSearchParams] = useSearchParams()

  // Initialize active tab from URL or default to 'wits-hierarchies'
  const [activeTab, setActiveTab] = useState<Tab>(() => {
    const tabFromUrl = searchParams.get('tab') as Tab
    const validTabs: Tab[] = ['wits-hierarchies', 'wits-mappings', 'statuses-mappings', 'workflows', 'custom-fields']
    return validTabs.includes(tabFromUrl) ? tabFromUrl : 'wits-hierarchies'
  })

  // Set document title based on active tab
  useEffect(() => {
    const titles: Record<Tab, string> = {
      'wits-hierarchies': 'Work Item Types - Hierarchies',
      'wits-mappings': 'Work Item Types - Mappings',
      'statuses-mappings': 'Statuses - Mappings',
      'workflows': 'Workflows',
      'custom-fields': 'Custom Fields - Mappings'
    }
    document.title = `${titles[activeTab]} - PEM`
  }, [activeTab])

  const tabs = [
    { id: 'wits-hierarchies' as Tab, label: 'WIT Hierarchies', icon: GitBranch },
    { id: 'wits-mappings' as Tab, label: 'WIT Mappings', icon: List },
    { id: 'statuses-mappings' as Tab, label: 'Status Mappings', icon: RefreshCw },
    { id: 'workflows' as Tab, label: 'Workflows', icon: Workflow },
    { id: 'custom-fields' as Tab, label: 'Custom Fields', icon: Sliders }
  ]

  // Handle tab change and update URL
  const handleTabChange = (tab: Tab) => {
    setActiveTab(tab)
    setSearchParams({ tab })
  }

  const renderTabContent = () => {
    switch (activeTab) {
      case 'wits-hierarchies':
        return <WitsHierarchiesPage embedded />
      case 'wits-mappings':
        return <WitsMappingsPage embedded />
      case 'statuses-mappings':
        return <StatusesMappingsPage embedded />
      case 'workflows':
        return <WorkflowsPage embedded />
      case 'custom-fields':
        return <CustomFieldMappingPage embedded />
      default:
        return null
    }
  }

  return (
    <div className="min-h-screen bg-primary">
      <Header />

      <div className="flex">
        <CollapsedSidebar />

        <main className="flex-1 ml-16 py-8">
          <div className="ml-12 mr-12">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="space-y-6"
            >
              {/* Page Header */}
              <div className="space-y-2">
                <h1 className="text-3xl font-bold text-primary">
                  MAPPINGS
                </h1>
                <p className="text-secondary">
                  Configure work item types, statuses, workflows, and custom field mappings
                </p>
              </div>

              {/* Tabs */}
              <div className="border-b border-default">
                <nav className="flex space-x-8">
                  {tabs.map((tab) => (
                    <button
                      key={tab.id}
                      onClick={() => handleTabChange(tab.id)}
                      className={`py-3 px-1 border-b-2 font-medium text-sm flex items-center space-x-2 transition-colors ${
                        activeTab === tab.id
                          ? 'border-primary text-primary'
                          : 'border-transparent text-secondary hover:text-primary hover:border-gray-300'
                      }`}
                    >
                      <tab.icon className="w-4 h-4" />
                      <span>{tab.label}</span>
                    </button>
                  ))}
                </nav>
              </div>

              {/* Tab Content */}
              <motion.div
                key={activeTab}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
              >
                <Suspense fallback={
                  <div className="text-center py-12">
                    <Loader2 className="h-12 w-12 animate-spin mx-auto mb-4 text-primary" />
                    <p className="text-secondary">Loading...</p>
                  </div>
                }>
                  {renderTabContent()}
                </Suspense>
              </motion.div>
            </motion.div>
          </div>
        </main>
      </div>
    </div>
  )
}

