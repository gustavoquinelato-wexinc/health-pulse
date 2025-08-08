import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export default function AuthCallbackPage() {
  const navigate = useNavigate()
  const { isAuthenticated } = useAuth()

  useEffect(() => {
    // Since we're not using OAuth callback flow anymore,
    // just redirect to appropriate page
    if (isAuthenticated) {
      navigate('/home', { replace: true })
    } else {
      navigate('/login', { replace: true })
    }
  }, [isAuthenticated, navigate])

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-white rounded-full shadow-lg mb-4">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
        <h2 className="text-xl font-semibold text-gray-800 mb-2">
          Redirecting...
        </h2>
        <p className="text-gray-600">
          Please wait while we redirect you.
        </p>
      </div>
    </div>
  )
}
