import React, { useEffect } from 'react'
import { useCentralizedAuth } from '../contexts/CentralizedAuthContext'
import { useNavigate } from 'react-router-dom'

export default function CentralizedLoginPage() {
  const { login, isAuthenticated, isLoading } = useCentralizedAuth()
  const navigate = useNavigate()

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/', { replace: true })
    }
  }, [isAuthenticated, navigate])

  // Auto-redirect to centralized auth service
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      // Small delay to show the page briefly
      const timer = setTimeout(() => {
        login()
      }, 1000)
      return () => clearTimeout(timer)
    }
  }, [isLoading, isAuthenticated, login])

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
        <div className="text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-white rounded-full shadow-lg mb-4">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
          <h2 className="text-xl font-semibold text-gray-800 mb-2">
            Loading...
          </h2>
          <p className="text-gray-600">
            Checking authentication status.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="text-center max-w-md mx-auto p-6">
        {/* Logo and Title */}
        <div className="inline-flex items-center justify-center w-20 h-20 bg-white rounded-full shadow-lg mb-6">
          <svg className="w-10 h-10 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
          </svg>
        </div>
        
        <h1 className="text-3xl font-bold text-gray-800 mb-2">
          Pulse Platform
        </h1>
        <p className="text-gray-600 mb-8">
          Frontend Application
        </p>

        {/* Loading State */}
        <div className="bg-white rounded-2xl p-8 shadow-xl">
          <div className="flex items-center justify-center mb-4">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
          <h2 className="text-lg font-semibold text-gray-800 mb-2">
            Redirecting to Sign In
          </h2>
          <p className="text-gray-600 text-sm mb-6">
            You will be redirected to the centralized authentication service.
          </p>
          
          {/* Manual Login Button */}
          <button
            onClick={login}
            className="w-full bg-blue-600 text-white font-semibold py-3 px-4 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-all duration-200 transform hover:scale-[1.02]"
          >
            <svg className="w-5 h-5 inline-block mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1" />
            </svg>
            Sign In Now
          </button>
        </div>

        {/* Info */}
        <div className="mt-8">
          <p className="text-gray-500 text-xs">
            <svg className="w-4 h-4 inline-block mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 0h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
            Secure authentication powered by Pulse Platform
          </p>
        </div>
      </div>
    </div>
  )
}
