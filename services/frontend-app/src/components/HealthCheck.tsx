/**
 * Health Check Component with ML infrastructure monitoring
 * Phase 1-6: Frontend Service Compatibility
 */

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  DatabaseHealthResponse,
  MLHealthResponse,
  ComprehensiveHealthResponse,
} from '../types';
import apiService from '../services/apiService';

interface HealthCheckProps {
  autoRefresh?: boolean;
  refreshInterval?: number;
  className?: string;
}

export const HealthCheck: React.FC<HealthCheckProps> = ({
  autoRefresh = true,
  refreshInterval = 30000, // 30 seconds
  className = '',
}) => {
  const [basicHealth, setBasicHealth] = useState<any>(null);
  const [dbHealth, setDbHealth] = useState<DatabaseHealthResponse | null>(null);
  const [mlHealth, setMlHealth] = useState<MLHealthResponse | null>(null);
  const [comprehensiveHealth, setComprehensiveHealth] = useState<ComprehensiveHealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const checkHealth = async () => {
    try {
      setError(null);

      const [basicResponse, dbResponse, mlResponse, comprehensiveResponse] = await Promise.allSettled([
        apiService.getBasicHealth(),
        apiService.getDatabaseHealth(),
        apiService.getMLHealth(),
        apiService.getComprehensiveHealth(),
      ]);

      if (basicResponse.status === 'fulfilled') {
        setBasicHealth(basicResponse.value);
      }

      if (dbResponse.status === 'fulfilled') {
        setDbHealth(dbResponse.value);
      }

      if (mlResponse.status === 'fulfilled') {
        setMlHealth(mlResponse.value);
      }

      if (comprehensiveResponse.status === 'fulfilled') {
        setComprehensiveHealth(comprehensiveResponse.value);
      }

      setLastUpdated(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch health status');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkHealth();

    if (autoRefresh) {
      const interval = setInterval(checkHealth, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [autoRefresh, refreshInterval]);

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'healthy':
      case 'ok':
      case 'available':
        return 'text-green-600 bg-green-100';
      case 'degraded':
      case 'warning':
        return 'text-yellow-600 bg-yellow-100';
      case 'unhealthy':
      case 'error':
      case 'unavailable':
        return 'text-red-600 bg-red-100';
      default:
        return 'text-gray-600 bg-gray-100';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status.toLowerCase()) {
      case 'healthy':
      case 'ok':
      case 'available':
        return (
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
          </svg>
        );
      case 'degraded':
      case 'warning':
        return (
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
          </svg>
        );
      case 'unhealthy':
      case 'error':
      case 'unavailable':
        return (
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
          </svg>
        );
      default:
        return (
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
          </svg>
        );
    }
  };

  if (loading && !basicHealth && !dbHealth && !mlHealth) {
    return (
      <div className={`flex items-center justify-center p-8 ${className}`}>
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        <span className="ml-2 text-secondary">Checking system health...</span>
      </div>
    );
  }

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-primary">System Health</h2>
        <div className="flex items-center space-x-4">
          {lastUpdated && (
            <span className="text-sm text-tertiary">
              Last updated: {lastUpdated.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={checkHealth}
            disabled={loading}
            className="px-3 py-1 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {loading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-center">
            <div className="text-red-600">
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">Health check error</h3>
              <p className="text-sm text-red-700 mt-1">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Overall Status */}
      {comprehensiveHealth && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-card border border-border rounded-lg p-6"
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-primary">Overall System Status</h3>
            <div className={`flex items-center space-x-2 px-3 py-1 rounded-full ${getStatusColor(comprehensiveHealth.status)}`}>
              {getStatusIcon(comprehensiveHealth.status)}
              <span className="font-medium">{comprehensiveHealth.status}</span>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">{comprehensiveHealth.summary.healthy_components}</div>
              <div className="text-tertiary">Healthy</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-yellow-600">{comprehensiveHealth.summary.degraded_components}</div>
              <div className="text-tertiary">Degraded</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-red-600">{comprehensiveHealth.summary.unhealthy_components}</div>
              <div className="text-tertiary">Unhealthy</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-primary">{comprehensiveHealth.summary.total_components}</div>
              <div className="text-tertiary">Total</div>
            </div>
          </div>
        </motion.div>
      )}

      {/* Basic Health */}
      {basicHealth && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="bg-card border border-border rounded-lg p-6"
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-primary">Basic Service Health</h3>
            <div className={`flex items-center space-x-2 px-3 py-1 rounded-full ${getStatusColor(basicHealth.status || 'unknown')}`}>
              {getStatusIcon(basicHealth.status || 'unknown')}
              <span className="font-medium">{basicHealth.status || 'Unknown'}</span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div>
              <span className="font-medium text-secondary">Service:</span> {basicHealth.message || 'Backend Service'}
            </div>
            <div>
              <span className="font-medium text-secondary">Version:</span> {basicHealth.version || 'Unknown'}
            </div>
            <div>
              <span className="font-medium text-secondary">Database:</span> {basicHealth.database_status || 'Unknown'}
            </div>
            <div>
              <span className="font-medium text-secondary">Message:</span> {basicHealth.database_message || 'No message'}
            </div>
          </div>
        </motion.div>
      )}

      {/* Database Health */}
      {dbHealth && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-card border border-border rounded-lg p-6"
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-primary">Database Health</h3>
            <div className={`flex items-center space-x-2 px-3 py-1 rounded-full ${getStatusColor(dbHealth.status)}`}>
              {getStatusIcon(dbHealth.status)}
              <span className="font-medium">{dbHealth.status}</span>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <span className="font-medium text-secondary">Connection:</span> {dbHealth.database_connection}
            </div>

            {dbHealth.ml_tables && Object.keys(dbHealth.ml_tables).length > 0 && (
              <div>
                <h4 className="font-medium text-secondary mb-2">ML Tables</h4>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                  {Object.entries(dbHealth.ml_tables).map(([table, status]) => (
                    <div key={table} className={`flex items-center space-x-2 px-2 py-1 rounded ${getStatusColor(status)}`}>
                      {getStatusIcon(status)}
                      <span className="text-sm font-medium">{table}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {dbHealth.vector_columns && Object.keys(dbHealth.vector_columns).length > 0 && (
              <div>
                <h4 className="font-medium text-secondary mb-2">Vector Columns</h4>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                  {Object.entries(dbHealth.vector_columns).map(([column, count]) => (
                    <div key={column} className="flex justify-between items-center px-2 py-1 bg-gray-50 rounded">
                      <span className="text-sm font-medium">{column}</span>
                      <span className="text-sm text-tertiary">{count}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </motion.div>
      )}

      {/* ML Infrastructure Health */}
      {mlHealth && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="bg-card border border-border rounded-lg p-6"
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-primary">ML Infrastructure Health</h3>
            <div className={`flex items-center space-x-2 px-3 py-1 rounded-full ${getStatusColor(mlHealth.status)}`}>
              {getStatusIcon(mlHealth.status)}
              <span className="font-medium">{mlHealth.status}</span>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <span className="font-medium text-secondary">Replica Connection:</span> {mlHealth.replica_connection}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* pgvector */}
              <div className={`p-3 rounded-lg border ${mlHealth.pgvector.available ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'}`}>
                <div className="flex items-center space-x-2 mb-2">
                  {getStatusIcon(mlHealth.pgvector.available ? 'available' : 'unavailable')}
                  <span className="font-medium">pgvector</span>
                </div>
                <div className="text-sm text-secondary">
                  {mlHealth.pgvector.available ? 'Available' : 'Unavailable'}
                  {mlHealth.pgvector.error && (
                    <div className="text-red-600 mt-1">{mlHealth.pgvector.error}</div>
                  )}
                </div>
              </div>

              {/* PostgresML */}
              <div className={`p-3 rounded-lg border ${mlHealth.postgresml.available ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'}`}>
                <div className="flex items-center space-x-2 mb-2">
                  {getStatusIcon(mlHealth.postgresml.available ? 'available' : 'unavailable')}
                  <span className="font-medium">PostgresML</span>
                </div>
                <div className="text-sm text-secondary">
                  {mlHealth.postgresml.available ? (
                    <>Available {mlHealth.postgresml.version && `(${mlHealth.postgresml.version})`}</>
                  ) : (
                    'Unavailable'
                  )}
                  {mlHealth.postgresml.error && (
                    <div className="text-red-600 mt-1">{mlHealth.postgresml.error}</div>
                  )}
                </div>
              </div>
            </div>

            <div className={`p-3 rounded-lg border ${mlHealth.vector_columns_accessible ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'}`}>
              <div className="flex items-center space-x-2">
                {getStatusIcon(mlHealth.vector_columns_accessible ? 'available' : 'unavailable')}
                <span className="font-medium">Vector Columns Access</span>
                <span className="text-sm text-secondary">
                  {mlHealth.vector_columns_accessible ? 'Accessible' : 'Not Accessible'}
                </span>
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  );
};

export default HealthCheck;
