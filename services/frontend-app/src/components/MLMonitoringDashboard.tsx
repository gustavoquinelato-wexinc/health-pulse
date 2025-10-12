/**
 * ML Monitoring Dashboard Component
 * Phase 1-6: Frontend Service Compatibility - Admin interface for ML monitoring
 */

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  LearningMemoryResponse,
  PredictionsResponse,
  AnomalyAlertsResponse,
  MLStatsResponse,
} from '../types';
import apiService from '../services/apiService';

interface MLMonitoringDashboardProps {
  clientId: number;
  className?: string;
}

export const MLMonitoringDashboard: React.FC<MLMonitoringDashboardProps> = ({
  clientId,
  className = '',
}) => {
  const [stats, setStats] = useState<MLStatsResponse | null>(null);
  const [learningMemory, setLearningMemory] = useState<LearningMemoryResponse | null>(null);
  const [predictions, setPredictions] = useState<PredictionsResponse | null>(null);
  const [anomalyAlerts, setAnomalyAlerts] = useState<AnomalyAlertsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'learning' | 'predictions' | 'alerts'>('overview');

  useEffect(() => {
    const fetchMLData = async () => {
      try {
        setLoading(true);
        setError(null);

        const [statsResponse, learningResponse, predictionsResponse, alertsResponse] = await Promise.allSettled([
          apiService.getMLStats(clientId, 30),
          apiService.getLearningMemory(clientId, { limit: 10 }),
          apiService.getPredictions(clientId, { limit: 10 }),
          apiService.getAnomalyAlerts(clientId, { limit: 10, acknowledged: false }),
        ]);

        if (statsResponse.status === 'fulfilled') {
          setStats(statsResponse.value);
        }

        if (learningResponse.status === 'fulfilled') {
          setLearningMemory(learningResponse.value);
        }

        if (predictionsResponse.status === 'fulfilled') {
          setPredictions(predictionsResponse.value);
        }

        if (alertsResponse.status === 'fulfilled') {
          setAnomalyAlerts(alertsResponse.value);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch ML monitoring data');
      } finally {
        setLoading(false);
      }
    };

    fetchMLData();
  }, [clientId]);

  if (loading) {
    return (
      <div className={`flex items-center justify-center p-8 ${className}`}>
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600"></div>
        <span className="ml-2 text-secondary">Loading ML monitoring data...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`p-4 bg-red-50 border border-red-200 rounded-lg ${className}`}>
        <div className="flex items-center">
          <div className="text-red-600">
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
          </div>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-red-800">Error loading ML monitoring data</h3>
            <p className="text-sm text-red-700 mt-1">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  const tabs = [
    { id: 'overview', label: 'Overview', count: null },
    { id: 'learning', label: 'Learning Memory', count: learningMemory?.total_count },
    { id: 'predictions', label: 'Predictions', count: predictions?.total_count },
    { id: 'alerts', label: 'Alerts', count: anomalyAlerts?.total_count },
  ] as const;

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-primary">ML Monitoring Dashboard</h2>
        <div className="text-sm text-tertiary">
          {stats && `Period: ${stats.period.days} days (${stats.period.start_date} - ${stats.period.end_date})`}
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-border">
        <nav className="-mb-px flex space-x-8">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                activeTab === tab.id
                  ? 'border-purple-500 text-purple-600'
                  : 'border-transparent text-secondary hover:text-primary hover:border-gray-300'
              }`}
            >
              {tab.label}
              {tab.count !== null && tab.count !== undefined && (
                <span className={`ml-2 px-2 py-1 rounded-full text-xs ${
                  activeTab === tab.id ? 'bg-purple-100 text-purple-800' : 'bg-gray-100 text-gray-600'
                }`}>
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="mt-6">
        {activeTab === 'overview' && stats && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-6"
          >
            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-card border border-border rounded-lg p-4">
                <div className="text-2xl font-bold text-blue-600">{stats.summary.learning_memories}</div>
                <div className="text-sm text-secondary">Learning Memories</div>
              </div>
              <div className="bg-card border border-border rounded-lg p-4">
                <div className="text-2xl font-bold text-green-600">{stats.summary.predictions}</div>
                <div className="text-sm text-secondary">Predictions</div>
              </div>
              <div className="bg-card border border-border rounded-lg p-4">
                <div className="text-2xl font-bold text-yellow-600">{stats.summary.anomaly_alerts}</div>
                <div className="text-sm text-secondary">Anomaly Alerts</div>
              </div>
              <div className="bg-card border border-border rounded-lg p-4">
                <div className="text-2xl font-bold text-red-600">{stats.summary.unacknowledged_alerts}</div>
                <div className="text-sm text-secondary">Unacknowledged</div>
              </div>
            </div>

            {/* Model Usage */}
            {stats.model_usage.length > 0 && (
              <div className="bg-card border border-border rounded-lg p-6">
                <h3 className="text-lg font-semibold text-primary mb-4">Model Usage</h3>
                <div className="space-y-3">
                  {stats.model_usage.map((model, index) => (
                    <div key={index} className="flex items-center justify-between">
                      <span className="font-medium text-secondary">{model.model_name}</span>
                      <span className="text-sm text-tertiary">{model.prediction_count} predictions</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}

        {activeTab === 'learning' && learningMemory && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-4"
          >
            {learningMemory.learning_memories.length === 0 ? (
              <div className="text-center p-8">
                <div className="text-secondary">No learning memories found</div>
              </div>
            ) : (
              learningMemory.learning_memories.map((memory) => (
                <div key={memory.id} className="bg-card border border-border rounded-lg p-4">
                  <div className="flex items-start justify-between mb-2">
                    <h4 className="font-medium text-primary">{memory.error_type}</h4>
                    <span className="text-xs text-tertiary">{new Date(memory.created_at).toLocaleString()}</span>
                  </div>
                  <div className="space-y-2 text-sm">
                    <div><span className="font-medium">Intent:</span> {memory.user_intent}</div>
                    <div><span className="font-medium">WorkItem:</span> {memory.specific_issue}</div>
                    <div><span className="font-medium">Suggested Fix:</span> {memory.suggested_fix}</div>
                    <div><span className="font-medium">Confidence:</span> {(memory.confidence * 100).toFixed(1)}%</div>
                  </div>
                </div>
              ))
            )}
          </motion.div>
        )}

        {activeTab === 'predictions' && predictions && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-4"
          >
            {predictions.predictions.length === 0 ? (
              <div className="text-center p-8">
                <div className="text-secondary">No predictions found</div>
              </div>
            ) : (
              predictions.predictions.map((prediction) => (
                <div key={prediction.id} className="bg-card border border-border rounded-lg p-4">
                  <div className="flex items-start justify-between mb-2">
                    <h4 className="font-medium text-primary">{prediction.model_name}</h4>
                    <span className="text-xs text-tertiary">{new Date(prediction.created_at).toLocaleString()}</span>
                  </div>
                  <div className="space-y-2 text-sm">
                    <div><span className="font-medium">Type:</span> {prediction.prediction_type}</div>
                    {prediction.model_version && (
                      <div><span className="font-medium">Version:</span> {prediction.model_version}</div>
                    )}
                    {prediction.confidence_score && (
                      <div><span className="font-medium">Confidence:</span> {(prediction.confidence_score * 100).toFixed(1)}%</div>
                    )}
                    {prediction.accuracy_score && (
                      <div><span className="font-medium">Accuracy:</span> {(prediction.accuracy_score * 100).toFixed(1)}%</div>
                    )}
                  </div>
                </div>
              ))
            )}
          </motion.div>
        )}

        {activeTab === 'alerts' && anomalyAlerts && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-4"
          >
            {anomalyAlerts.anomaly_alerts.length === 0 ? (
              <div className="text-center p-8">
                <div className="text-secondary">No anomaly alerts found</div>
              </div>
            ) : (
              anomalyAlerts.anomaly_alerts.map((alert) => (
                <div key={alert.id} className={`border rounded-lg p-4 ${
                  alert.severity === 'high' ? 'bg-red-50 border-red-200' :
                  alert.severity === 'medium' ? 'bg-yellow-50 border-yellow-200' :
                  'bg-blue-50 border-blue-200'
                }`}>
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center space-x-2">
                      <h4 className="font-medium text-primary">{alert.model_name}</h4>
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                        alert.severity === 'high' ? 'bg-red-100 text-red-800' :
                        alert.severity === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                        'bg-blue-100 text-blue-800'
                      }`}>
                        {alert.severity}
                      </span>
                      {!alert.acknowledged && (
                        <span className="px-2 py-1 rounded-full text-xs font-medium bg-orange-100 text-orange-800">
                          Unacknowledged
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-tertiary">{new Date(alert.created_at).toLocaleString()}</span>
                  </div>
                  <div className="text-sm text-secondary">
                    Alert data: {JSON.stringify(alert.alert_data, null, 2)}
                  </div>
                  {alert.acknowledged && alert.acknowledged_at && (
                    <div className="mt-2 text-xs text-tertiary">
                      Acknowledged: {new Date(alert.acknowledged_at).toLocaleString()}
                    </div>
                  )}
                </div>
              ))
            )}
          </motion.div>
        )}
      </div>
    </div>
  );
};

export default MLMonitoringDashboard;
