
import { useState } from 'react'

type ForecastModel = 'Linear Regression' | 'Exponential Smoothing' | 'Prophet'
type ForecastDuration = '3M' | '6M'

interface ForecastingControlsProps {
  model: ForecastModel
  duration: ForecastDuration
  enabled: boolean
  loading: boolean
  onModelChange: (model: ForecastModel) => void
  onDurationChange: (duration: ForecastDuration) => void
  onApplyForecast: () => void
  onClearForecast: () => void
}

export default function ForecastingControls({
  model,
  duration,
  enabled,
  loading,
  onModelChange,
  onDurationChange,
  onApplyForecast,
  onClearForecast
}: ForecastingControlsProps) {
  const [showHelp, setShowHelp] = useState(false)

  return (
    <>
      {/* Forecasting Controls Card - All elements in same row */}
      <div className="card p-4 hover:shadow-md transition-all duration-300">
        <div className="flex items-end space-x-2">
          {/* Forecasting Model with Help */}
          <div className="flex flex-col flex-1">
            <div className="flex items-center space-x-1 mb-1">
              <label className="text-xs text-secondary">Forecasting Model</label>
              <button
                onClick={() => setShowHelp(true)}
                className="w-4 h-4 rounded-full bg-blue-100 border border-blue-300 text-xs text-blue-600 hover:bg-blue-200 transition-all flex items-center justify-center"
                title="Forecast model information"
              >
                ?
              </button>
            </div>
            <select
              value={model}
              onChange={(e) => onModelChange(e.target.value as ForecastModel)}
              disabled={loading}
              className="bg-primary border border-default rounded px-2 py-2 text-sm"
            >
              <option value="Linear Regression">Linear</option>
              <option value="Exponential Smoothing">Exponential</option>
              <option value="Prophet">Prophet</option>
            </select>
          </div>

          {/* Duration */}
          <div className="flex flex-col">
            <label className="text-xs text-secondary mb-1">Duration</label>
            <div className="flex bg-secondary border-2 border-default rounded p-1">
              {(['3M', '6M'] as ForecastDuration[]).map((durationOption) => (
                <button
                  key={durationOption}
                  onClick={() => onDurationChange(durationOption)}
                  disabled={loading}
                  className={`px-2 py-1 text-xs font-medium rounded transition-all ${duration === durationOption
                    ? 'text-white shadow-sm'
                    : 'text-secondary hover:text-primary hover:bg-primary'
                    }`}
                  style={duration === durationOption ? {
                    background: 'linear-gradient(135deg, var(--color-1), var(--color-2))'
                  } : {}}
                >
                  {durationOption}
                </button>
              ))}
            </div>
          </div>

          {/* Apply/Clear Button */}
          <div className="flex flex-col">
            {enabled ? (
              <button
                onClick={onClearForecast}
                className="px-3 py-2 text-sm font-medium text-secondary hover:text-primary border border-default rounded hover:bg-secondary transition-all"
              >
                Clear
              </button>
            ) : (
              <button
                onClick={onApplyForecast}
                disabled={loading}
                className={`px-3 py-2 text-sm font-medium rounded transition-all ${loading
                  ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  : 'bg-blue-600 text-white hover:bg-blue-700'
                  }`}
              >
                {loading ? (
                  <div className="flex items-center justify-center space-x-1">
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    <span>Applying...</span>
                  </div>
                ) : (
                  'Apply'
                )}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Help Modal */}
      {showHelp && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-primary border border-default rounded-lg p-6 max-w-md mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-primary">Forecast Models</h3>
              <button
                onClick={() => setShowHelp(false)}
                className="text-secondary hover:text-primary"
              >
                ✕
              </button>
            </div>
            <div className="space-y-3 text-sm">
              <div>
                <strong className="text-primary">Linear Regression:</strong>
                <p className="text-secondary">Simple trend-based prediction using historical data points. Best for stable, linear trends.</p>
              </div>
              <div>
                <strong className="text-primary">Exponential Smoothing:</strong>
                <p className="text-secondary">Weighted average giving more importance to recent observations. Good for data with trends but no seasonality.</p>
              </div>
              <div>
                <strong className="text-primary">Prophet:</strong>
                <p className="text-secondary">Advanced time series forecasting with seasonality detection. Best for complex patterns and long-term forecasts.</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
