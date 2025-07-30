import { motion } from 'framer-motion'
import { useNavigate, useParams } from 'react-router-dom'
import CollapsedSidebar from '../components/CollapsedSidebar'
import Header from '../components/Header'
import { useAuth } from '../contexts/AuthContext'

interface ETLPageConfig {
  title: string
  description: string
  servicePath: string
}

// Configuration for different ETL pages (ordered to match ETL admin menu)
const ETL_PAGES: Record<string, ETLPageConfig> = {
  'dashboard': {
    title: 'ETL Home',
    description: 'Monitor and control ETL job execution',
    servicePath: '/home'
  },
  'admin': {
    title: 'ETL Admin Panel',
    description: 'Manage ETL system configuration and settings',
    servicePath: '/admin'
  },
  'issuetype-mappings': {
    title: 'Issue Type Mappings',
    description: 'Configure Jira issue type hierarchies and mappings',
    servicePath: '/admin/issuetype-mappings'
  },
  'issuetype-hierarchies': {
    title: 'Issue Type Hierarchies',
    description: 'Manage issue type hierarchy levels and relationships',
    servicePath: '/admin/issuetype-hierarchies'
  },
  'status-mappings': {
    title: 'Status Mappings',
    description: 'Configure Jira status to workflow step mappings',
    servicePath: '/admin/status-mappings'
  },
  'workflows': {
    title: 'Workflow Management',
    description: 'Define and manage workflow steps and configurations',
    servicePath: '/admin/workflows'
  }
}

export default function ETLManagementPage() {
  const { page = 'dashboard' } = useParams<{ page: string }>()
  const navigate = useNavigate()
  const { user, isAdmin } = useAuth()

  // Check if user is admin - ETL Management is admin-only
  if (!isAdmin) {
    return (
      <div className="min-h-screen bg-primary">
        <Header />
        <div className="flex">
          <CollapsedSidebar />
          <main className="flex-1 ml-16">
            <div className="flex items-center justify-center h-[calc(100vh-80px)]">
              <div className="text-center">
                <div className="text-6xl mb-4">🔒</div>
                <h1 className="text-2xl font-bold text-primary mb-2">Access Denied</h1>
                <p className="text-secondary mb-4">ETL Management requires administrator privileges.</p>
                <button
                  onClick={() => navigate('/')}
                  className="px-4 py-2 bg-color-1 text-white rounded-lg hover:bg-opacity-90 transition-colors"
                >
                  Return to Home
                </button>
              </div>
            </div>
          </main>
        </div>
      </div>
    )
  }

  // Get page configuration or default to dashboard
  const pageConfig = ETL_PAGES[page] || ETL_PAGES['dashboard']

  return (
    <div className="min-h-screen bg-primary">
      <Header />

      <div className="flex">
        <CollapsedSidebar />

        <main className="flex-1 ml-16">
          {/* Page Header */}
          <div className="bg-secondary border-b border-default px-6 py-4">
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
              className="space-y-1"
            >
              {/* Back navigation for subpages */}
              {page && page !== 'dashboard' && (
                <div className="flex items-center space-x-3 mb-2">
                  <button
                    onClick={() => navigate('/etl')}
                    className="text-secondary hover:text-primary transition-colors"
                  >
                    ← Back to ETL Management
                  </button>
                </div>
              )}

              <h1 className="text-2xl font-bold text-primary">
                {pageConfig.title}
              </h1>
              <p className="text-secondary text-sm">
                {pageConfig.description}
              </p>
            </motion.div>
          </div>

          {/* ETL Service Frame */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="h-[calc(100vh-140px)]"
          >
            {/* Iframe with authentication token */}
            {(() => {
              // Get authentication token
              const getAuthToken = () => {
                // Try localStorage first (primary storage)
                let token = localStorage.getItem('pulse_token')

                // Fallback to cookies if localStorage is empty
                if (!token) {
                  const cookies = document.cookie.split(';')
                  const tokenCookie = cookies.find(cookie =>
                    cookie.trim().startsWith('pulse_token=')
                  )
                  if (tokenCookie) {
                    token = tokenCookie.split('=')[1]
                  }
                }

                return token
              }

              // Build iframe URL with authentication and theme parameters
              const token = getAuthToken()
              const serviceUrl = import.meta.env.VITE_ETL_SERVICE_URL || 'http://localhost:8000'
              const baseUrl = `${serviceUrl}${pageConfig.servicePath}`

              const params = new URLSearchParams({
                embedded: 'true',
                theme: 'light',
                colorMode: 'default'
              })

              // Add token if available
              if (token) {
                params.set('token', token)
              }

              const iframeUrl = `${baseUrl}?${params.toString()}`

              return (
                <iframe
                  src={iframeUrl}
                  className="w-full h-full border-0 bg-primary"
                  title={`ETL Management - ${pageConfig.servicePath}`}
                  sandbox="allow-same-origin allow-scripts allow-forms allow-popups allow-modals"
                />
              )
            })()}
          </motion.div>
        </main>
      </div>
    </div>
  )
}

// Export individual page components for specific routes if needed
export function ETLDashboardPage() {
  return <ETLManagementPage />
}

export function ETLAdminPage() {
  return <ETLManagementPage />
}

export function StatusMappingsPage() {
  return <ETLManagementPage />
}

export function IssueTypeMappingsPage() {
  return <ETLManagementPage />
}

export function WorkflowsPage() {
  return <ETLManagementPage />
}

export function IssueTypeHierarchiesPage() {
  return <ETLManagementPage />
}
