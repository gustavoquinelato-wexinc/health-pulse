import { Navigate, Route, BrowserRouter as Router, Routes } from 'react-router-dom'
import AdminRoute from './components/AdminRoute'
import TenantErrorBoundary from './components/ClientErrorBoundary'
import ProtectedRoute from './components/ProtectedRoute'
import { AuthProvider } from './contexts/AuthContext'
import { ThemeProvider } from './contexts/ThemeContext'

import AuthCallbackPage from './pages/AuthCallbackPage'
import HomePage from './pages/HomePage'
import LoginPage from './pages/LoginPage'
import NotFoundPage from './pages/NotFoundPage'
import UserPreferencesPage from './pages/UserPreferencesPage'

// ETL-specific pages
import WitsMappingsPage from './pages/WitsMappingsPage'
import WitsHierarchiesPage from './pages/WitsHierarchiesPage'
import StatusesMappingsPage from './pages/StatusesMappingsPage'
import WorkflowsPage from './pages/WorkflowsPage'
import IntegrationsPage from './pages/IntegrationsPage'
import QdrantPage from './pages/QdrantPage'

// Phase 2.1: Custom Fields Management pages
import CustomFieldMappingPage from './pages/CustomFieldMappingPage'

// Queue Management page
import QueueManagementPage from './pages/QueueManagementPage'

function App() {
  return (
    <TenantErrorBoundary>
      <AuthProvider>
        <ThemeProvider>
          <Router
            future={{
              v7_startTransition: true,
              v7_relativeSplatPath: true
            }}
          >
            <div className="min-h-screen bg-primary transition-colors duration-200">
              <Routes>
                {/* Authentication Routes */}
                <Route path="/login" element={<LoginPage />} />
                <Route path="/auth/callback" element={<AuthCallbackPage />} />

                {/* Main Routes */}
                <Route
                  path="/home"
                  element={
                    <ProtectedRoute>
                      <HomePage />
                    </ProtectedRoute>
                  }
                />

                {/* ETL Management Routes - Admin Only */}
                <Route
                  path="/wits-mappings"
                  element={
                    <AdminRoute>
                      <WitsMappingsPage />
                    </AdminRoute>
                  }
                />
                <Route
                  path="/wits-hierarchies"
                  element={
                    <AdminRoute>
                      <WitsHierarchiesPage />
                    </AdminRoute>
                  }
                />
                <Route
                  path="/statuses-mappings"
                  element={
                    <AdminRoute>
                      <StatusesMappingsPage />
                    </AdminRoute>
                  }
                />
                <Route
                  path="/workflows"
                  element={
                    <AdminRoute>
                      <WorkflowsPage />
                    </AdminRoute>
                  }
                />
                <Route
                  path="/integrations"
                  element={
                    <AdminRoute>
                      <IntegrationsPage />
                    </AdminRoute>
                  }
                />

                {/* Phase 2.1: Custom Fields Management Routes - Admin Only */}
                <Route
                  path="/custom-fields-mappings"
                  element={
                    <AdminRoute>
                      <CustomFieldMappingPage />
                    </AdminRoute>
                  }
                />

                {/* Queue Management Routes - Admin Only */}
                <Route
                  path="/queue-management"
                  element={
                    <AdminRoute>
                      <QueueManagementPage />
                    </AdminRoute>
                  }
                />

                {/* Personal Settings Routes - Accessible to all users */}
                <Route
                  path="/profile"
                  element={
                    <ProtectedRoute>
                      <UserPreferencesPage />
                    </ProtectedRoute>
                  }
                />

                {/* Admin Routes - Admin only */}
                <Route
                  path="/qdrant"
                  element={
                    <AdminRoute>
                      <QdrantPage />
                    </AdminRoute>
                  }
                />

                <Route path="/" element={<Navigate to="/home" replace />} />

                {/* 404 Not Found - Must be last route */}
                <Route path="*" element={<NotFoundPage />} />
              </Routes>
            </div>
          </Router>
        </ThemeProvider>
      </AuthProvider>
    </TenantErrorBoundary >
  )
}

export default App
