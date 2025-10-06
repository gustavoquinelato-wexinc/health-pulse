import React, { useState, useEffect } from 'react';
import { Loader2, Sliders, Save, Database, Download } from 'lucide-react';
import Header from '../components/Header';
import CollapsedSidebar from '../components/CollapsedSidebar';
import ToastContainer from '../components/ToastContainer';

import { useToast } from '../hooks/useToast';
import { customFieldsApi, integrationsApi } from '../services/etlApiService';
import {
  Integration,
  CustomFieldMappingConfig,
  CustomFieldMapping,
  GetCustomFieldMappingResponse
} from '../types';

const CustomFieldMappingPage: React.FC = () => {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [selectedIntegration, setSelectedIntegration] = useState<number | null>(null);
  const [mappingConfig, setMappingConfig] = useState<CustomFieldMappingConfig | null>(null);
  const [availableColumns, setAvailableColumns] = useState<string[]>([]);

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const { toasts, removeToast, showSuccess, showError } = useToast();

  // Load integrations on component mount
  useEffect(() => {
    loadIntegrations();
  }, []);

  // Auto-select first Jira integration when integrations are loaded
  useEffect(() => {
    if (integrations.length > 0 && !selectedIntegration) {
      const jiraIntegration = integrations[0]; // Should be Jira since we filter for it
      setSelectedIntegration(jiraIntegration.id);
      loadMappingConfig(jiraIntegration.id);
    }
  }, [integrations]);

  // Load mapping config when integration is selected
  useEffect(() => {
    if (selectedIntegration) {
      loadMappingConfig(selectedIntegration);
    }
  }, [selectedIntegration]);

  const loadIntegrations = async () => {
    try {
      setLoading(true);
      const response = await integrationsApi.getIntegrations();
      const jiraIntegrations = response.data.filter((integration: Integration) =>
        integration.name?.toLowerCase() === 'jira' && integration.integration_type?.toLowerCase() === 'data'
      );
      setIntegrations(jiraIntegrations);
    } catch (error) {
      console.error('Failed to load integrations:', error);
      showError('Load Failed', 'Failed to load integrations');
    } finally {
      setLoading(false);
    }
  };

  const loadMappingConfig = async (integrationId: number) => {
    try {
      setLoading(true);
      const response = await customFieldsApi.getMappings(integrationId);
      const data: GetCustomFieldMappingResponse = response.data;
      
      setAvailableColumns(data.available_columns);
      
      // Convert the mapping data to our config format
      const mappings: CustomFieldMapping[] = Object.entries(data.custom_field_mappings || {}).map(([jiraFieldId, config]: [string, any]) => ({
        jira_field_id: jiraFieldId,
        jira_field_name: config.field_name || jiraFieldId,
        mapped_column: config.mapped_column,
        is_active: config.is_active !== false
      }));

      setMappingConfig({
        project_id: 0, // Will be set when we add project selection
        integration_id: integrationId,
        mappings,
        last_updated: new Date().toISOString()
      });
    } catch (error) {
      console.error('Failed to load mapping config:', error);
      showError('Load Failed', 'Failed to load custom field mappings');
    } finally {
      setLoading(false);
    }
  };

  const saveMappingConfig = async () => {
    if (!selectedIntegration || !mappingConfig) return;

    try {
      setSaving(true);

      // Convert mappings back to the API format
      const customFieldMappings = mappingConfig.mappings.reduce((acc, mapping) => {
        acc[mapping.jira_field_id] = {
          field_name: mapping.jira_field_name,
          mapped_column: mapping.mapped_column,
          is_active: mapping.is_active
        };
        return acc;
      }, {} as Record<string, any>);

      await customFieldsApi.saveMappings(selectedIntegration, customFieldMappings);

      showSuccess('Save Successful', 'Custom field mappings saved successfully');
    } catch (error) {
      console.error('Failed to save mapping config:', error);
      showError('Save Failed', 'Failed to save custom field mappings');
    } finally {
      setSaving(false);
    }
  };

  const syncCustomFields = async () => {
    if (!selectedIntegration) return;

    try {
      setSyncing(true);

      // Show initial feedback
      showSuccess('Sync Started', 'Requesting custom fields data from Jira...');

      const response = await customFieldsApi.syncCustomFields(selectedIntegration);
      const data = response.data;

      if (data.success) {
        showSuccess(
          'Sync Completed',
          data.message || `Custom fields sync completed successfully. Discovered ${data.discovered_fields_count || 0} fields.`
        );

        // Reload the mapping config to show any newly discovered fields
        await loadMappingConfig(selectedIntegration);
      } else {
        showError('Sync Failed', data.message || 'Custom fields sync failed');
      }

    } catch (error: any) {
      console.error('Failed to sync custom fields:', error);
      console.error('Error response:', error.response);
      console.error('Error status:', error.response?.status);
      console.error('Error data:', error.response?.data);

      const errorMessage = error.response?.data?.detail || error.message || 'Failed to sync custom fields from Jira';
      showError('Sync Failed', errorMessage);
    } finally {
      setSyncing(false);
    }
  };

  const updateMapping = (index: number, field: keyof CustomFieldMapping, value: any) => {
    if (!mappingConfig) return;

    const updatedMappings = [...mappingConfig.mappings];
    updatedMappings[index] = { ...updatedMappings[index], [field]: value };
    
    setMappingConfig({
      ...mappingConfig,
      mappings: updatedMappings,
      last_updated: new Date().toISOString()
    });
  };

  const addNewMapping = () => {
    if (!mappingConfig) return;

    const newMapping: CustomFieldMapping = {
      jira_field_id: '',
      jira_field_name: '',
      mapped_column: undefined,
      is_active: true
    };

    setMappingConfig({
      ...mappingConfig,
      mappings: [...mappingConfig.mappings, newMapping],
      last_updated: new Date().toISOString()
    });
  };

  const removeMapping = (index: number) => {
    if (!mappingConfig) return;

    const updatedMappings = mappingConfig.mappings.filter((_, i) => i !== index);
    setMappingConfig({
      ...mappingConfig,
      mappings: updatedMappings,
      last_updated: new Date().toISOString()
    });
  };

  const getAvailableColumnsForMapping = (currentColumn?: string) => {
    const usedColumns = mappingConfig?.mappings
      .filter(m => m.mapped_column && m.mapped_column !== currentColumn)
      .map(m => m.mapped_column) || [];
    
    return availableColumns.filter(col => !usedColumns.includes(col));
  };

  return (
    <div className="min-h-screen">
      <Header />
      <div className="flex">
        <CollapsedSidebar />
        <main className="flex-1 ml-16 py-8">
          <div className="ml-12 mr-12">
            {/* Page Header */}
            <div className="mb-8">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h1 className="text-3xl font-bold text-primary">
                    Custom Fields
                  </h1>
                  <p className="text-lg text-secondary">
                    Configure how Jira custom fields map to work_items table columns. Use the Sync button to discover custom fields from Jira using the createmeta API.
                  </p>
                </div>
              </div>
            </div>

            {/* Jira Integration Info Card */}
            {selectedIntegration && (
              <div className="mb-6 p-6 rounded-lg shadow-md border border-transparent bg-secondary"
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = 'var(--color-1)'
                  e.currentTarget.style.boxShadow = '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'transparent'
                  e.currentTarget.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
                }}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center">
                      <Sliders className="h-5 w-5 text-accent" />
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold text-primary">Jira Custom Fields Configuration</h3>
                      <p className="text-sm text-secondary">
                        {integrations.find(i => i.id === selectedIntegration)?.base_url || 'Jira Integration'}
                      </p>
                    </div>
                  </div>

                  <button
                    onClick={syncCustomFields}
                    disabled={syncing || loading}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2 disabled:opacity-50"
                    title="Sync custom fields from Jira using createmeta API"
                  >
                    <Download className={`h-4 w-4 ${syncing ? 'animate-spin' : ''}`} />
                    <span>{syncing ? 'Syncing from Jira...' : 'Sync from Jira'}</span>
                  </button>
                </div>
              </div>
            )}

            {/* Available Custom Field Columns */}
            {selectedIntegration && !loading && (
              <div className="mb-6 p-6 rounded-lg shadow-md border border-transparent bg-secondary"
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = 'var(--color-1)'
                  e.currentTarget.style.boxShadow = '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'transparent'
                  e.currentTarget.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
                }}
              >
                <div className="flex items-center space-x-3 mb-4">
                  <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center">
                    <Database className="h-5 w-5 text-accent" />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-primary">Available Database Columns</h3>
                    <p className="text-sm text-secondary">20 dedicated custom field columns plus JSON overflow</p>
                  </div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3">
                  {availableColumns.filter(col => col !== 'overflow').map((column) => (
                    <div key={column} className="px-3 py-2 bg-accent/5 rounded-lg border border-accent/20">
                      <span className="text-sm font-medium text-primary">{column}</span>
                    </div>
                  ))}
                  <div className="px-3 py-2 bg-yellow-50 rounded-lg border border-yellow-200">
                    <span className="text-sm font-medium text-yellow-800">JSON Overflow</span>
                  </div>
                </div>
              </div>
            )}

            {/* Loading State */}
            {loading && (
              <div className="bg-secondary rounded-lg shadow-sm p-6">
                <div className="text-center py-12">
                  <Loader2 className="h-12 w-12 animate-spin mx-auto mb-4 text-primary" />
                  <h2 className="text-2xl font-semibold text-primary mb-2">
                    Loading...
                  </h2>
                  <p className="text-secondary">
                    Fetching custom field mappings
                  </p>
                </div>
              </div>
            )}

            {/* No Jira Integration Found */}
            {!loading && integrations.length === 0 && (
              <div className="bg-secondary rounded-lg shadow-sm p-6">
                <div className="text-center py-12">
                  <div className="text-6xl mb-4">🔍</div>
                  <h2 className="text-2xl font-semibold text-primary mb-2">
                    No Jira Integration Found
                  </h2>
                  <p className="text-secondary mb-6">
                    Custom field mapping requires an active Jira integration. Please configure a Jira integration first.
                  </p>
                  <button
                    onClick={() => window.location.href = '/integrations'}
                    className="px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
                  >
                    Configure Integrations
                  </button>
                </div>
              </div>
            )}

            {/* Mapping Configuration */}
            {selectedIntegration && mappingConfig && !loading && (
              <div className="rounded-lg bg-table-container shadow-md overflow-hidden border border-transparent"
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = 'var(--color-1)'
                  e.currentTarget.style.boxShadow = '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'transparent'
                  e.currentTarget.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
                }}
              >
                <div className="px-6 py-5 flex justify-between items-center bg-table-header">
                  <h2 className="text-lg font-semibold text-table-header">Custom Field Mappings</h2>
                  <div className="flex gap-2">
                    <button
                      onClick={addNewMapping}
                      className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2 font-medium shadow-sm"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M5 12h14"></path>
                        <path d="M12 5v14"></path>
                      </svg>
                      <span>Add Mapping</span>
                    </button>
                    <button
                      onClick={saveMappingConfig}
                      disabled={saving}
                      className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center space-x-2 font-medium shadow-sm disabled:opacity-50"
                    >
                      <Save className="h-4 w-4" />
                      <span>{saving ? 'Saving...' : 'Save Changes'}</span>
                    </button>
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="bg-table-column-header">
                        <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-table-column-header">
                          Jira Field ID
                        </th>
                        <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-table-column-header">
                          Field Name
                        </th>
                        <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-table-column-header">
                          Mapped Column
                        </th>
                        <th className="px-6 py-4 text-center text-xs font-semibold uppercase tracking-wider text-table-column-header">
                          Active
                        </th>
                        <th className="px-6 py-4 text-center text-xs font-semibold uppercase tracking-wider text-table-column-header">
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {mappingConfig.mappings.map((mapping, index) => (
                        <tr
                          key={index}
                          className={`${index % 2 === 0 ? 'bg-table-row-even' : 'bg-table-row-odd'}`}
                        >
                          <td className="px-6 py-5 whitespace-nowrap text-sm text-table-row">
                            <input
                              type="text"
                              value={mapping.jira_field_id}
                              onChange={(e) => updateMapping(index, 'jira_field_id', e.target.value)}
                              className="w-full px-3 py-2 border border-tertiary/20 rounded-lg bg-primary text-primary"
                              placeholder="customfield_10001"
                            />
                          </td>
                          <td className="px-6 py-5 whitespace-nowrap text-sm text-table-row">
                            <input
                              type="text"
                              value={mapping.jira_field_name}
                              onChange={(e) => updateMapping(index, 'jira_field_name', e.target.value)}
                              className="w-full px-3 py-2 border border-tertiary/20 rounded-lg bg-primary text-primary"
                              placeholder="Field Name"
                            />
                          </td>
                          <td className="px-6 py-5 whitespace-nowrap text-sm text-table-row">
                            <select
                              value={mapping.mapped_column || ''}
                              onChange={(e) => updateMapping(index, 'mapped_column', e.target.value || undefined)}
                              className="w-full px-3 py-2 border border-tertiary/20 rounded-lg bg-primary text-primary"
                            >
                              <option value="">Select column...</option>
                              <option value="overflow">JSON Overflow</option>
                              {getAvailableColumnsForMapping(mapping.mapped_column).map((column) => (
                                <option key={column} value={column}>
                                  {column}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td className="px-6 py-5 whitespace-nowrap text-center">
                            <input
                              type="checkbox"
                              checked={mapping.is_active}
                              onChange={(e) => updateMapping(index, 'is_active', e.target.checked)}
                              className="h-4 w-4 text-accent focus:ring-accent border-tertiary/20 rounded"
                            />
                          </td>
                          <td className="px-6 py-5 whitespace-nowrap text-center">
                            <button
                              onClick={() => removeMapping(index)}
                              className="text-red-600 hover:text-red-800 text-sm font-medium px-3 py-1 rounded-md hover:bg-red-50 transition-colors"
                            >
                              Remove
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {mappingConfig.mappings.length === 0 && (
                  <div className="text-center py-12">
                    <div className="text-6xl mb-4">⚙️</div>
                    <h3 className="text-xl font-semibold text-primary mb-2">
                      No Mappings Configured
                    </h3>
                    <p className="text-secondary">
                      No custom field mappings configured. Click "Add Mapping" to get started.
                    </p>
                  </div>
                )}
              </div>
            )}


          </div>
        </main>
      </div>

      {/* Toast Container */}
      <ToastContainer toasts={toasts} onRemoveToast={removeToast} />
    </div>
  );
};

export default CustomFieldMappingPage;
