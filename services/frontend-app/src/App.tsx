import { Navigate, Route, BrowserRouter as Router, Routes } from 'react-router-dom'
import AdminRoute from './components/AdminRoute'
import ClientErrorBoundary from './components/ClientErrorBoundary'
import ProtectedRoute from './components/ProtectedRoute'
import { AuthProvider } from './contexts/AuthContext'
import { ThemeProvider } from './contexts/ThemeContext'
import ChangeFailureRatePage from './pages/ChangeFailureRatePage'
import ColorSchemeSettingsPage from './pages/ColorSchemeSettingsPage'
import DeploymentFrequencyPage from './pages/DeploymentFrequencyPage'
import DoraOverviewPage from './pages/DoraOverviewPage'
import EngineeringAnalyticsPage from './pages/EngineeringAnalyticsPage'

import ClientManagementPage from './pages/ClientManagementPage'
import HomePage from './pages/HomePage'
import HomePageBackup from './pages/HomePageBackup'
import HomePageOptionB from './pages/HomePageOptionB'
import LeadTimeForChangesPage from './pages/LeadTimeForChangesPage'
import LoginPage from './pages/LoginPage'
import NotificationsPage from './pages/NotificationsPage'
import SettingsPage from './pages/SettingsPage'
import TimeToRestorePage from './pages/TimeToRestorePage'
import UserManagementPage from './pages/UserManagementPage'
import UserPreferencesPage from './pages/UserPreferencesPage'

function App() {
  return (
    <ClientErrorBoundary>
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
                <Route path="/login" element={<LoginPage />} />

                {/* Main Routes */}
                <Route
                  path="/home"
                  element={
                    <ProtectedRoute>
                      <HomePage />
                    </ProtectedRoute>
                  }
                />

                {/* Alternative Homepage Routes (accessible by direct URL) */}
                <Route
                  path="/home-backup"
                  element={
                    <ProtectedRoute>
                      <HomePageBackup />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/home-option-b"
                  element={
                    <ProtectedRoute>
                      <HomePageOptionB />
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

                {/* Engineering Analytics Route */}
                <Route
                  path="/engineering"
                  element={
                    <ProtectedRoute>
                      <EngineeringAnalyticsPage />
                    </ProtectedRoute>
                  }
                />



                {/* Settings Routes */}
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
                      <ClientManagementPage />
                    </AdminRoute>
                  }
                />
                <Route
                  path="/settings/user-preferences"
                  element={
                    <AdminRoute>
                      <UserPreferencesPage />
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

                <Route path="/" element={<Navigate to="/home" replace />} />
              </Routes>
            </div>
          </Router>
        </ThemeProvider>
      </AuthProvider>
    </ClientErrorBoundary>
  )
}

export default App
