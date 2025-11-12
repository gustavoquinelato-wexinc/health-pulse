import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Plus, Edit, X, TestTube, Check, AlertCircle, Settings, Play, Pause } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import CollapsedSidebar from '../../components/CollapsedSidebar';
import Header from '../../components/Header';
import useDocumentTitle from '../../hooks/useDocumentTitle';

interface AIProvider {
  id: number;
  name: string; // This will be the provider name from backend
  type?: string; // Provider type: Data Source or AI Provider
  provider: string;
  base_url?: string;
  ai_model?: string;
  ai_model_config?: any;
  fallback_integration_id?: number;
  active: boolean;
  created_at: string;
  updated_at: string;
}

interface ProviderType {
  value: string;
  label: string;
  description: string;
  count: number;
}

const AIConfigurationPage: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [providers, setProviders] = useState<AIProvider[]>([]);
  const [providerTypes, setProviderTypes] = useState<ProviderType[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingProvider, setEditingProvider] = useState<AIProvider | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    type: '',
    provider: '',
    base_url: '',
    ai_model: '',
    ai_model_config: '{}',
    fallback_integration_id: '',
    active: true
  });
  const [message, setMessage] = useState<{type: 'success' | 'error' | 'info', text: string} | null>(null);

  // Set document title
  useDocumentTitle('AI Configuration');

  // Check if user is admin
  const isAdmin = user?.is_admin || user?.role === 'admin';

  const showMessage = (type: 'success' | 'error' | 'info', text: string) => {
    setMessage({ type, text });
    setTimeout(() => setMessage(null), 5000);
  };

  useEffect(() => {
    if (isAdmin) {
      fetchProviders();
      fetchProviderTypes();
    }
  }, [isAdmin]);

  const fetchProviders = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/api/v1/ai-providers');
      setProviders(response.data.providers || []);
    } catch (error) {
      console.error('Error fetching AI providers:', error);
      showMessage('error', 'Failed to fetch AI providers');
    } finally {
      setLoading(false);
    }
  };

  const fetchProviderTypes = async () => {
    try {
      const response = await axios.get('/api/v1/ai-provider-types');
      setProviderTypes(response.data.provider_types || []);
    } catch (error) {
      console.error('Error fetching provider types:', error);
      // Fallback to default provider types if API fails
      setProviderTypes([
        { value: 'wex_gateway', label: 'WEX Gateway', description: 'Internal WEX AI service', count: 0 },
        { value: 'sentence_transformers', label: 'Sentence Transformers', description: 'Local embedding models', count: 0 },
        { value: 'openai', label: 'OpenAI', description: 'OpenAI API service', count: 0 },
        { value: 'azure_openai', label: 'Azure OpenAI', description: 'Microsoft Azure OpenAI service', count: 0 }
      ]);
    }
  };

  const handleCreateProvider = () => {
    setEditingProvider(null);
    setFormData({
      name: '',
      type: '',
      provider: '',
      base_url: '',
      ai_model: '',
      ai_model_config: '{}',
      fallback_integration_id: '',
      active: true
    });
    setModalVisible(true);
  };

  const handleEditProvider = (provider: AIProvider) => {
    setEditingProvider(provider);
    setFormData({
      name: provider.name || '',
      type: provider.type || '',
      provider: provider.provider,
      base_url: provider.base_url || '',
      ai_model: provider.ai_model || '',
      ai_model_config: JSON.stringify(provider.ai_model_config || {}, null, 2),
      fallback_integration_id: provider.fallback_integration_id?.toString() || '',
      active: provider.active
    });
    setModalVisible(true);
  };

  const handleDeleteProvider = async (providerId: number) => {
    if (!window.confirm('Are you sure you want to delete this AI provider?')) {
      return;
    }
    
    try {
      await axios.delete(`/api/v1/ai-providers/${providerId}`);
      showMessage('success', 'AI provider deleted successfully');
      fetchProviders();
    } catch (error) {
      console.error('Error deleting AI provider:', error);
      showMessage('error', 'Failed to delete AI provider');
    }
  };

  const handleToggleActive = async (provider: AIProvider) => {
    try {
      const updatedProvider = {
        ...provider,
        active: !provider.active
      };

      await axios.put(`/api/v1/ai-providers/${provider.id}`, updatedProvider);
      showMessage('success', `AI provider ${provider.active ? 'paused' : 'resumed'} successfully`);
      fetchProviders();
    } catch (error) {
      console.error('Error toggling AI provider status:', error);
      showMessage('error', 'Failed to update AI provider status');
    }
  };

  const handleTestProvider = async (provider: AIProvider) => {
    try {
      setLoading(true);
      const response = await axios.post('/api/v1/ai-providers/test', {
        provider: provider.provider,
        base_url: provider.base_url,
        ai_model: provider.ai_model,
        ai_model_config: provider.ai_model_config,
      });
      
      if (response.data.success) {
        const testResult = response.data.test_result;
        const responseTime = testResult.response_time || 0;
        const status = testResult.status || 'unknown';
        const details = testResult.details || '';

        if (status === 'passed') {
          showMessage('success', `Test successful! Response time: ${responseTime}ms. ${details}`);
        } else {
          showMessage('error', `Test failed: ${testResult.error || 'Unknown error'}`);
        }
      } else {
        showMessage('error', `Test failed: ${response.data.error}`);
      }
    } catch (error) {
      console.error('Error testing AI provider:', error);
      showMessage('error', 'Failed to test AI provider');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    try {
      let parsedConfig = {};
      try {
        parsedConfig = JSON.parse(formData.ai_model_config);
      } catch (error) {
        showMessage('error', 'Invalid JSON in AI model configuration');
        return;
      }

      const payload = {
        name: formData.name,
        type: formData.type,
        provider: formData.provider,
        base_url: formData.base_url || null,
        ai_model: formData.ai_model || null,
        ai_model_config: parsedConfig,
        fallback_integration_id: formData.fallback_integration_id ? parseInt(formData.fallback_integration_id) : null,
        active: formData.active
      };

      if (editingProvider) {
        await axios.put(`/api/v1/ai-providers/${editingProvider.id}`, payload);
        showMessage('success', 'AI provider updated successfully');
      } else {
        await axios.post('/api/v1/ai-providers', payload);
        showMessage('success', 'AI provider created successfully');
      }
      
      setModalVisible(false);
      fetchProviders();
    } catch (error) {
      console.error('Error saving AI provider:', error);
      showMessage('error', 'Failed to save AI provider');
    }
  };

  const handleInputChange = (field: string, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
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
                <p className="text-secondary">You need administrator privileges to access AI configuration.</p>
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
                  <h1 className="text-3xl font-bold text-primary">
                    AI Configuration
                  </h1>
                  <p className="text-secondary">
                    Manage AI providers and models for your organization
                  </p>
                </div>
                <motion.button
                  className="btn-primary flex items-center space-x-2"
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={handleCreateProvider}
                >
                  <Plus className="w-4 h-4" />
                  <span>Add Provider</span>
                </motion.button>
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
              {message.type === 'success' && <Check className="w-4 h-4" />}
              {message.type === 'error' && <X className="w-4 h-4" />}
              {message.type === 'info' && <AlertCircle className="w-4 h-4" />}
              <span>{message.text}</span>
            </div>
          </motion.div>
        )}

        {/* Providers List */}
        <div className="card overflow-hidden">

          {loading ? (
            <div className="text-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-color-1 mx-auto"></div>
              <p className="text-secondary mt-2">Loading providers...</p>
            </div>
          ) : providers.length === 0 ? (
            <div className="text-center py-8">
              <Settings className="w-16 h-16 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-primary mb-2">No AI Providers</h3>
              <p className="text-secondary mb-4">Get started by adding your first AI provider</p>
              <button
                className="btn btn-primary"
                onClick={handleCreateProvider}
              >
                Add Provider
              </button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-border">
                <thead className="bg-muted">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-secondary uppercase tracking-wider">
                      Provider
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-secondary uppercase tracking-wider">
                      Model
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-secondary uppercase tracking-wider">
                      Base URL
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-secondary uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-secondary uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-primary divide-y divide-border">
                  {providers.map((provider) => (
                    <tr key={provider.id} className="hover:bg-muted">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-primary">{provider.name}</div>
                        <div className="text-sm text-secondary">{provider.provider}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-primary">{provider.ai_model || '-'}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-primary">
                          {provider.base_url ? (
                            <a href={provider.base_url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-700 transition-colors duration-150">
                              {provider.base_url}
                            </a>
                          ) : '-'}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                          provider.active
                            ? 'bg-green-100 text-green-800'
                            : 'bg-gray-100 text-gray-800'
                        }`}>
                          {provider.active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <div className="flex items-center justify-end space-x-2">
                          <button
                            onClick={() => handleTestProvider(provider)}
                            className="text-purple-600 hover:text-purple-700 transition-colors duration-150"
                            title="Test Provider"
                          >
                            <TestTube className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleEditProvider(provider)}
                            className="text-blue-600 hover:text-blue-700 transition-colors duration-150"
                            title="Edit Provider"
                          >
                            <Edit className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleToggleActive(provider)}
                            className={`${
                              provider.active
                                ? 'text-orange-600 hover:text-orange-700'
                                : 'text-green-600 hover:text-green-700'
                            } transition-colors duration-150`}
                            title={provider.active ? 'Pause Provider' : 'Resume Provider'}
                          >
                            {provider.active ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                          </button>
                          <button
                            onClick={() => handleDeleteProvider(provider.id)}
                            className="text-red-600 hover:text-red-700 transition-colors duration-150"
                            title="Delete Provider"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

          </motion.div>
        </main>
      </div>

      {/* Modal */}
      {modalVisible && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto"
          >
            <div className="flex items-center justify-between p-6 border-b border-gray-200">
              <h2 className="text-xl font-semibold text-primary">
                {editingProvider ? 'Edit AI Provider' : 'Add AI Provider'}
              </h2>
              <button
                type="button"
                onClick={() => setModalVisible(false)}
                className="text-secondary hover:text-primary transition-colors text-xl"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-primary mb-1">
                  Provider Name *
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => handleInputChange('name', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="e.g., Main OpenAI Provider"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-primary mb-1">
                  Type *
                </label>
                <select
                  value={formData.type}
                  onChange={(e) => handleInputChange('type', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  required
                >
                  <option value="">Select type</option>
                  <option value="data_source">Data Source</option>
                  <option value="ai_provider">AI Provider</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-primary mb-1">
                  Provider Type *
                </label>
                <select
                  value={formData.provider}
                  onChange={(e) => handleInputChange('provider', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  required
                >
                  <option value="">Select provider type</option>
                  {providerTypes.map((type) => (
                    <option key={type.value} value={type.value}>
                      {type.label}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-gray-500 mt-1">
                  {formData.provider && providerTypes.find(t => t.value === formData.provider)?.description}
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-primary mb-1">
                  Base URL
                </label>
                <input
                  type="url"
                  value={formData.base_url}
                  onChange={(e) => handleInputChange('base_url', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="https://api.example.com"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-primary mb-1">
                  AI Model *
                </label>
                {formData.provider === 'wex_gateway' ? (
                  <select
                    value={formData.ai_model}
                    onChange={(e) => handleInputChange('ai_model', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    required
                  >
                    <option value="">Select WEX Gateway model</option>
                    <optgroup label="🏆 Recommended">
                      <option value="bedrock-claude-sonnet-4-v1">Claude Sonnet 4 (Strategic Analysis)</option>
                      <option value="azure-gpt-4o-mini">GPT-4o Mini (Fast & Cost-Effective)</option>
                      <option value="azure-text-embedding-3-small">Text Embedding 3 Small (Semantic Search)</option>
                    </optgroup>
                    <optgroup label="💎 Premium">
                      <option value="bedrock-claude-opus-4-v1">Claude Opus 4 (Maximum Intelligence)</option>
                      <option value="azure-gpt-4o">GPT-4o (Enhanced Reasoning)</option>
                      <option value="azure-text-embedding-3-large">Text Embedding 3 Large (High Accuracy)</option>
                    </optgroup>
                    <optgroup label="🚀 Specialized">
                      <option value="azure-r1">DeepSeek R1 (Scientific Reasoning)</option>
                      <option value="bedrock-nova-pro-v1">Nova Pro (Multimodal)</option>
                      <option value="azure-textembedding-ada-002">Ada 002 (Legacy Embeddings)</option>
                    </optgroup>
                    <optgroup label="💰 Cost-Effective">
                      <option value="bedrock-claude-3-5-haiku-v1">Claude Haiku (Fast Response)</option>
                      <option value="bedrock-nova-lite-v1">Nova Lite (Efficient)</option>
                      <option value="bedrock-llama3-2-3b-instruct-v1">Llama 3.2 3B (Lightweight)</option>
                    </optgroup>
                  </select>
                ) : (
                  <input
                    type="text"
                    value={formData.ai_model}
                    onChange={(e) => handleInputChange('ai_model', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="e.g., all-mpnet-base-v2, gpt-4"
                    required
                  />
                )}
                <p className="text-xs text-gray-500 mt-1">
                  {formData.provider === 'wex_gateway'
                    ? 'Select from available WEX AI Gateway models'
                    : 'Enter the model name for your provider'}
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-primary mb-1">
                  Model Configuration (JSON)
                </label>
                <textarea
                  value={formData.ai_model_config}
                  onChange={(e) => handleInputChange('ai_model_config', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  rows={4}
                  placeholder='{"temperature": 0.7, "max_tokens": 1000}'
                />
              </div>

              {/* Fallback Provider - Only for AI integrations, not Embedding */}
              {formData.type === 'AI' && (
                <div>
                  <label className="block text-sm font-medium text-primary mb-1">
                    Fallback Provider
                  </label>
                  <select
                    value={formData.fallback_integration_id}
                    onChange={(e) => handleInputChange('fallback_integration_id', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value="">No fallback provider</option>
                    {providers
                      .filter(p => editingProvider ? p.id !== editingProvider.id : true)
                      .filter(p => p.active && p.type === 'AI')
                      .map((provider) => (
                        <option key={provider.id} value={provider.id}>
                          {provider.name} ({provider.provider})
                        </option>
                      ))}
                  </select>
                  <p className="text-xs text-gray-500 mt-1">
                    Optional fallback AI provider if this one fails
                  </p>
                </div>
              )}

              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="active"
                  checked={formData.active}
                  onChange={(e) => handleInputChange('active', e.target.checked)}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <label htmlFor="active" className="ml-2 block text-sm text-primary">
                  Active
                </label>
              </div>

              <div className="flex justify-end space-x-3 pt-4">
                <button
                  type="button"
                  onClick={() => setModalVisible(false)}
                  className="btn btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                >
                  {editingProvider ? 'Update' : 'Create'} Provider
                </button>
              </div>
            </form>
          </motion.div>
        </div>
      )}
    </div>
  );
};

export default AIConfigurationPage;
