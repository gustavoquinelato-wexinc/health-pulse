import { motion } from 'framer-motion'
import { useEffect, useMemo, useState } from 'react'
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts'
import { useTheme } from '../contexts/ThemeContext'

interface TrendDataPoint {
  week?: string
  week_label?: string
  month?: string  // Keep for backward compatibility
  value: number
  avg_value?: number
  issue_count?: number
  // Forecasting fields
  historical_mean?: number
  forecast_mean?: number
  forecast_confidence_range?: [number, number] // [lower, upper]
  is_forecast?: boolean
  // Trend line fields
  trend_value?: number
  is_trend?: boolean
}





interface ForecastResponse {
  forecast_data: TrendDataPoint[]
  model_info: {
    model_used: string
    confidence_level: number
    r_squared?: number
    mae?: number // Mean Absolute Error
  }
}

interface DoraTrendChartProps {
  selectedMetric: string
  data?: TrendDataPoint[]
  filters?: {
    team?: string
    project_key?: string
    wit_to?: string
    status_to?: string
    aha_initiative?: string
    aha_project_code?: string
    aha_milestone?: string
  }
  forecastConfig?: {
    model: 'Linear Regression' | 'Exponential Smoothing' | 'Prophet'
    duration: '3M' | '6M'
    enabled: boolean
  }
  onForecastConfigChange?: (config: {
    model: 'Linear Regression' | 'Exponential Smoothing' | 'Prophet'
    duration: '3M' | '6M'
    enabled: boolean
  }) => void
  forecastLoading?: boolean
  onForecastLoadingChange?: (loading: boolean) => void
}

type TimePeriod = '1M' | '3M' | '6M' | '1Y' | '2Y' | '5Y' | 'CUSTOM' // These represent week periods: 4W, 12W, 24W, 52W, 104W, 260W

interface PeriodOption {
  value: TimePeriod
  label: string
  weeks: number | null // null for MAX and CUSTOM
}

const periodOptions: PeriodOption[] = [
  { value: '1M', label: '4W', weeks: 4 },    // 1 month = 4 weeks
  { value: '3M', label: '12W', weeks: 12 },  // 3 months = 12 weeks
  { value: '6M', label: '24W', weeks: 24 },  // 6 months = 24 weeks
  { value: '1Y', label: '52W', weeks: 52 },  // 1 year = 52 weeks
  { value: '2Y', label: '104W', weeks: 104 }, // 2 years = 104 weeks
  { value: '5Y', label: '260W', weeks: 260 }, // 5 years = 260 weeks
  { value: 'CUSTOM', label: 'CUSTOM', weeks: null }
]

// Mock data for different metrics
const mockTrendData: Record<string, TrendDataPoint[]> = {
  'lead-time': [
    { month: 'Jan', value: 2.3 },
    { month: 'Feb', value: 2.1 },
    { month: 'Mar', value: 1.8 },
    { month: 'Apr', value: 2.0 },
    { month: 'May', value: 1.6 },
    { month: 'Jun', value: 1.4 },
    { month: 'Jul', value: 1.7 },
    { month: 'Aug', value: 1.5 },
    { month: 'Sep', value: 1.3 },
    { month: 'Oct', value: 1.2 },
    { month: 'Nov', value: 1.1 },
    { month: 'Dec', value: 1.0 }
  ],
  'deployment-frequency': [
    { month: 'Jan', value: 3.2 },
    { month: 'Feb', value: 3.8 },
    { month: 'Mar', value: 4.1 },
    { month: 'Apr', value: 3.9 },
    { month: 'May', value: 4.5 },
    { month: 'Jun', value: 4.8 },
    { month: 'Jul', value: 4.3 },
    { month: 'Aug', value: 5.1 },
    { month: 'Sep', value: 5.4 },
    { month: 'Oct', value: 5.2 },
    { month: 'Nov', value: 5.8 },
    { month: 'Dec', value: 6.0 }
  ],
  'change-failure-rate': [
    { month: 'Jan', value: 8.5 },
    { month: 'Feb', value: 7.2 },
    { month: 'Mar', value: 6.8 },
    { month: 'Apr', value: 7.1 },
    { month: 'May', value: 5.9 },
    { month: 'Jun', value: 5.2 },
    { month: 'Jul', value: 4.8 },
    { month: 'Aug', value: 4.3 },
    { month: 'Sep', value: 3.9 },
    { month: 'Oct', value: 3.5 },
    { month: 'Nov', value: 3.1 },
    { month: 'Dec', value: 2.8 }
  ],
  'time-to-restore': [
    { month: 'Jan', value: 120 },
    { month: 'Feb', value: 105 },
    { month: 'Mar', value: 95 },
    { month: 'Apr', value: 88 },
    { month: 'May', value: 82 },
    { month: 'Jun', value: 75 },
    { month: 'Jul', value: 68 },
    { month: 'Aug', value: 62 },
    { month: 'Sep', value: 58 },
    { month: 'Oct', value: 52 },
    { month: 'Nov', value: 48 },
    { month: 'Dec', value: 45 }
  ]
}

const metricConfig = {
  'lead-time': {
    title: 'Lead Time for Changes',
    unit: 'days',
    gradient: 'linear-gradient(135deg, var(--color-1) 0%, var(--color-2) 100%)',
    color1: 'var(--color-1)',
    color2: 'var(--color-2)',
    onColor: 'var(--on-gradient-1-2)'
  },
  'deployment-frequency': {
    title: 'Deployment Frequency',
    unit: 'per day',
    gradient: 'linear-gradient(135deg, var(--color-2) 0%, var(--color-3) 100%)',
    color1: 'var(--color-2)',
    color2: 'var(--color-3)',
    onColor: 'var(--on-gradient-2-3)'
  },
  'change-failure-rate': {
    title: 'Change Failure Rate',
    unit: '%',
    gradient: 'linear-gradient(135deg, var(--color-3) 0%, var(--color-4) 100%)',
    color1: 'var(--color-3)',
    color2: 'var(--color-4)',
    onColor: 'var(--on-gradient-3-4)'
  },
  'time-to-restore': {
    title: 'Time to Restore',
    unit: 'minutes',
    gradient: 'linear-gradient(135deg, var(--color-4) 0%, var(--color-5) 100%)',
    color1: 'var(--color-4)',
    color2: 'var(--color-5)',
    onColor: 'var(--on-gradient-4-5)'
  }
}

