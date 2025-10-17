import React, { useState, useEffect, useMemo, useRef } from 'react';
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
    if (!searchQuery.trim()) {
      return options;
    }

    const query = searchQuery.toLowerCase();
    return options.filter(field =>
      field.name.toLowerCase().includes(query) ||
      field.external_id.toLowerCase().includes(query)
    );
  }, [options, searchQuery]);

  // Handle null/undefined/empty string values properly
  const numericValue = value && value !== '' ? Number(value) : null;
  const selectedOption = numericValue ? options.find(f => f.id === numericValue) : null;

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
  const [originalMappings, setOriginalMappings] = useState<FieldMappingState>({});

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [forceRender, setForceRender] = useState(0);
  const syncCompletedRef = useRef(false);
  const { toasts, removeToast, showSuccess, showError } = useToast();

  // Check if there are unsaved changes
  const hasUnsavedChanges = JSON.stringify(fieldMappings) !== JSON.stringify(originalMappings);

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

  const loadMappingConfig = async (integrationId: number, skipLoadingState: boolean = false) => {
    try {
      if (!skipLoadingState) {
        setLoading(true);
      }
      const response = await customFieldsApi.getMappingsTable(integrationId);
      const data = response.data;

      if (data.success) {
        setFieldMappings(data.mappings || {});
        setOriginalMappings(data.mappings || {}); // Store original for comparison
      }
    } catch (error) {
      console.error('Failed to load mapping config:', error);
      showError('Load Failed', 'Failed to load custom field mappings');
    } finally {
      if (!skipLoadingState) {
        setLoading(false);
      }
    }
  };

  const saveMappingConfig = async () => {
    if (!selectedIntegration) return;

    try {
      setSaving(true);

      const response = await customFieldsApi.saveMappingsTable(selectedIntegration, fieldMappings);
      const data = response.data;

      if (data.success) {
        setOriginalMappings(fieldMappings); // Update original after successful save
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
      syncCompletedRef.current = false; // Reset completion flag

      const response = await customFieldsApi.syncCustomFields(selectedIntegration);
      const data = response.data;

      if (data.success) {
        // Don't show success message here - wait for polling to complete
        // Poll for transform worker completion and reload
        // DON'T stop syncing here - keep button spinning until polling completes
        pollForTransformCompletion();
      } else {
        showError('Queue Failed', data.message || 'Custom fields extraction & transform failed');
        setSyncing(false); // Only stop spinning on error
      }

    } catch (error: any) {
      console.error('Failed to sync custom fields:', error);
      const errorMessage = error.response?.data?.detail || error.message || 'Failed to queue custom fields for extraction & transform';
      showError('Queue Failed', errorMessage);
      setSyncing(false); // Only stop spinning on error
    }
  };

  const pollForTransformCompletion = () => {
    if (!selectedIntegration) return;

    // Poll every 1 second for up to 30 seconds
    let pollCount = 0;
    const maxPolls = 30;

    const pollInterval = setInterval(async () => {
      pollCount++;

      try {
        // Check if transform worker has completed processing
        const statusResponse = await customFieldsApi.getSyncStatus(selectedIntegration);
        const statusData = statusResponse.data;

        if (statusData.success && statusData.processing_complete) {
          // Only process if we haven't already completed
          if (syncCompletedRef.current) {
            return; // Already processed, skip
          }

          // Mark as completed immediately to prevent duplicate processing
          syncCompletedRef.current = true;
          clearInterval(pollInterval);

          // Transform worker has completed - completely reload the page data
          try {

            // Reload custom fields from scratch
            await loadCustomFields(selectedIntegration);

            // Reload mappings from scratch
            await loadMappingConfig(selectedIntegration);

            // Force a complete re-render
            setForceRender(prev => prev + 1);

            // Show success message and stop spinning
            // Use a small delay to ensure state has updated, then get the current count
            setTimeout(() => {
              setSyncing(false); // Stop button spinning when everything is complete
              const currentCount = customFields.length;
              showSuccess('Queue Complete', `Custom fields extraction & transform completed successfully (${currentCount} fields total)`);
            }, 500);

          } catch (error) {
            console.error('Error reloading data after sync:', error);
            setSyncing(false); // Stop spinning on error
            showError('Error', 'Failed to reload data after sync');
          }
        }

        // Stop polling after max attempts
        if (pollCount >= maxPolls) {
          console.warn('⚠️ Polling timeout - transform worker may still be processing');
          clearInterval(pollInterval);
          setSyncing(false); // Stop spinning on timeout
          showError('Timeout', 'Transform worker is taking longer than expected. Please refresh the page in a moment.');
        }
      } catch (error) {
        console.error('Error polling for sync status:', error);
        clearInterval(pollInterval);
        setSyncing(false); // Stop spinning on error
      }
    }, 1000);
  };

  const content = (
    <div key={`custom-fields-${forceRender}`}>
            {/* Queue for Extraction & Transform Button */}
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
                  title="Queue custom fields for extraction and transform from Jira using createmeta API"
                >
                  {syncing ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
                      <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
                      <line x1="12" y1="22.08" x2="12" y2="12"></line>
                    </svg>
                  )}
                  <span>{syncing ? 'Queueing...' : 'Queue for Extraction & Transform'}</span>
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
                    disabled={saving || !hasUnsavedChanges}
                    className="px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2 font-medium shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
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
                      Click "Queue for Extraction & Transform" above to discover custom fields from your Jira projects.
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
                        {/* Development Field Section - First (right below header) */}
                        <tr>
                          <td colSpan={4} className="px-6 py-3 bg-development-divider">
                            <div className="flex items-center">
                              <div className="flex-grow border-t border-development-border"></div>
                              <span className="px-4 text-xs font-semibold text-development-text uppercase tracking-wider">
                                Development Field (Auto-selected)
                              </span>
                              <div className="flex-grow border-t border-development-border"></div>
                            </div>
                          </td>
                        </tr>

                        {/* Development Field Row */}
                        {(() => {
                          const selectedFieldId = fieldMappings['development_field'];
                          const selectedField = customFields.find(f => f.id === selectedFieldId);

                          return (
                            <tr className="bg-development-row">
                              <td className="px-6 py-4 whitespace-nowrap">
                                <div className="text-sm font-bold text-development-label">DEVELOPMENT</div>
                              </td>
                              <td className="px-6 py-4">
                                <SearchableSelect
                                  value={selectedFieldId || ''}
                                  onChange={(value) => {
                                    setFieldMappings(prev => ({
                                      ...prev,
                                      development_field: value ? parseInt(value) : null
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
                        })()}

                        {/* Team Fields Section - Second */}
                        <tr>
                          <td colSpan={4} className="px-6 py-3 bg-team-divider">
                            <div className="flex items-center">
                              <div className="flex-grow border-t border-team-border"></div>
                              <span className="px-4 text-xs font-semibold text-team-text uppercase tracking-wider">
                                Team Fields
                              </span>
                              <div className="flex-grow border-t border-team-border"></div>
                            </div>
                          </td>
                        </tr>

                        {/* Team Fields - Team and Story Points */}
                        {[
                          { key: 'team_field', label: 'TEAM' },
                          { key: 'story_points_field', label: 'STORY POINTS' }
                        ].map((specialField, index) => {
                          const selectedFieldId = fieldMappings[specialField.key];
                          const selectedField = customFields.find(f => f.id === selectedFieldId);

                          return (
                            <tr key={specialField.key} className={index % 2 === 0 ? 'bg-team-row-even' : 'bg-team-row-odd'}>
                              <td className="px-6 py-4 whitespace-nowrap">
                                <div className="text-sm font-bold text-team-label">{specialField.label}</div>
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

                        {/* Custom Fields Section - Third */}
                        <tr>
                          <td colSpan={4} className="px-6 py-3 bg-custom-divider">
                            <div className="flex items-center">
                              <div className="flex-grow border-t border-custom-border"></div>
                              <span className="px-4 text-xs font-semibold text-custom-text uppercase tracking-wider">
                                Custom Fields (20 Available)
                              </span>
                              <div className="flex-grow border-t border-custom-border"></div>
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
                              className={`${index % 2 === 0 ? 'bg-custom-row-even' : 'bg-custom-row-odd'} hover:bg-table-row-hover transition-colors`}
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
    </div>
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
