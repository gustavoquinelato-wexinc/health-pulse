import { Navigate, Route, BrowserRouter as Router, Routes } from 'react-router-dom'
import AdminRoute from './components/AdminRoute'
import ClientErrorBoundary from './components/ClientErrorBoundary'
import ProtectedRoute from './components/ProtectedRoute'
import { AuthProvider } from './contexts/AuthContext'
import { ThemeProvider } from './contexts/ThemeContext'
import ChangeFailureRatePage from './pages/ChangeFailureRatePage'
import ColorSchemeSettingsPage from './pages/ColorSchemeSettingsPage'
import DeploymentFrequencyPage from './pages/DeploymentFrequencyPage'
import DoraCombinedPage from './pages/DoraCombinedPage'
import DoraOverviewPage from './pages/DoraOverviewPage'
import EngineeringAnalyticsPage from './pages/EngineeringAnalyticsPage'

import AuthCallbackPage from './pages/AuthCallbackPage'
import ClientManagementPage from './pages/ClientManagementPage'
import HomePage from './pages/HomePage'
import LeadTimeForChangesPage from './pages/LeadTimeForChangesPage'
import LoginPage from './pages/LoginPage'
import NotificationsPage from './pages/NotificationsPage'
import SettingsPage from './pages/SettingsPage'
import TimeToRestorePage from './pages/TimeToRestorePage'
import UserManagementPage from './pages/UserManagementPage'
import UserPreferencesPage from './pages/UserPreferencesPage'
import BranchingPage from './pages/engineering/Deployments/BranchingPage'
import CadencePage from './pages/engineering/Deployments/CadencePage'
import FlowEfficiencyPage from './pages/engineering/LeadTime/FlowEfficiencyPage'
import PRLifecyclePage from './pages/engineering/LeadTime/PRLifecyclePage'
import ReviewsPage from './pages/engineering/LeadTime/ReviewsPage'
import WipBatchPage from './pages/engineering/LeadTime/WipBatchPage'
import HotfixesPage from './pages/engineering/Quality/HotfixesPage'
import PostReleasePage from './pages/engineering/Quality/PostReleasePage'
import IncidentsPage from './pages/engineering/Reliability/IncidentsPage'
import RecoveryPage from './pages/engineering/Reliability/RecoveryPage'


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

                {/* Engineering Analytics Routes */}
                <Route
                  path="/engineering"
                  element={
                    <ProtectedRoute>
                      <EngineeringAnalyticsPage />
                    </ProtectedRoute>
                  }
                />
                {/* Lead-Time Drivers */}
                <Route path="/engineering/lead-time" element={<ProtectedRoute><EngineeringAnalyticsPage /></ProtectedRoute>} />
                <Route path="/engineering/lead-time/pr-lifecycle" element={<ProtectedRoute><PRLifecyclePage /></ProtectedRoute>} />
                <Route path="/engineering/lead-time/reviews" element={<ProtectedRoute><ReviewsPage /></ProtectedRoute>} />
                <Route path="/engineering/lead-time/wip-batch" element={<ProtectedRoute><WipBatchPage /></ProtectedRoute>} />
                <Route path="/engineering/lead-time/flow-efficiency" element={<ProtectedRoute><FlowEfficiencyPage /></ProtectedRoute>} />
                {/* Deployment Drivers */}
                <Route path="/engineering/deployments" element={<ProtectedRoute><EngineeringAnalyticsPage /></ProtectedRoute>} />
                <Route path="/engineering/deployments/branching" element={<ProtectedRoute><BranchingPage /></ProtectedRoute>} />
                <Route path="/engineering/deployments/cadence" element={<ProtectedRoute><CadencePage /></ProtectedRoute>} />
                {/* Quality Drivers */}
                <Route path="/engineering/quality" element={<ProtectedRoute><EngineeringAnalyticsPage /></ProtectedRoute>} />
                <Route path="/engineering/quality/post-release" element={<ProtectedRoute><PostReleasePage /></ProtectedRoute>} />
                <Route path="/engineering/quality/hotfixes" element={<ProtectedRoute><HotfixesPage /></ProtectedRoute>} />
                {/* Reliability Drivers */}
                <Route path="/engineering/reliability" element={<ProtectedRoute><EngineeringAnalyticsPage /></ProtectedRoute>} />
                <Route path="/engineering/reliability/incidents" element={<ProtectedRoute><IncidentsPage /></ProtectedRoute>} />
                <Route path="/engineering/reliability/recovery" element={<ProtectedRoute><RecoveryPage /></ProtectedRoute>} />



                {/* Personal Settings Routes - Accessible to all users */}
                <Route
                  path="/profile"
                  element={
                    <ProtectedRoute>
                      <UserPreferencesPage />
                    </ProtectedRoute>
                  }
                />

                {/* Admin Settings Routes - Admin only */}
                <Route
                  path="/admin"
                  element={
                    <AdminRoute>
                      <SettingsPage />
                    </AdminRoute>
                  }
                />
                <Route
                  path="/admin/color-scheme"
                  element={
                    <AdminRoute>
                      <ColorSchemeSettingsPage />
                    </AdminRoute>
                  }
                />
                <Route
                  path="/admin/user-management"
                  element={
                    <AdminRoute>
                      <UserManagementPage />
                    </AdminRoute>
                  }
                />
                <Route
                  path="/admin/client-management"
                  element={
                    <AdminRoute>
                      <ClientManagementPage />
                    </AdminRoute>
                  }
                />
                <Route
                  path="/admin/notifications"
                  element={
                    <AdminRoute>
                      <NotificationsPage />
                    </AdminRoute>
                  }
                />

                {/* Legacy redirects for backward compatibility */}
                <Route path="/settings" element={<Navigate to="/admin" replace />} />
                <Route path="/settings/color-scheme" element={<Navigate to="/admin/color-scheme" replace />} />
                <Route path="/settings/user-management" element={<Navigate to="/admin/user-management" replace />} />
                <Route path="/settings/client-management" element={<Navigate to="/admin/client-management" replace />} />
                <Route path="/settings/user-preferences" element={<Navigate to="/profile" replace />} />
                <Route path="/settings/notifications" element={<Navigate to="/admin/notifications" replace />} />

                <Route path="/" element={<Navigate to="/home" replace />} />
              </Routes>
            </div>
          </Router>
        </ThemeProvider>
      </AuthProvider>
    </ClientErrorBoundary >
  )
}

export default App
