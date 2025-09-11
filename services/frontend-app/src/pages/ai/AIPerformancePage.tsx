import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';
import { BarChart3, TrendingUp, Clock, DollarSign, Activity, AlertCircle, Calendar } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import CollapsedSidebar from '../../components/CollapsedSidebar';
import Header from '../../components/Header';
import useDocumentTitle from '../../hooks/useDocumentTitle';

interface PerformanceMetrics {
  total_requests: number;
  avg_response_time: number;
  total_cost: number;
  success_rate: number;
  provider_usage: Array<{
    provider: string;
    requests: number;
    cost: number;
    avg_response_time: number;
  }>;
  daily_usage: Array<{
    date: string;
    requests: number;
    cost: number;
    avg_response_time: number;
  }>;
}

const AIPerformancePage: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [metrics, setMetrics] = useState<PerformanceMetrics | null>(null);
  const [loading, setLoading] = useState(false);
  const [dateRange, setDateRange] = useState({
    start: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0], // 7 days ago
    end: new Date().toISOString().split('T')[0] // today
  });
  const [message, setMessage] = useState<{type: 'success' | 'error' | 'info', text: string} | null>(null);

  // Set document title
  useDocumentTitle('AI Performance');

  // Check if user is admin
  const isAdmin = user?.is_admin || user?.role === 'admin';

  const showMessage = (type: 'success' | 'error' | 'info', text: string) => {
    setMessage({ type, text });
    setTimeout(() => setMessage(null), 5000);
  };

  useEffect(() => {
    if (isAdmin) {
      fetchMetrics();
    }
  }, [isAdmin, dateRange]);

  const fetchMetrics = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/api/v1/ai-performance-metrics', {
        params: {
          start_date: dateRange.start,
          end_date: dateRange.end
        }
      });
      setMetrics(response.data);
    } catch (error) {
      console.error('Error fetching AI performance metrics:', error);
      showMessage('error', 'Failed to fetch performance metrics');
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 4
    }).format(amount);
  };

  const formatNumber = (num: number) => {
    return new Intl.NumberFormat('en-US').format(num);
  };

  if (!isAdmin) {
    return (
      <div className="min-h-screen bg-primary">
        <Header />
        <div className="flex">
          <CollapsedSidebar />
          <main className="flex-1 p-6 ml-16">
            <div className="max-w-4xl mx-auto">
              <div className="card p-8 text-center">
                <AlertCircle className="w-16 h-16 text-yellow-500 mx-auto mb-4" />
                <h2 className="text-2xl font-bold text-primary mb-2">Access Denied</h2>
                <p className="text-secondary">You need administrator privileges to access AI performance metrics.</p>
              </div>
            </div>
          </main>
        </div>
      </div>
    );
  }

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
        {/* Header */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="space-y-2">
              <div className="flex items-center space-x-3">
                <button
                  onClick={() => navigate('/settings')}
                  className="text-secondary hover:text-primary transition-colors"
                >
                  ← Back to Settings
                </button>
              </div>
              <div className="flex items-center space-x-3">
                <BarChart3 className="w-8 h-8 text-color-3" />
                <div>
                  <h1 className="text-3xl font-bold text-primary">AI Performance</h1>
                  <p className="text-secondary">Monitor AI usage, costs, and performance metrics</p>
                </div>
              </div>
            </div>
            
            {/* Date Range Selector */}
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                <Calendar className="w-4 h-4 text-text-secondary" />
                <input
                  type="date"
                  value={dateRange.start}
                  onChange={(e) => setDateRange(prev => ({ ...prev, start: e.target.value }))}
                  className="px-3 py-2 border border-border-color rounded-md focus:outline-none focus:ring-2 focus:ring-color-1"
                />
                <span className="text-text-secondary">to</span>
                <input
                  type="date"
                  value={dateRange.end}
                  onChange={(e) => setDateRange(prev => ({ ...prev, end: e.target.value }))}
                  className="px-3 py-2 border border-border-color rounded-md focus:outline-none focus:ring-2 focus:ring-color-1"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Message */}
        {message && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className={`mb-6 p-4 rounded-lg border ${
              message.type === 'success' ? 'bg-green-50 border-green-200 text-green-800' :
              message.type === 'error' ? 'bg-red-50 border-red-200 text-red-800' :
              'bg-blue-50 border-blue-200 text-blue-800'
            }`}
          >
            <div className="flex items-center space-x-2">
              <AlertCircle className="w-4 h-4" />
              <span>{message.text}</span>
            </div>
          </motion.div>
        )}

        {loading ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-color-1 mx-auto"></div>
            <p className="text-text-secondary mt-4">Loading performance metrics...</p>
          </div>
        ) : metrics ? (
          <div className="space-y-6">
            {/* Key Metrics Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="card p-6"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-text-secondary">Total Requests</p>
                    <p className="text-2xl font-bold text-text-primary">{formatNumber(metrics.total_requests)}</p>
                  </div>
                  <Activity className="w-8 h-8 text-color-1" />
                </div>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
                className="card p-6"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-text-secondary">Avg Response Time</p>
                    <p className="text-2xl font-bold text-text-primary">{metrics.avg_response_time.toFixed(0)}ms</p>
                  </div>
                  <Clock className="w-8 h-8 text-color-2" />
                </div>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="card p-6"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-text-secondary">Total Cost</p>
                    <p className="text-2xl font-bold text-text-primary">{formatCurrency(metrics.total_cost)}</p>
                  </div>
                  <DollarSign className="w-8 h-8 text-color-3" />
                </div>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
                className="card p-6"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-text-secondary">Success Rate</p>
                    <p className="text-2xl font-bold text-text-primary">{(metrics.success_rate * 100).toFixed(1)}%</p>
                  </div>
                  <TrendingUp className="w-8 h-8 text-color-4" />
                </div>
              </motion.div>
            </div>

            {/* Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Daily Usage Chart */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 }}
                className="card"
              >
                <div className="p-6 border-b border-border-color">
                  <h3 className="text-lg font-semibold text-text-primary">Daily Usage</h3>
                  <p className="text-text-secondary">Requests and costs over time</p>
                </div>
                <div className="p-6">
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={metrics.daily_usage}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" />
                      <YAxis />
                      <Tooltip />
                      <Line type="monotone" dataKey="requests" stroke="#3B82F6" strokeWidth={2} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </motion.div>

              {/* Provider Usage Chart */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.5 }}
                className="card"
              >
                <div className="p-6 border-b border-border-color">
                  <h3 className="text-lg font-semibold text-text-primary">Provider Usage</h3>
                  <p className="text-text-secondary">Requests by provider</p>
                </div>
                <div className="p-6">
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={metrics.provider_usage}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="provider" />
                      <YAxis />
                      <Tooltip />
                      <Bar dataKey="requests" fill="#10B981" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </motion.div>
            </div>

            {/* Provider Details Table */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6 }}
              className="card"
            >
              <div className="p-6 border-b border-border-color">
                <h3 className="text-lg font-semibold text-text-primary">Provider Performance</h3>
                <p className="text-text-secondary">Detailed metrics by AI provider</p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-bg-primary">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">
                        Provider
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">
                        Requests
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">
                        Avg Response Time
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">
                        Total Cost
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border-color">
                    {metrics.provider_usage.map((provider, index) => (
                      <tr key={index} className="hover:bg-bg-primary">
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-text-primary">
                          {provider.provider}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-text-secondary">
                          {formatNumber(provider.requests)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-text-secondary">
                          {provider.avg_response_time.toFixed(0)}ms
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-text-secondary">
                          {formatCurrency(provider.cost)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </motion.div>
          </div>
        ) : (
          <div className="text-center py-12">
            <BarChart3 className="w-16 h-16 text-muted mx-auto mb-4" />
            <h3 className="text-lg font-medium text-primary mb-2">No Performance Data</h3>
            <p className="text-secondary">No AI performance metrics available for the selected date range.</p>
          </div>
        )}
          </motion.div>
        </main>
      </div>
    </div>
  );
};

export default AIPerformancePage;
