import React from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import { ThemeProvider } from './contexts/ThemeContext'
import LoginPage from './pages/LoginPage'
import HomePage from './pages/HomePage'
import ProtectedRoute from './components/ProtectedRoute'

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <Router>
          <div className="min-h-screen bg-primary transition-colors duration-200">
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route 
                path="/home" 
                element={
                  <ProtectedRoute>
                    <HomePage />
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
