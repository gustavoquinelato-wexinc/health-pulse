import React, { useState, useEffect } from 'react';
import { Loader2, Download, FileText, Save } from 'lucide-react';
import Header from '../components/Header';
import CollapsedSidebar from '../components/CollapsedSidebar';
import ToastContainer from '../components/ToastContainer';

import { useToast } from '../hooks/useToast';
import { customFieldsApi, integrationsApi } from '../services/etlApiService';
import {
  Integration,
  CustomField
} from '../types';

// Mapping state: maps custom_field_XX to custom_fields.id
interface FieldMappingState {
  [key: string]: number | null; // e.g., { "custom_field_01": 123, "custom_field_02": null, ... }
}

interface CustomFieldMappingPageProps {
  embedded?: boolean
}

const CustomFieldMappingPage: React.FC<CustomFieldMappingPageProps> = ({ embedded = false }) => {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [selectedIntegration, setSelectedIntegration] = useState<number | null>(null);
  const [customFields, setCustomFields] = useState<CustomField[]>([]);
  const [fieldMappings, setFieldMappings] = useState<FieldMappingState>({});

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
      loadCustomFields(jiraIntegration.id);
      loadMappingConfig(jiraIntegration.id);
    }
  }, [integrations]);

  // Load custom fields and mapping when integration is selected
  useEffect(() => {
    if (selectedIntegration) {
      loadCustomFields(selectedIntegration);
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

  const loadCustomFields = async (integrationId: number) => {
    try {
      const response = await customFieldsApi.listCustomFields(integrationId);
      const data = response.data;

      if (data.success) {
        setCustomFields(data.custom_fields || []);
      }
    } catch (error) {
      console.error('Failed to load custom fields:', error);
      showError('Load Failed', 'Failed to load custom fields from database');
    }
  };

  const loadMappingConfig = async (integrationId: number) => {
    try {
      setLoading(true);
      const response = await customFieldsApi.getMappingsTable(integrationId);
      const data = response.data;

      if (data.success) {
        setFieldMappings(data.mappings || {});
      }
    } catch (error) {
      console.error('Failed to load mapping config:', error);
      showError('Load Failed', 'Failed to load custom field mappings');
    } finally {
      setLoading(false);
    }
  };

  const saveMappingConfig = async () => {
    if (!selectedIntegration) return;

    try {
      setSaving(true);

      const response = await customFieldsApi.saveMappingsTable(selectedIntegration, fieldMappings);
      const data = response.data;

      if (data.success) {
        showSuccess('Save Successful', 'Custom field mappings saved successfully');
      } else {
        showError('Save Failed', data.message || 'Failed to save custom field mappings');
      }
    } catch (error: any) {
      console.error('Failed to save mapping config:', error);
      const errorMessage = error.response?.data?.detail || error.message || 'Failed to save custom field mappings';
      showError('Save Failed', errorMessage);
    } finally {
      setSaving(false);
    }
  };

  const updateFieldMapping = (fieldKey: string, customFieldId: number | null) => {
    setFieldMappings(prev => ({
      ...prev,
      [fieldKey]: customFieldId
    }));
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

        // Reload custom fields to show newly discovered fields
        await loadCustomFields(selectedIntegration);
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

  const content = (
    <>
            {/* Sync from Jira Button */}
            {!loading && selectedIntegration && (
              <div className="mb-6 flex justify-end">
                <button
                  onClick={syncCustomFields}
                  disabled={syncing}
                  className="px-4 py-2 rounded-lg text-white flex items-center space-x-2 transition-colors disabled:opacity-50"
                  style={{ background: 'var(--gradient-1-2)' }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.opacity = '0.9'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.opacity = '1'
                  }}
                  title="Sync custom fields from Jira using createmeta API"
                >
                  <Download className={`h-4 w-4 ${syncing ? 'animate-spin' : ''}`} />
                  <span>{syncing ? 'Syncing from Jira...' : 'Sync from Jira'}</span>
                </button>
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

            {/* Custom Field Mappings Table */}
            {selectedIntegration && !loading && (
              <div className="rounded-lg bg-table-container shadow-md overflow-hidden border border-gray-400">
                <div className="px-6 py-5 flex justify-between items-center bg-table-header">
                  <h2 className="text-lg font-semibold text-table-header">Custom Field Mappings</h2>
                  <button
                    onClick={saveMappingConfig}
                    disabled={saving}
                    className="px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2 font-medium shadow-sm disabled:opacity-50"
                  >
                    <Save className="h-4 w-4" />
                    <span>{saving ? 'Saving...' : 'Save Mappings'}</span>
                  </button>
                </div>

                {customFields.length === 0 ? (
                  <div className="text-center py-12">
                    <div className="flex justify-center mb-4">
                      <FileText className="h-16 w-16 text-secondary" />
                    </div>
                    <h3 className="text-xl font-semibold text-primary mb-2">
                      No Custom Fields Found
                    </h3>
                    <p className="text-secondary mb-4">
                      Click "Sync from Jira" above to discover custom fields from your Jira projects.
                    </p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="bg-table-column-header">
                          <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-table-column-header w-48">
                            Work Items Column
                          </th>
                          <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-table-column-header">
                            Jira Custom Field
                          </th>
                          <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-table-column-header w-32">
                            Field Type
                          </th>
                          <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-table-column-header w-40">
                            Jira Field ID
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {Array.from({ length: 20 }, (_, i) => i + 1).map((num, index) => {
                          const fieldKey = `custom_field_${num.toString().padStart(2, '0')}`;
                          const selectedFieldId = fieldMappings[fieldKey];
                          const selectedField = customFields.find(f => f.id === selectedFieldId);
                          const displayLabel = `Custom Field ${num.toString().padStart(2, '0')}`;

                          return (
                            <tr
                              key={fieldKey}
                              className={`${index % 2 === 0 ? 'bg-table-row-even' : 'bg-table-row-odd'} hover:bg-table-row-hover transition-colors`}
                            >
                              <td className="px-6 py-4 whitespace-nowrap">
                                <div className="flex items-center">
                                  <div className="flex-shrink-0 w-8 mr-3">
                                    <span className="text-sm font-medium text-secondary">{num.toString().padStart(2, '0')}</span>
                                  </div>
                                  <div className="text-sm font-medium text-primary">{displayLabel}</div>
                                </div>
                              </td>
                              <td className="px-6 py-4">
                                <select
                                  value={selectedFieldId || ''}
                                  onChange={(e) => updateFieldMapping(fieldKey, e.target.value ? parseInt(e.target.value) : null)}
                                  className="w-full px-3 py-2 border border-tertiary/20 rounded-lg bg-primary text-primary text-sm focus:ring-2 focus:ring-accent focus:border-accent transition-all"
                                >
                                  <option value="">-- Not Mapped --</option>
                                  {customFields.map((field) => (
                                    <option key={field.id} value={field.id}>
                                      {field.name}
                                    </option>
                                  ))}
                                </select>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap">
                                {selectedField ? (
                                  <span className="text-sm text-secondary">
                                    {selectedField.field_type}
                                  </span>
                                ) : (
                                  <span className="text-sm text-secondary">-</span>
                                )}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap">
                                {selectedField ? (
                                  <code className="text-xs text-secondary bg-tertiary/20 px-2 py-1 rounded">
                                    {selectedField.external_id}
                                  </code>
                                ) : (
                                  <span className="text-sm text-secondary">-</span>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

      {/* Toast Container - Always show, even in embedded mode */}
      <ToastContainer toasts={toasts} onRemoveToast={removeToast} />
    </>
  )

  if (embedded) {
    return content
  }

  return (
    <div className="min-h-screen">
      <Header />
      <div className="flex">
        <CollapsedSidebar />
        <main className="flex-1 ml-16 py-8">
          <div className="ml-12 mr-12">
            {content}
          </div>
        </main>
      </div>
    </div>
  );
};

export default CustomFieldMappingPage;
