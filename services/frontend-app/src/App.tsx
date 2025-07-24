import { Navigate, Route, BrowserRouter as Router, Routes } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'
import { AuthProvider } from './contexts/AuthContext'
import { ThemeProvider } from './contexts/ThemeContext'
import ChangeFailureRatePage from './pages/ChangeFailureRatePage'
import DeploymentFrequencyPage from './pages/DeploymentFrequencyPage'
import DoraOverviewPage from './pages/DoraOverviewPage'
import EngineeringAnalyticsPage from './pages/EngineeringAnalyticsPage'
import HomePage from './pages/HomePage'
import HomePageBackup from './pages/HomePageBackup'
import HomePageOptionB from './pages/HomePageOptionB'
import LeadTimeForChangesPage from './pages/LeadTimeForChangesPage'
import LoginPage from './pages/LoginPage'
import SettingsPage from './pages/SettingsPage'
import TimeToRestorePage from './pages/TimeToRestorePage'

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
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

              {/* Settings Route */}
              <Route
                path="/settings"
                element={
                  <ProtectedRoute>
                    <SettingsPage />
                  </ProtectedRoute>
                }
              />

              <Route path="/" element={<Navigate to="/home" replace />} />
            </Routes>
          </div>
        </Router>
      </AuthProvider>
    </ThemeProvider>
  )
}

export default App
