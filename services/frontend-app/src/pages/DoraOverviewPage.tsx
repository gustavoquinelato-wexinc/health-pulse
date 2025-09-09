import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import CollapsedSidebar from '../components/CollapsedSidebar'
import DoraFilterToolbar from '../components/DoraFilterToolbar'
import DoraTrendChart from '../components/DoraTrendChart'
import ForecastingControls from '../components/ForecastingControls'
import Header from '../components/Header'
import useDocumentTitle from '../hooks/useDocumentTitle'

export default function DoraOverviewPage() {
  // Set document title
  useDocumentTitle('DORA Metrics')

  // State for selected metric in trend chart
  const [selectedMetric, setSelectedMetric] = useState('lead-time')

  // State for filters
  const [filters, setFilters] = useState({
    team: '',
    project_key: '',
    wit_to: '',
    status_to: '',
    aha_initiative: '',
    aha_project_code: '',
    aha_milestone: ''
  })

  // State for current lead time value
  const [currentLeadTime, setCurrentLeadTime] = useState('0')

  // Function to calculate current lead time from chart data
  const calculateCurrentLeadTime = async () => {
    try {
      const token = localStorage.getItem('pulse_token') || document.cookie
        .split('; ')
        .find(row => row.startsWith('pulse_token='))
        ?.split('=')[1]

      if (!token) return

      // Build query parameters from filters
      const queryParams = new URLSearchParams()
      Object.entries(filters).forEach(([key, value]) => {
        if (value && value.trim()) {
          queryParams.append(key, value.trim())
        }
      })

      const queryString = queryParams.toString()
      const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001'
      const url = `${apiBase}/api/v1/metrics/dora/lead-time-trend${queryString ? `?${queryString}` : ''}`



      const response = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })



      if (response.ok) {
        const data = await response.json()
        // The data is in trend_data array, not directly in data
        const trendData = data.trend_data || []

        if (trendData.length > 0) {
          // Get the most recent data point
          const recentData = trendData
            .filter((point: any) => !point.is_forecast && point.value !== null && point.value !== undefined)
            .sort((a: any, b: any) => new Date(b.week).getTime() - new Date(a.week).getTime())

          if (recentData.length > 0) {
            const latestValue = recentData[0].value
            const formattedValue = `${latestValue.toFixed(1)}d`
            setCurrentLeadTime(formattedValue)
          }
        }
      }
    } catch (error) {
      console.error('Error fetching lead time data:', error)
    }
  }

  // Update lead time when filters change
  useEffect(() => {
    calculateCurrentLeadTime()
  }, [filters])

  // State for forecasting
  const [forecastConfig, setForecastConfig] = useState({
    model: 'Linear Regression' as 'Linear Regression' | 'Exponential Smoothing' | 'Prophet',
    duration: '3M' as '3M' | '6M',
    enabled: false
  })
  const [forecastLoading, setForecastLoading] = useState(false)



  // DORA Metrics data with gradient backgrounds matching settings page
  const doraMetrics = [
    // Velocity Metrics (Left Side)
    {
      title: 'Lead Time for Changes',
      value: currentLeadTime, // Dynamic value from API
      description: 'Time from code commit to production',
      gradient: 'linear-gradient(135deg, var(--color-1) 0%, var(--color-2) 100%)',
      onColor: 'var(--on-gradient-1-2)',
      borderColor: 'var(--color-1)',
      category: 'velocity'
    },
    {
      title: 'Deployment Frequency',
      value: 'SOON',
      description: 'How often deployments occur',
      gradient: 'linear-gradient(135deg, var(--color-2) 0%, var(--color-3) 100%)',
      onColor: 'var(--on-gradient-2-3)',
      borderColor: 'var(--color-2)',
      category: 'velocity'
    },
    // Stability Metrics (Right Side)
    {
      title: 'Change Failure Rate',
      value: 'SOON',
      description: 'Percentage of deployments causing failures',
      gradient: 'linear-gradient(135deg, var(--color-3) 0%, var(--color-4) 100%)',
      onColor: 'var(--on-gradient-3-4)',
      borderColor: 'var(--color-3)',
      category: 'stability'
    },
    {
      title: 'Time to Restore',
      value: 'SOON',
      description: 'Time to recover from failures',
      gradient: 'linear-gradient(135deg, var(--color-4) 0%, var(--color-5) 100%)',
      onColor: 'var(--on-gradient-4-5)',
      borderColor: 'var(--color-4)',
      category: 'stability'
    }
  ]

  return (
    <div className="min-h-screen bg-primary">
      <Header />

      <div className="flex">
        <CollapsedSidebar />

        <main className="flex-1 p-6 ml-16">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="space-y-6"
          >
            <div className="space-y-2">
              <h1 className="text-3xl font-bold text-primary">
                DORA Metrics Overview
              </h1>
              <p className="text-secondary">
                DevOps Research and Assessment metrics dashboard
              </p>
            </div>

            {/* DORA Metrics Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              {doraMetrics.map((metric, index) => (
                <motion.div
                  key={metric.title}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.1 }}
                  className="rounded-xl p-6 space-y-4 backdrop-blur-sm hover:shadow-md transition-all duration-300"
                  style={{
                    background: metric.gradient,
                    color: metric.onColor
                  }}
                >
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-medium opacity-90">{metric.title}</h3>
                    <div className="w-3 h-3 bg-white bg-opacity-30 rounded-full"></div>
                  </div>

                  <div className="space-y-2">
                    <div className="text-2xl font-bold">{metric.value}</div>
                    <div className="text-xs opacity-80">{metric.description}</div>
                  </div>
                </motion.div>
              ))}
            </div>

            {/* Filters and Forecasting Section - Match DORA metrics grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
              {/* Filters - Same size as first 3 DORA cards (3/4 width) */}
              <div className="lg:col-span-3">
                <DoraFilterToolbar
                  selectedMetric={selectedMetric}
                  onMetricChange={setSelectedMetric}
                  filters={filters}
                  onFiltersChange={setFilters}
                  disabled={false}
                />
              </div>

              {/* Forecasting Controls - Same size as last DORA card (1/4 width) */}
              {selectedMetric === 'lead-time' && (
                <div className="lg:col-span-1">
                  <ForecastingControls
                    model={forecastConfig.model}
                    duration={forecastConfig.duration}
                    enabled={forecastConfig.enabled}
                    loading={forecastLoading}
                    onModelChange={(model) => setForecastConfig(prev => ({ ...prev, model }))}
                    onDurationChange={(duration) => setForecastConfig(prev => ({ ...prev, duration }))}
                    onApplyForecast={() => {
                      setForecastLoading(true)
                      setForecastConfig(prev => ({ ...prev, enabled: true }))
                    }}
                    onClearForecast={() => {
                      setForecastConfig(prev => ({ ...prev, enabled: false }))
                    }}
                  />
                </div>
              )}
            </div>

            {/* Trend Chart Section */}
            <DoraTrendChart
              selectedMetric={selectedMetric}
              filters={filters}
              forecastConfig={forecastConfig}
              onForecastConfigChange={setForecastConfig}
              forecastLoading={forecastLoading}
              onForecastLoadingChange={setForecastLoading}
            />
          </motion.div>
        </main>
      </div>
    </div >
  )
}