export default function DoraTrendChart({
  selectedMetric,
  data,
  filters = {},
  forecastConfig,
  onForecastConfigChange: _onForecastConfigChange,
  forecastLoading: _forecastLoading,
  onForecastLoadingChange: _onForecastLoadingChange
}: DoraTrendChartProps) {
  const { theme } = useTheme()
  const [selectedPeriod, setSelectedPeriod] = useState<TimePeriod>('6M')
  const [customStartDate, setCustomStartDate] = useState('')
  const [customEndDate, setCustomEndDate] = useState('')
  const [removeEmptyWeeks, setRemoveEmptyWeeks] = useState(false) // Default OFF (show empty weeks)
  const [showCustomRange, setShowCustomRange] = useState(false)
  const [historicalData, setHistoricalData] = useState<TrendDataPoint[]>([])
  const [forecastData, setForecastData] = useState<TrendDataPoint[]>([])
  const [loading, setLoading] = useState(true) // Start with loading true to prevent mock data flash
  const [error, setError] = useState<string | null>(null)


  // Helper function to calculate trend line using linear regression
  const calculateTrendLine = (data: TrendDataPoint[]): TrendDataPoint[] => {
    // Get only valid data points (exclude empty weeks and forecasts)
    const validData = data.filter(point =>
      point.value !== undefined &&
      point.value !== null &&
      !isNaN(point.value) &&
      !point.is_forecast
    )

    if (validData.length < 2) return data.map(point => ({ ...point, trend_value: undefined }))

    // Create mapping of original indices to valid data indices
    const validIndices: number[] = []
    data.forEach((point, index) => {
      if (point.value !== undefined &&
        point.value !== null &&
        !isNaN(point.value) &&
        !point.is_forecast) {
        validIndices.push(index)
      }
    })

    // Simple linear regression using actual data positions
    const n = validData.length
    const sumX = validIndices.reduce((sum, index) => sum + index, 0)
    const sumY = validData.reduce((sum, point) => sum + point.value, 0)
    const sumXY = validData.reduce((sum, point, i) => sum + (validIndices[i] * point.value), 0)
    const sumXX = validIndices.reduce((sum, index) => sum + (index * index), 0)

    const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX)
    const intercept = (sumY - slope * sumX) / n

    // Generate trend line points for all data points
    return data.map((point, index) => ({
      ...point,
      trend_value: intercept + slope * index,
      is_trend: true
    }))
  }

  // Combined data for chart rendering
  const chartData = useMemo(() => {
    // Transform historical data to include historical_mean
    const transformedHistorical = historicalData.map(point => ({
      ...point,
      historical_mean: point.value,
      forecast_mean: undefined,
      forecast_confidence_range: undefined,
      is_forecast: false
    }))

    // Transform forecast data to ensure proper structure and clamp negative values to 0
    const transformedForecast = forecastData.map(point => ({
      ...point,
      value: Math.max(0, point.forecast_mean || 0), // Clamp negative values to 0
      forecast_mean: Math.max(0, point.forecast_mean || 0), // Also clamp forecast_mean
      forecast_confidence_range: point.forecast_confidence_range
        ? [Math.max(0, point.forecast_confidence_range[0]), Math.max(0, point.forecast_confidence_range[1])] as [number, number]
        : undefined, // Clamp confidence range to 0 minimum
      historical_mean: undefined,
      is_forecast: true
    }))

    // Add a bridge point for seamless connection if we have both historical and forecast data
    let bridgePoint: TrendDataPoint[] = []
    if (transformedHistorical.length > 0 && transformedForecast.length > 0) {
      const lastHistorical = transformedHistorical[transformedHistorical.length - 1]

      // Create a bridge point that has both historical and forecast values
      // This ensures the lines and areas connect perfectly
      bridgePoint = [{
        ...lastHistorical,
        historical_mean: lastHistorical.value, // Keep historical area going
        forecast_mean: lastHistorical.value, // Make forecast line start from last historical value
        value: lastHistorical.value, // Ensure consistency
        is_forecast: false // Keep as historical for area continuity
      }]
    }

    // Combine: historical + bridge + forecast
    return [...transformedHistorical, ...bridgePoint, ...transformedForecast]
  }, [historicalData, forecastData])



  // Fetch real data for lead-time metric
  const fetchLeadTimeData = async () => {
    if (selectedMetric !== 'lead-time') return

    setLoading(true)
    setError(null)

    try {
      const token = localStorage.getItem('pulse_token') || document.cookie
        .split('; ')
        .find(row => row.startsWith('pulse_token='))
        ?.split('=')[1]

      if (!token) {
        throw new Error('No authentication token found')
      }

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

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const result = await response.json()
      setHistoricalData(result.trend_data || [])
      setError(null) // Clear any previous errors on successful fetch

      // If forecast is enabled, re-fetch forecast with new historical data
      if (forecastConfig?.enabled) {
        await fetchForecastData(result.trend_data || [])
      }
    } catch (err) {
      console.error('Error fetching lead time trend data:', err)
      setError(err instanceof Error ? err.message : 'Failed to fetch data')
      // Fall back to empty data on error
      setHistoricalData([])
      setForecastData([])
    } finally {
      setLoading(false)
    }
  }

  // Fetch forecast data
  const fetchForecastData = async (baseHistoricalData?: TrendDataPoint[]) => {
    if (!forecastConfig) return

    const dataToUse = baseHistoricalData || historicalData
    if (dataToUse.length === 0) return

    _onForecastLoadingChange?.(true)
    try {
      const token = localStorage.getItem('pulse_token') || document.cookie
        .split('; ')
        .find(row => row.startsWith('pulse_token='))
        ?.split('=')[1]

      if (!token) {
        throw new Error('No authentication token found')
      }

      const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001'
      const url = `${apiBase}/api/v1/metrics/dora/forecast`

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          metric: 'lead-time-trend',
          model: forecastConfig.model,
          duration: forecastConfig.duration,
          historical_data: dataToUse,
          filters: filters
        })
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const result: ForecastResponse = await response.json()
      setForecastData(result.forecast_data || [])

    } catch (err) {
      console.error('Error fetching forecast data:', err)
      setError(err instanceof Error ? err.message : 'Failed to fetch forecast')
      setForecastData([])
    } finally {
      _onForecastLoadingChange?.(false)
    }
  }



  // Fetch data when component mounts, metric changes, or filters change
  useEffect(() => {
    fetchLeadTimeData()
  }, [selectedMetric, filters])

  // Handle forecast configuration changes
  useEffect(() => {
    if (forecastConfig?.enabled && historicalData.length > 0) {
      fetchForecastData()
    } else if (!forecastConfig?.enabled) {
      setForecastData([])
    }
  }, [forecastConfig?.enabled, forecastConfig?.model, forecastConfig?.duration])

  // Force chart re-render when theme changes to update colors immediately
  useEffect(() => {
    // This effect ensures the chart updates its colors when theme changes
    // The key prop on ComposedChart will force a complete re-render
  }, [theme])

  // Determine which data to use - avoid mock data flash
  const allData = (() => {
    if (data) return data  // Prop data takes precedence
    if (selectedMetric === 'lead-time') {
      // For lead-time, use combined historical + forecast data or empty array while loading
      return chartData.length > 0 ? chartData : []
    }
    // For other metrics, use mock data
    return mockTrendData[selectedMetric] || mockTrendData['lead-time']
  })()

  const config = metricConfig[selectedMetric as keyof typeof metricConfig] || metricConfig['lead-time']

  // Helper function to find oldest data date
  const getOldestDataDate = (data: TrendDataPoint[]): Date | null => {
    const validDates = data
      .map(point => {
        if (!point.week) return null
        try {
          const dateStr = point.week.replace('Z', '').replace('T', ' ')
          const date = new Date(dateStr)
          return !isNaN(date.getTime()) ? date : null
        } catch {
          return null
        }
      })
      .filter((date): date is Date => date !== null)
      .sort((a, b) => a.getTime() - b.getTime())

    return validDates.length > 0 ? validDates[0] : null
  }

  // Filter data based on selected period
  const getFilteredData = (data: TrendDataPoint[], period: TimePeriod): TrendDataPoint[] => {

    if (period === 'CUSTOM') {
      if (!customStartDate || !customEndDate) return data

      const startDate = new Date(customStartDate)
      const endDate = new Date(customEndDate)
      const today = new Date()

      // Align start date to Monday (same logic as other periods)
      const startMonday = new Date(startDate)
      const startDayOfWeek = startDate.getDay()
      const daysToMonday = startDayOfWeek === 0 ? -6 : 1 - startDayOfWeek // Handle Sunday (0) as -6
      startMonday.setDate(startDate.getDate() + daysToMonday)

      // Smart start for CUSTOM: use oldest data date from actual data if it's newer than selected start
      const oldestDataDate = getOldestDataDate(data.filter(point => !point.is_forecast))
      const effectiveStartMonday = oldestDataDate && oldestDataDate > startMonday
        ? (() => {
          const smartStart = new Date(oldestDataDate)
          const smartDayOfWeek = smartStart.getDay()
          const daysToSmartMonday = smartDayOfWeek === 0 ? -6 : 1 - smartDayOfWeek
          smartStart.setDate(smartStart.getDate() + daysToSmartMonday)
          return smartStart
        })()
        : startMonday

      // If end date includes today or future, align to current Monday (like other periods)
      // Otherwise, align to the Monday of the selected end date's week
      let endMonday: Date
      if (endDate >= today) {
        // Use current Monday (same as other periods)
        endMonday = new Date(today)
        const todayDayOfWeek = today.getDay()
        const daysToCurrentMonday = todayDayOfWeek === 0 ? -6 : 1 - todayDayOfWeek
        endMonday.setDate(today.getDate() + daysToCurrentMonday)
      } else {
        // Use Monday of the selected end date's week
        endMonday = new Date(endDate)
        const endDayOfWeek = endDate.getDay()
        const daysToEndMonday = endDayOfWeek === 0 ? -6 : 1 - endDayOfWeek
        endMonday.setDate(endDate.getDate() + daysToEndMonday)
      }

      // Generate complete timeline for custom date range
      const completeTimeline: TrendDataPoint[] = []

      // Calculate number of weeks in the custom range (Monday to Monday weeks)
      const timeDiff = endMonday.getTime() - effectiveStartMonday.getTime()
      const totalWeeks = Math.floor(timeDiff / (7 * 24 * 60 * 60 * 1000)) + 1 // +1 to include both start and end weeks



      // Generate week-by-week timeline starting from effective Monday
      for (let weekIndex = 0; weekIndex < totalWeeks; weekIndex++) {
        const currentWeekDate = new Date(effectiveStartMonday)
        currentWeekDate.setDate(effectiveStartMonday.getDate() + (weekIndex * 7))

        // Don't break early - we want to include all weeks up to endMonday
        // Skip if we've gone past the aligned end date (Monday)
        if (currentWeekDate > endMonday) break



        // Create week label (always include year)
        const weekLabel = currentWeekDate.toLocaleDateString('en-US', {
          month: 'short',
          day: 'numeric',
          year: 'numeric'
        })

        // Find actual data for this week
        const actualDataForWeek = data.find(point => {
          if (!point.week) return false
          try {
            const pointDate = new Date(point.week.replace('Z', '').replace('T', ' '))
            if (isNaN(pointDate.getTime())) return false

            // Check if the data point falls within this week (Monday to Sunday)
            const weekStart = new Date(currentWeekDate)
            weekStart.setHours(0, 0, 0, 0) // Start of Monday
            const weekEnd = new Date(currentWeekDate)
            weekEnd.setDate(weekEnd.getDate() + 6) // Sunday of the same week
            weekEnd.setHours(23, 59, 59, 999) // End of Sunday

            return pointDate >= weekStart && pointDate <= weekEnd
          } catch {
            return false
          }
        })

        // Create data point (with actual data if available, undefined if not)
        if (actualDataForWeek) {
          completeTimeline.push({
            ...actualDataForWeek,
            week_label: weekLabel
          })
        } else {
          completeTimeline.push({
            week: currentWeekDate.toISOString(),
            week_label: weekLabel,
            value: undefined as any,
            historical_mean: undefined as any,
            forecast_mean: undefined,
            forecast_confidence_range: undefined,
            is_forecast: false
          })
        }
      }

      // Apply empty weeks filtering for CUSTOM period
      if (removeEmptyWeeks) {
        return completeTimeline.filter(point =>
          point.value !== undefined && point.value !== null
        )
      }

      return completeTimeline
    }

    const periodConfig = periodOptions.find(p => p.value === period)
    if (!periodConfig?.weeks) return data

    // Separate historical and forecast data
    const historicalData = data.filter(point => !point.is_forecast)
    const forecastData = data.filter(point => point.is_forecast)

    // Use Monday of current week as the end point for consistency
    const today = new Date()
    const currentMonday = new Date(today)
    // Get Monday of current week (0 = Sunday, 1 = Monday, etc.)
    const dayOfWeek = today.getDay()
    const daysToMonday = dayOfWeek === 0 ? -6 : 1 - dayOfWeek // Handle Sunday (0) as -6
    currentMonday.setDate(today.getDate() + daysToMonday)

    // Calculate the theoretical period start date (full period from current week)
    const theoreticalStartMonday = new Date(currentMonday)
    theoreticalStartMonday.setDate(currentMonday.getDate() - (periodConfig.weeks * 7))

    // STEP 1: Filter dataset to only include data within the theoretical period range
    const periodFilteredData = historicalData.filter(point => {
      if (!point.week) return false
      try {
        const pointDate = new Date(point.week)
        return pointDate >= theoreticalStartMonday && pointDate <= currentMonday
      } catch {
        return false
      }
    })

    // STEP 2: Find oldest week in the filtered dataset
    const oldestDataInPeriod = getOldestDataDate(periodFilteredData)

    // STEP 3: Smart start - use oldest data date if it's newer than theoretical start
    // This removes empty initial weeks while maintaining period integrity
    const effectiveStartMonday = oldestDataInPeriod && oldestDataInPeriod > theoreticalStartMonday
      ? (() => {
        const smartStart = new Date(oldestDataInPeriod)
        const smartDayOfWeek = smartStart.getDay()
        const daysToSmartMonday = smartDayOfWeek === 0 ? -6 : 1 - smartDayOfWeek
        smartStart.setDate(smartStart.getDate() + daysToSmartMonday)
        return smartStart
      })()
      : theoreticalStartMonday

    const completeTimeline: TrendDataPoint[] = []

    // STEP 4: Calculate effective weeks to generate from smart start to current week
    const timeDiff = currentMonday.getTime() - effectiveStartMonday.getTime()
    const actualWeeksAvailable = Math.ceil(timeDiff / (7 * 24 * 60 * 60 * 1000)) + 1

    // Generate weeks from smart start to current week (no empty initial weeks)
    let weeksToGenerate = actualWeeksAvailable

    // For 52W, generate 53 weeks so current week appears at an even index for X-axis display
    if (periodConfig.weeks === 52) {
      weeksToGenerate = Math.min(actualWeeksAvailable + 1, 53) // Add one week if possible, max 53
    }





    // Generate weeks in chronological order (oldest first, newest last)
    // From smart start to current week (no empty initial weeks)
    const actualWeeksToGenerate = Math.max(weeksToGenerate, 1)

    for (let weekIndex = 0; weekIndex < actualWeeksToGenerate; weekIndex++) {
      const currentWeekDate = new Date(effectiveStartMonday)
      currentWeekDate.setDate(effectiveStartMonday.getDate() + (weekIndex * 7))

      // Don't go beyond current Monday
      if (currentWeekDate > currentMonday) {
        break
      }



      // STEP 3: Create week label with year (always include year)
      const weekLabel = currentWeekDate.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric'
      })





      // STEP 4: Find actual data for this week
      const actualDataForWeek = historicalData.find(point => {
        if (!point.week) return false
        try {
          // Handle both formats: '2024-09-02T00:00:00' and '2024-09-02T00:00:00.000Z'
          const pointDate = new Date(point.week)
          if (isNaN(pointDate.getTime())) return false

          // Check if the data point falls within this week (Monday to Sunday)
          const weekStart = new Date(currentWeekDate)
          weekStart.setHours(0, 0, 0, 0) // Start of Monday
          const weekEnd = new Date(currentWeekDate)
          weekEnd.setDate(weekEnd.getDate() + 6) // Sunday of the same week
          weekEnd.setHours(23, 59, 59, 999) // End of Sunday

          const isMatch = pointDate >= weekStart && pointDate <= weekEnd



          return isMatch
        } catch {
          return false
        }
      })

      // STEP 5: Create data point (with actual data if available, undefined if not)
      if (actualDataForWeek) {
        // Use the actual data point but update the week_label to match our timeline
        completeTimeline.push({
          ...actualDataForWeek,
          week_label: weekLabel // Use our consistent week label format
        })
      } else {
        // Create placeholder for missing week
        completeTimeline.push({
          week: currentWeekDate.toISOString(),
          week_label: weekLabel,
          value: undefined as any, // undefined creates gaps in the line
          historical_mean: undefined as any,
          forecast_mean: undefined,
          forecast_confidence_range: undefined,
          is_forecast: false
        })
      }
    }



    // Add bridge point for seamless connection between historical and forecast
    let result = [...completeTimeline]
    if (forecastData.length > 0 && completeTimeline.length > 0) {
      // Find the last historical data point with actual data
      const lastHistoricalWithData = completeTimeline
        .slice()
        .reverse()
        .find(point => point.value !== undefined && !point.is_forecast)

      if (lastHistoricalWithData) {
        // Create bridge point for seamless connection
        const bridgePoint = {
          ...lastHistoricalWithData,
          historical_mean: lastHistoricalWithData.value,
          forecast_mean: lastHistoricalWithData.value,
          is_forecast: false // Keep as historical for area continuity
        }
        result.push(bridgePoint)
      }
    }

    // STEP 3: Apply empty weeks filtering if enabled
    let finalResult = [...result, ...forecastData]

    if (removeEmptyWeeks) {
      // Filter out weeks with no actual data (keep only weeks with real values)
      finalResult = finalResult.filter(point =>
        point.is_forecast || // Always keep forecast data
        (point.value !== undefined && point.value !== null) // Keep weeks with actual data
      )
    }

    return finalResult
  }

  const filteredChartData = (() => {
    const filtered = getFilteredData(allData, selectedPeriod)

    // Calculate trend line for the filtered data
    const trendData = calculateTrendLine(filtered)

    // Merge trend values back into the filtered data
    return filtered.map((point, index) => ({
      ...point,
      trend_value: trendData[index]?.trend_value
    }))
  })()

  // Show loading state if no data and still loading
  if (selectedMetric === 'lead-time' && filteredChartData.length === 0 && loading) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full"
      >
        <div
        className="card p-6 space-y-4 transition-all duration-200"
        onMouseEnter={(e) => {
          e.currentTarget.style.borderColor = 'var(--color-1)'
          e.currentTarget.style.boxShadow = theme === 'dark'
            ? '0 2px 2px 0 rgba(255, 255, 255, 0.08)'
            : '0 2px 2px 0 rgba(0, 0, 0, 0.12)'
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.borderColor = theme === 'dark' ? '#4a5568' : '#9ca3af'
          e.currentTarget.style.boxShadow = theme === 'dark'
            ? '0 2px 2px 0 rgba(255, 255, 255, 0.05)'
            : '0 2px 2px 0 rgba(0, 0, 0, 0.1)'
        }}
      >
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-primary">Lead Time for Changes Trend</h3>
            <div className="text-sm text-secondary">Loading...</div>
          </div>
          <div className="h-64 flex items-center justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        </div>
      </motion.div>
    )
  }

  // Calculate statistics for reference lines
  const validValues = filteredChartData
    .map(d => d.value)
    .filter(value => value !== null && value !== undefined && !isNaN(value))
    .sort((a, b) => a - b)

  const medianValue = validValues.length > 0 ?
    validValues[Math.floor(validValues.length / 2)] : 0

  const meanValue = validValues.length > 0 ?
    validValues.reduce((sum, value) => sum + value, 0) / validValues.length : 0



  // Calculate on-color from background color (same logic as ThemeContext)
  const calculateOnColor = (hex: string): string => {
    try {
      const h = hex.replace('#', '')
      const r = parseInt(h.slice(0, 2), 16) / 255
      const g = parseInt(h.slice(2, 4), 16) / 255
      const b = parseInt(h.slice(4, 6), 16) / 255
      const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4))
      const L = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
      const contrast = (Lbg: number, Lfg: number) => (Math.max(Lbg, Lfg) + 0.05) / (Math.min(Lbg, Lfg) + 0.05)
      const cBlack = contrast(L, 0)
      const cWhite = contrast(L, 1)
      return cWhite >= cBlack ? '#FFFFFF' : '#000000'
    } catch {
      return '#000000'
    }
  }

  // Get computed styles to access CSS custom properties
  const getComputedColor = (colorVar: string, fallback: string) => {
    if (typeof window !== 'undefined') {
      const computedStyle = getComputedStyle(document.documentElement)
      const value = computedStyle.getPropertyValue(colorVar).trim()
      return value || fallback
    }
    return fallback
  }

  // Get chart-safe color that adapts to theme
  const getChartSafeColor = (colorVar: string, fallback: string) => {
    const originalColor = getComputedColor(colorVar, fallback)
    const isDarkMode = document.documentElement.getAttribute('data-theme') === 'dark'

    // Calculate luminance to determine if color is too dark/light for current theme
    const getLuminance = (hex: string) => {
      try {
        const h = hex.replace('#', '')
        const r = parseInt(h.slice(0, 2), 16) / 255
        const g = parseInt(h.slice(2, 4), 16) / 255
        const b = parseInt(h.slice(4, 6), 16) / 255
        const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4))
        return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
      } catch {
        return 0.5 // neutral fallback
      }
    }

    const luminance = getLuminance(originalColor)

    // If color is too dark for dark mode or too light for light mode, adjust it
    if (isDarkMode && luminance < 0.3) {
      // In dark mode, if color is too dark, lighten it
      return lightenColor(originalColor, 0.4)
    } else if (!isDarkMode && luminance > 0.7) {
      // In light mode, if color is too light, darken it
      return darkenColor(originalColor, 0.3)
    }

    return originalColor
  }

  // Helper function to lighten a color
  const lightenColor = (hex: string, amount: number) => {
    try {
      const h = hex.replace('#', '')
      const r = Math.min(255, parseInt(h.slice(0, 2), 16) + Math.round(255 * amount))
      const g = Math.min(255, parseInt(h.slice(2, 4), 16) + Math.round(255 * amount))
      const b = Math.min(255, parseInt(h.slice(4, 6), 16) + Math.round(255 * amount))
      return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`
    } catch {
      return hex
    }
  }

  // Helper function to darken a color
  const darkenColor = (hex: string, amount: number) => {
    try {
      const h = hex.replace('#', '')
      const r = Math.max(0, parseInt(h.slice(0, 2), 16) - Math.round(255 * amount))
      const g = Math.max(0, parseInt(h.slice(2, 4), 16) - Math.round(255 * amount))
      const b = Math.max(0, parseInt(h.slice(4, 6), 16) - Math.round(255 * amount))
      return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`
    } catch {
      return hex
    }
  }



  // Format data for Recharts
  const formattedData = filteredChartData.map((point, index) => {
    const displayLabel = point.week_label || `Week ${index + 1}`

    return {
      ...point,
      index,
      displayLabel,
      year: (() => {
        const dateStr = point.week || point.week_label
        if (dateStr) {
          try {
            const date = new Date(dateStr)
            return !isNaN(date.getTime()) ? date.getFullYear().toString() : '2024'
          } catch {
            return '2024'
          }
        }
        return '2024'
      })()
    }
  });



  // Hide chart for deployment frequency (SOON will be shown in the metric card)
  if (selectedMetric === 'deployment-frequency') {
    return null
  }

  // Show empty state if no data and not loading
  if (selectedMetric === 'lead-time' && filteredChartData.length === 0 && !loading) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full"
      >
        <div
          className="card p-6 space-y-4 transition-all duration-200"
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = 'var(--color-1)'
            e.currentTarget.style.boxShadow = theme === 'dark'
              ? '0 2px 2px 0 rgba(255, 255, 255, 0.08)'
              : '0 2px 2px 0 rgba(0, 0, 0, 0.12)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = theme === 'dark' ? '#4a5568' : '#9ca3af'
            e.currentTarget.style.boxShadow = theme === 'dark'
              ? '0 2px 2px 0 rgba(255, 255, 255, 0.05)'
              : '0 2px 2px 0 rgba(0, 0, 0, 0.1)'
          }}
        >
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-primary">Lead Time for Changes Trend</h3>
            {error && (
              <div className="text-sm text-red-500">Error loading data</div>
            )}
          </div>
          <div className="h-64 flex items-center justify-center">
            <div className="text-center text-secondary">
              <p className="text-lg mb-2">No DORA data available</p>
              <p className="text-sm">Complete some stories with merged PRs to see lead time trends</p>
            </div>
          </div>
        </div>
      </motion.div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="w-full"
    >


      <div
        className="card p-6 space-y-4 transition-all duration-200"
        onMouseEnter={(e) => {
          e.currentTarget.style.borderColor = 'var(--color-1)'
          e.currentTarget.style.boxShadow = theme === 'dark'
            ? '0 2px 2px 0 rgba(255, 255, 255, 0.08)'
            : '0 2px 2px 0 rgba(0, 0, 0, 0.12)'
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.borderColor = theme === 'dark' ? '#4a5568' : '#9ca3af'
          e.currentTarget.style.boxShadow = theme === 'dark'
            ? '0 2px 2px 0 rgba(255, 255, 255, 0.05)'
            : '0 2px 2px 0 rgba(0, 0, 0, 0.1)'
        }}
      >
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-primary">
            {config.title} Trend
            {selectedMetric === 'lead-time' && historicalData.length > 0 && (
              <span className="text-sm text-secondary ml-2">(Weekly Data)</span>
            )}
          </h3>
          <div className="flex items-center space-x-4">
            {loading && selectedMetric === 'lead-time' && (
              <div className="text-sm text-secondary">Loading...</div>
            )}
            {error && selectedMetric === 'lead-time' && (
              <div className="text-sm text-red-500" title={error}>Data fetch error</div>
            )}
            {chartData.length > 0 && (
              <div className="text-sm text-secondary">
                Latest: <span className="font-semibold text-primary">{chartData[chartData.length - 1]?.value} {config.unit}</span>
                {selectedMetric === 'lead-time' && historicalData.length > 0 && filteredChartData[filteredChartData.length - 1]?.issue_count && (
                  <span className="text-xs text-secondary ml-1">
                    ({chartData[chartData.length - 1]?.issue_count} issues)
                  </span>
                )}
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              {periodOptions.map((period) => (
                <button
                  key={period.value}
                  onClick={() => {
                    setSelectedPeriod(period.value)
                    if (period.value === 'CUSTOM') {
                      setShowCustomRange(true)
                    } else {
                      setShowCustomRange(false)
                    }
                  }}
                  className={`px-3 py-1 text-xs rounded-full transition-all duration-200 font-medium ${selectedPeriod === period.value
                    ? ''
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200 border border-gray-300'
                    }`}
                  style={
                    selectedPeriod === period.value
                      ? {
                        background: config.gradient,
                        color: config.onColor
                      }
                      : {}
                  }
                >
                  {period.label}
                </button>
              ))}
            </div>

            {/* Remove Empty Weeks Checkbox */}
            <div className="flex items-center space-x-2 ml-4">
              <input
                type="checkbox"
                id="removeEmptyWeeks"
                checked={removeEmptyWeeks}
                onChange={(e) => setRemoveEmptyWeeks(e.target.checked)}
                className="w-4 h-4 text-blue-600 bg-primary border-default rounded focus:ring-blue-500 focus:ring-2"
              />
              <label htmlFor="removeEmptyWeeks" className="text-sm text-secondary">
                Remove empty weeks
              </label>
            </div>
          </div>
        </div>

        {/* Combined Legend: Trend lines + Historical/Forecast */}
        {chartData.length > 1 && (
          <div className="flex items-center justify-center space-x-6 text-xs text-secondary mb-4">
            {/* Median */}
            <div className="flex items-center space-x-2">
              <div
                className="w-6 h-0.5 border-t-2"
                style={{ borderColor: 'var(--color-3, #059669)' }}
              ></div>
              <span
                className="px-2 py-1 rounded text-xs font-semibold"
                style={{
                  backgroundColor: 'var(--color-3, #059669)',
                  color: 'var(--on-color-3, #ffffff)'
                }}
              >
                Median
              </span>
            </div>

            {/* Mean */}
            <div className="flex items-center space-x-2">
              <div
                className="w-6 h-0.5 border-t-2"
                style={{ borderColor: 'var(--color-4, #0EA5E9)' }}
              ></div>
              <span
                className="px-2 py-1 rounded text-xs font-semibold"
                style={{
                  backgroundColor: 'var(--color-4, #0EA5E9)',
                  color: 'var(--on-color-4, #ffffff)'
                }}
              >
                Mean
              </span>
            </div>

            {/* Historical Data */}
            <div className="flex items-center space-x-2">
              <div
                className="w-6 h-0.5 border-t-2"
                style={{ borderColor: config.color1 }}
              ></div>
              <span className="text-xs">Historical</span>
            </div>

            {/* Forecast Data */}
            {forecastData.length > 0 && (
              <div className="flex items-center space-x-2">
                <div
                  className="w-6 h-0.5 border-t-2"
                  style={{ borderColor: 'var(--color-5, #8B5CF6)' }}
                ></div>
                <span className="text-xs">Forecast ({forecastConfig?.duration || '3M'})</span>
              </div>
            )}

            {/* Trend Line */}
            <div className="flex items-center space-x-2">
              <div
                className="w-6 h-0.5 border-t-2"
                style={{ borderColor: '#ec4899' }}
              ></div>
              <span className="text-xs">Trend</span>
            </div>
          </div>
        )}

        {/* Chart */}
        <div className="w-full h-96 focus:outline-none relative" style={{ outline: 'none' }}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart
              key={`chart-${selectedMetric}-${theme}`} // Force re-render on theme change
              data={formattedData}
              margin={{
                top: 10,
                right: 10,
                left: 10,
                bottom: 10, // Minimal bottom margin
              }}
              style={{ outline: 'none' }}
            >
              {/* Gradient definitions */}
              <defs>
                {/* Historical data gradient - theme-aware */}
                <linearGradient id={`areaGradient-${selectedMetric}-${theme}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={getChartSafeColor(config.color1.replace('var(', '').replace(')', ''), '#C8102E')} stopOpacity={0.8} />
                  <stop offset="30%" stopColor={getChartSafeColor(config.color1.replace('var(', '').replace(')', ''), '#C8102E')} stopOpacity={0.4} />
                  <stop offset="100%" stopColor={getChartSafeColor(config.color2.replace('var(', '').replace(')', ''), '#253746')} stopOpacity={0.1} />
                </linearGradient>
                {/* Forecast data gradient (different colors, more transparent) */}
                <linearGradient id={`forecastGradient-${selectedMetric}-${theme}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={getComputedColor('--color-5', '#8B5CF6')} stopOpacity={0.6} />
                  <stop offset="95%" stopColor={getComputedColor('--color-5', '#8B5CF6')} stopOpacity={0.1} />
                </linearGradient>
              </defs>

              <CartesianGrid
                strokeDasharray="2 2"
                stroke="#9ca3af"
                strokeOpacity={1}
                horizontal={true}
                vertical={true}
                strokeWidth={1}
              />
              <XAxis
                dataKey="displayLabel"
                tick={{
                  fontSize: 11,
                  fill: 'var(--text-primary, #1f2937)',
                  fontWeight: 400
                }}
                axisLine={{
                  stroke: 'var(--axis-color, #374151)',
                  strokeWidth: 1,
                  strokeLinecap: 'square'
                }}
                tickLine={{
                  stroke: 'var(--axis-color, #374151)',
                  strokeWidth: 1,
                  strokeLinecap: 'square'
                }}
                interval={(() => {
                  const dataLength = filteredChartData.length

                  // Rule: ≤24 weeks = weekly; >24 weeks = bi-weekly
                  if (dataLength <= 24) {
                    return 0 // Show all labels (weekly)
                  } else {
                    return 1 // Show every 2nd label (bi-weekly)
                  }
                })()}
                angle={-45}
                textAnchor="end"
                height={60}
              />
              <YAxis
                domain={['dataMin - 10%', 'dataMax + 10%']}
                tick={{
                  fontSize: 12,
                  fill: 'var(--text-primary, #1f2937)',
                  fontWeight: 400
                }}
                axisLine={{
                  stroke: 'var(--axis-color, #374151)',
                  strokeWidth: 1,
                  strokeLinecap: 'square'
                }}
                tickLine={{
                  stroke: 'var(--axis-color, #374151)',
                  strokeWidth: 1,
                  strokeLinecap: 'square'
                }}
                tickFormatter={(value) => Math.round(value).toString()}
                label={{
                  value: config.unit === 'days' ? 'Days' : config.unit,
                  angle: -90,
                  position: 'insideLeft',
                  style: {
                    textAnchor: 'middle',
                    fontSize: '12px',
                    fill: 'var(--text-primary, #1f2937)',
                    fontWeight: 600
                  }
                }}
              />


              {/* Reference lines for median and mean */}
              {chartData.length > 1 && (
                <>
                  <ReferenceLine
                    y={medianValue || 0}
                    stroke="var(--color-3, #059669)"
                    strokeOpacity={1}
                    strokeWidth={2.5}
                  />
                  <ReferenceLine
                    y={meanValue || 0}
                    stroke="var(--color-4, #0EA5E9)"
                    strokeOpacity={1}
                    strokeWidth={2.5}
                  />
                </>
              )}

              {/* Historical Area */}
              <Area
                type="monotone"
                dataKey="historical_mean"
                stroke="none"
                fill={`url(#areaGradient-${selectedMetric}-${theme})`}
                isAnimationActive={false}
                activeDot={false}
                connectNulls={false}
              />

              {/* Forecast Area (main fill like historical) */}
              <Area
                type="monotone"
                dataKey="forecast_mean"
                stroke="none"
                fill={`url(#forecastGradient-${selectedMetric}-${theme})`}
                isAnimationActive={false}
                activeDot={false}
                connectNulls={false}
              />


              <Tooltip
                content={({ active, payload, label }) => {
                  if (active && payload && payload.length) {
                    const data = payload[0].payload
                    return (
                      <div
                        style={{
                          backgroundColor: 'var(--bg-secondary, #f8fafc)',
                          border: '1px solid var(--border-color, #e2e8f0)',
                          borderRadius: '8px',
                          boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                          color: 'var(--text-primary, #1f2937)',
                          padding: '12px',
                          fontSize: '14px'
                        }}
                      >
                        <div style={{ fontWeight: 600, marginBottom: '8px', color: 'var(--text-primary, #1f2937)' }}>
                          {label}
                        </div>
                        <div style={{ color: 'var(--text-secondary, #6b7280)', marginBottom: '4px' }}>
                          <span style={{ fontWeight: 600, color: 'var(--text-primary, #1f2937)' }}>
                            {data.is_forecast ? data.forecast_mean : (data.historical_mean || data.value)} {config.unit}
                          </span>
                          <span style={{ marginLeft: '4px' }}>
                            - {config.title} {data.is_forecast ? '(Forecast)' : ''}
                          </span>
                        </div>
                        {data.is_forecast && data.forecast_confidence_range && (
                          <div style={{ color: 'var(--text-secondary, #6b7280)', fontSize: '12px', marginBottom: '4px' }}>
                            <span style={{ fontWeight: 600, color: 'var(--text-primary, #1f2937)' }}>
                              Confidence: {data.forecast_confidence_range[0].toFixed(1)} - {data.forecast_confidence_range[1].toFixed(1)} {config.unit}
                            </span>
                          </div>
                        )}
                        {data.issue_count && (
                          <div style={{ color: 'var(--text-secondary, #6b7280)', fontSize: '12px' }}>
                            <span style={{ fontWeight: 600, color: 'var(--text-primary, #1f2937)' }}>
                              {data.issue_count}
                            </span>
                            <span style={{ marginLeft: '4px' }}>issues completed</span>
                          </div>
                        )}
                        {data.avg_value && (
                          <div style={{ color: 'var(--text-muted, #9ca3af)', fontSize: '12px', marginTop: '4px' }}>
                            Avg: {data.avg_value} {config.unit}
                          </div>
                        )}
                      </div>
                    )
                  }
                  return null
                }}
                cursor={false}
                isAnimationActive={false}
              />

              {/* Historical Line */}
              <Line
                type="monotone"
                dataKey="historical_mean"
                stroke={getChartSafeColor(config.color1.replace('var(', '').replace(')', ''), '#C8102E')}
                strokeWidth={3}
                connectNulls={false}
                dot={{
                  fill: getChartSafeColor(config.color1.replace('var(', '').replace(')', ''), '#C8102E'),
                  strokeWidth: 2,
                  stroke: '#ffffff',
                  r: 6
                }}
                activeDot={{
                  r: 8,
                  fill: getChartSafeColor(config.color1.replace('var(', '').replace(')', ''), '#C8102E'),
                  stroke: '#ffffff',
                  strokeWidth: 2
                }}
              />

              {/* Forecast Line (solid, different color) */}
              <Line
                type="monotone"
                dataKey="forecast_mean"
                stroke={getComputedColor('--color-5', '#8B5CF6')}
                strokeWidth={3}
                connectNulls={false}
                dot={{
                  fill: getComputedColor('--color-5', '#8B5CF6'),
                  strokeWidth: 2,
                  stroke: '#ffffff',
                  r: 4
                }}
                activeDot={{
                  r: 6,
                  fill: getComputedColor('--color-5', '#8B5CF6'),
                  stroke: '#ffffff',
                  strokeWidth: 2
                }}
              />

              {/* Trend Line (shows overall direction) */}
              <Line
                type="monotone"
                dataKey="trend_value"
                stroke="#ec4899"
                strokeWidth={2}
                connectNulls={true}
                dot={false}
                activeDot={false}
              />


            </ComposedChart>
          </ResponsiveContainer>

          {/* HTML Labels positioned absolutely */}
          {filteredChartData.length > 1 && (() => {
            // Calculate the actual Y positions of the trend lines within the chart
            const chartHeight = 384 - 80 // h-96 (384px) minus top/bottom margins (20px top + 60px bottom)
            const validChartValues = filteredChartData
              .map(d => d.value)
              .filter(value => value !== null && value !== undefined && !isNaN(value))

            if (validChartValues.length === 0) return null // No valid data to display

            const maxValue = Math.max(...validChartValues)
            const minValue = Math.min(...validChartValues)

            // Match the YAxis domain calculation: dataMin - 10%, dataMax + 10%
            const chartMax = maxValue * 1.1
            const chartMin = Math.max(0, minValue * 0.9)
            const chartRange = chartMax - chartMin

            // Calculate Y positions (inverted because CSS top is from top, chart is from bottom)
            const safeMedianValue = medianValue || 0
            const safeMeanValue = meanValue || 0
            const safeChartRange = chartRange || 1 // Prevent division by zero

            // Calculate Y positions - position boxes ABOVE the lines
            const medianY = 20 + ((chartMax - safeMedianValue) / safeChartRange) * chartHeight - 30 // 30px above the line
            const meanY = 20 + ((chartMax - safeMeanValue) / safeChartRange) * chartHeight - 30 // 30px above the line

            return (
              <>
                {/* Median Label */}
                <div
                  className="absolute px-2 py-1 rounded text-xs font-semibold shadow-lg"
                  style={{
                    top: `${Math.max(20, Math.min(medianY - 10, chartHeight - 10))}px`,
                    right: '60px', // Inside chart area
                    backgroundColor: getComputedColor('--color-3', '#059669'),
                    color: calculateOnColor(getComputedColor('--color-3', '#059669')),
                    opacity: 1,
                    zIndex: 10
                  }}
                >
                  Median: {(medianValue || 0).toFixed(1)}{config.unit === 'days' ? 'd' : config.unit}
                </div>

                {/* Mean Label */}
                <div
                  className="absolute px-2 py-1 rounded text-xs font-semibold shadow-lg"
                  style={{
                    top: `${Math.max(20, Math.min(meanY - 10, chartHeight - 10))}px`,
                    left: '80px', // Inside chart area, away from y-axis
                    backgroundColor: getComputedColor('--color-4', '#0EA5E9'),
                    color: calculateOnColor(getComputedColor('--color-4', '#0EA5E9')),
                    opacity: 1,
                    zIndex: 10
                  }}
                >
                  Mean: {(meanValue || 0).toFixed(1)}{config.unit === 'days' ? 'd' : config.unit}
                </div>
              </>
            )
          })()}
        </div>


      </div>

      {/* Custom Date Range Modal */}
      {showCustomRange && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="bg-secondary border border-default rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl"
          >
            <h3 className="text-lg font-semibold text-primary mb-4">Custom Date Range</h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm text-secondary mb-2">Start Date</label>
                <input
                  type="date"
                  value={customStartDate}
                  onChange={(e) => setCustomStartDate(e.target.value)}
                  className="w-full px-3 py-2 bg-primary border border-default rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm text-secondary mb-2">End Date</label>
                <input
                  type="date"
                  value={customEndDate}
                  onChange={(e) => setCustomEndDate(e.target.value)}
                  className="w-full px-3 py-2 bg-primary border border-default rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            <div className="flex justify-end space-x-3 mt-6">
              <button
                onClick={() => setShowCustomRange(false)}
                className="px-4 py-2 bg-tertiary text-muted rounded-lg hover:bg-secondary transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  setShowCustomRange(false)
                  // Data will automatically update via getFilteredData
                }}
                disabled={!customStartDate || !customEndDate}
                className="px-4 py-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed bg-blue-600 hover:bg-blue-700 text-white disabled:bg-gray-400"
              >
                Apply Range
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </motion.div>
  )
}
