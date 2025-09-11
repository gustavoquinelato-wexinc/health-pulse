import { motion } from 'framer-motion'
import { AlertTriangle, ArrowLeft, Home } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import useDocumentTitle from '../hooks/useDocumentTitle'

export default function NotFoundPage() {
  const navigate = useNavigate()
  const { isAuthenticated } = useAuth()

  // Set document title
  useDocumentTitle('Page Not Found')

  const handleGoBack = () => {
    if (window.history.length > 1) {
      navigate(-1)
    } else {
      navigate(isAuthenticated ? '/home' : '/')
    }
  }

  const handleGoHome = () => {
    navigate(isAuthenticated ? '/home' : '/')
  }

  return (
    <div className="min-h-screen bg-primary flex items-center justify-center px-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="max-w-2xl mx-auto text-center"
      >
        {/* 404 Icon */}
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ delay: 0.2, type: "spring", stiffness: 200 }}
          className="mb-8"
        >
          <AlertTriangle className="w-24 h-24 text-color-3 mx-auto opacity-80" />
        </motion.div>

        {/* Error Message */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4 }}
          className="card p-8 mb-8"
        >
          <h1 className="text-6xl font-bold mb-4 text-primary">404</h1>
          <h2 className="text-2xl font-semibold mb-4 text-primary">Page Not Found</h2>
          <p className="text-lg mb-6 text-secondary">
            The page you're looking for doesn't exist or has been moved.
          </p>

          {/* Helpful Information */}
          <div className="bg-muted rounded-lg p-4 mb-6 text-left">
            <h3 className="font-semibold mb-3 text-primary flex items-center">
              <AlertTriangle className="w-4 h-4 mr-2" />
              What you can do:
            </h3>
            <ul className="space-y-2 text-secondary">
              <li className="flex items-center">
                <span className="w-2 h-2 bg-color-3 rounded-full mr-3"></span>
                Check the URL for typos
              </li>
              <li className="flex items-center">
                <span className="w-2 h-2 bg-color-3 rounded-full mr-3"></span>
                Use the navigation menu to find what you need
              </li>
              <li className="flex items-center">
                <span className="w-2 h-2 bg-color-3 rounded-full mr-3"></span>
                Go back to the previous page
              </li>
            </ul>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <button
              onClick={handleGoHome}
              className="btn-crud-create flex items-center justify-center space-x-2"
            >
              <Home className="w-4 h-4" />
              <span>Return to Home</span>
            </button>
            <button
              onClick={handleGoBack}
              className="btn-neutral-tertiary flex items-center justify-center space-x-2"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Go Back</span>
            </button>
          </div>
        </motion.div>

        {/* Additional Help */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 }}
          className="text-sm text-muted"
        >
          <p>If you believe this is an error, please contact your system administrator.</p>
        </motion.div>
      </motion.div>

      {/* Background Animation */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <motion.div
          animate={{
            x: [0, 100, 0],
            y: [0, -100, 0],
          }}
          transition={{
            duration: 20,
            repeat: Infinity,
            ease: "linear"
          }}
          className="absolute -top-40 -right-40 w-80 h-80 bg-color-1 bg-opacity-5 rounded-full"
        />
        <motion.div
          animate={{
            x: [0, -100, 0],
            y: [0, 100, 0],
          }}
          transition={{
            duration: 25,
            repeat: Infinity,
            ease: "linear"
          }}
          className="absolute -bottom-40 -left-40 w-80 h-80 bg-color-2 bg-opacity-5 rounded-full"
        />
      </div>
    </div>
  )
}
