import React, { useState, useEffect, useMemo } from 'react';
import { Loader2, Download, FileText, Save, Search } from 'lucide-react';
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

// Searchable Select Component
interface SearchableSelectProps {
  value: string | number;
  onChange: (value: string) => void;
  options: CustomField[];
  placeholder: string;
}

const SearchableSelect: React.FC<SearchableSelectProps> = ({ value, onChange, options, placeholder }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);

  const filteredOptions = useMemo(() => {
    if (!searchQuery.trim()) return options;

    const query = searchQuery.toLowerCase();
    return options.filter(field =>
      field.name.toLowerCase().includes(query) ||
      field.external_id.toLowerCase().includes(query)
    );
  }, [options, searchQuery]);

  const selectedOption = options.find(f => f.id === Number(value));

  // Reset search when closing
  const handleClose = () => {
    setIsOpen(false);
    setSearchQuery('');
  };

  return (
    <div className="relative">
      {/* Display button showing current selection */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-3 py-2 border border-tertiary/20 rounded-lg bg-primary text-primary text-sm focus:ring-2 focus:ring-accent focus:border-accent transition-all text-left flex items-center justify-between"
      >
        <span className={selectedOption ? '' : 'text-secondary'}>
          {selectedOption ? `${selectedOption.name} (${selectedOption.external_id})` : placeholder}
        </span>
        <svg className="w-4 h-4 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <>
          {/* Backdrop to close dropdown */}
          <div
            className="fixed inset-0 z-10"
            onClick={handleClose}
          />

          {/* Dropdown */}
          <div className="absolute z-20 w-full mt-1 bg-white border border-gray-300 rounded-lg shadow-lg">
            <div className="p-2 border-b border-gray-200">
              <div className="relative">
                <Search className="absolute left-2 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search by name or ID..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  onClick={(e) => e.stopPropagation()}
                  autoFocus
                />
              </div>
            </div>
            <div className="max-h-60 overflow-y-auto">
              <div
                className="px-3 py-2 hover:bg-gray-100 cursor-pointer text-sm"
                onClick={() => {
                  onChange('');
                  handleClose();
                }}
              >
                {placeholder}
              </div>
              {filteredOptions.map((field) => (
                <div
                  key={field.id}
                  className={`px-3 py-2 hover:bg-gray-100 cursor-pointer text-sm ${
                    field.id === Number(value) ? 'bg-blue-50' : ''
                  }`}
                  onClick={() => {
                    onChange(String(field.id));
                    handleClose();
                  }}
                >
                  <div className="font-medium">
                    {field.name} <span className="text-xs text-gray-500">({field.external_id})</span>
                  </div>
                </div>
              ))}
              {filteredOptions.length === 0 && (
                <div className="px-3 py-2 text-sm text-gray-500 text-center">
                  No fields found
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

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

        // Poll for transform worker completion and reload
        pollForTransformCompletion();
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

  const pollForTransformCompletion = () => {
    if (!selectedIntegration) return;

    // Poll every 2 seconds for up to 30 seconds
    let pollCount = 0;
    const maxPolls = 15;

    const pollInterval = setInterval(async () => {
      pollCount++;

      try {
        // Reload custom fields to check if new fields appeared
        const response = await customFieldsApi.listCustomFields(selectedIntegration);
        const data = response.data;

        if (data.success && data.custom_fields) {
          const newFieldsCount = data.custom_fields.length;
          const currentFieldsCount = customFields.length;

          // If we have new fields, reload and stop polling
          if (newFieldsCount > currentFieldsCount) {
            setCustomFields(data.custom_fields);
            clearInterval(pollInterval);
            showSuccess('Fields Updated', `${newFieldsCount - currentFieldsCount} new custom fields discovered`);
          }
        }

        // Stop polling after max attempts
        if (pollCount >= maxPolls) {
          clearInterval(pollInterval);
        }
      } catch (error) {
        console.error('Error polling for custom fields:', error);
        clearInterval(pollInterval);
      }
    }, 2000);
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
                        {/* Special Fields Section */}
                        {[
                          { key: 'team_field', label: 'TEAM' },
                          { key: 'development_field', label: 'DEVELOPMENT' },
                          { key: 'story_points_field', label: 'STORY POINTS' }
                        ].map((specialField, index) => {
                          const selectedFieldId = fieldMappings[specialField.key];
                          const selectedField = customFields.find(f => f.id === selectedFieldId);

                          return (
                            <tr key={specialField.key} className={index % 2 === 0 ? 'bg-table-row-even' : 'bg-table-row-odd'}>
                              <td className="px-6 py-4 whitespace-nowrap">
                                <div className="text-sm font-bold" style={{ color: 'var(--table-column-header)' }}>{specialField.label}</div>
                              </td>
                              <td className="px-6 py-4">
                                <SearchableSelect
                                  value={selectedFieldId || ''}
                                  onChange={(value) => {
                                    setFieldMappings(prev => ({
                                      ...prev,
                                      [specialField.key]: value ? parseInt(value) : null
                                    }));
                                  }}
                                  options={customFields}
                                  placeholder="-- Not Mapped --"
                                />
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-secondary">
                                {selectedField?.field_type || '-'}
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

                        {/* Divider Row */}
                        <tr>
                          <td colSpan={4} className="px-6 py-3 bg-gray-100">
                            <div className="flex items-center">
                              <div className="flex-grow border-t border-gray-400"></div>
                              <span className="px-4 text-xs font-semibold text-gray-600 uppercase tracking-wider">
                                Custom Fields (20 Available)
                              </span>
                              <div className="flex-grow border-t border-gray-400"></div>
                            </div>
                          </td>
                        </tr>

                        {/* Regular Custom Fields Section */}
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
                                <SearchableSelect
                                  value={selectedFieldId || ''}
                                  onChange={(value) => updateFieldMapping(fieldKey, value ? parseInt(value) : null)}
                                  options={customFields}
                                  placeholder="-- Not Mapped --"
                                />
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
