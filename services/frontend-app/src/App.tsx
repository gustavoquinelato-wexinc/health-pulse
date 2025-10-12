import { Navigate, Route, BrowserRouter as Router, Routes } from 'react-router-dom'
import AdminRoute from './components/AdminRoute'
import TenantErrorBoundary from './components/ClientErrorBoundary'
import ProtectedRoute from './components/ProtectedRoute'
import { AuthProvider } from './contexts/AuthContext'
import { ThemeProvider } from './contexts/ThemeContext'
import ChangeFailureRatePage from './pages/ChangeFailureRatePage'
import ColorSchemeSettingsPage from './pages/ColorSchemeSettingsPage'
import DeploymentFrequencyPage from './pages/DeploymentFrequencyPage'
import DoraCombinedPage from './pages/DoraCombinedPage'
import DoraOverviewPage from './pages/DoraOverviewPage'

import AuthCallbackPage from './pages/AuthCallbackPage'
import TenantManagementPage from './pages/TenantManagementPage'
import HomePage from './pages/HomePage'
import LeadTimeForChangesPage from './pages/LeadTimeForChangesPage'
import LoginPage from './pages/LoginPage'
import NotFoundPage from './pages/NotFoundPage'
import NotificationsPage from './pages/NotificationsPage'
import SettingsPage from './pages/SettingsPage'
import TimeToRestorePage from './pages/TimeToRestorePage'
import UserManagementPage from './pages/UserManagementPage'
import UserPreferencesPage from './pages/UserPreferencesPage'
import AIConfigurationPage from './pages/ai/AIConfigurationPage'
import AIPerformancePage from './pages/ai/AIPerformancePage'


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



                {/* DORA Metrics Routes */}
                <Route
                  path="/dora"
                  element={
                    <ProtectedRoute>
                      <DoraOverviewPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/dora/combined"
                  element={
                    <ProtectedRoute>
                      <DoraCombinedPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/dora/deployment-frequency"
                  element={
                    <ProtectedRoute>
                      <DeploymentFrequencyPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/dora/lead-time"
                  element={
                    <ProtectedRoute>
                      <LeadTimeForChangesPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/dora/time-to-restore"
                  element={
                    <ProtectedRoute>
                      <TimeToRestorePage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/dora/change-failure-rate"
                  element={
                    <ProtectedRoute>
                      <ChangeFailureRatePage />
                    </ProtectedRoute>
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

                {/* Settings Routes - Admin only */}
                <Route
                  path="/settings"
                  element={
                    <AdminRoute>
                      <SettingsPage />
                    </AdminRoute>
                  }
                />
                <Route
                  path="/settings/color-scheme"
                  element={
                    <AdminRoute>
                      <ColorSchemeSettingsPage />
                    </AdminRoute>
                  }
                />
                <Route
                  path="/settings/user-management"
                  element={
                    <AdminRoute>
                      <UserManagementPage />
                    </AdminRoute>
                  }
                />
                <Route
                  path="/settings/client-management"
                  element={
                    <AdminRoute>
                      <TenantManagementPage />
                    </AdminRoute>
                  }
                />
                <Route
                  path="/settings/notifications"
                  element={
                    <AdminRoute>
                      <NotificationsPage />
                    </AdminRoute>
                  }
                />
                <Route
                  path="/settings/ai-config"
                  element={
                    <AdminRoute>
                      <AIConfigurationPage />
                    </AdminRoute>
                  }
                />
                <Route
                  path="/settings/ai-performance"
                  element={
                    <AdminRoute>
                      <AIPerformancePage />
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
