import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'

export default function NotFoundPage() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-primary flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="max-w-md w-full text-center"
      >
        <div className="mb-8">
          <div className="w-24 h-24 mx-auto mb-6 rounded-full flex items-center justify-center" style={{ background: 'var(--gradient-1-2)' }}>
            <span className="text-4xl font-bold" style={{ color: 'var(--on-gradient-1-2)' }}>404</span>
          </div>
          <h1 className="text-3xl font-bold text-primary mb-4">Page Not Found</h1>
          <p className="text-secondary mb-8">
            The ETL management page you're looking for doesn't exist or has been moved.
          </p>
        </div>

        <div className="space-y-4">
          <button
            onClick={() => navigate('/home')}
            className="btn-crud-edit w-full py-3"
          >
            Go to ETL Home
          </button>
          <button
            onClick={() => navigate(-1)}
            className="btn-neutral-secondary w-full py-3"
          >
            Go Back
          </button>
        </div>
      </motion.div>
    </div>
  )
}
