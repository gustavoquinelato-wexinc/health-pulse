import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001'

// Create axios instance with default config
const etlApi = axios.create({
  baseURL: `${API_BASE_URL}/app/etl`,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add request interceptor to include hybrid authentication
etlApi.interceptors.request.use(
  (config) => {
    // For ETL job operations: use service-to-service authentication
    // For UI pages (mappings, configs): use user JWT tokens
    const internalSecret = import.meta.env.VITE_ETL_INTERNAL_SECRET || 'dev-internal-secret-change'
    config.headers['X-Internal-Auth'] = internalSecret

    // Also include user token for UI operations (mappings, configurations, etc.)
    const token = localStorage.getItem('pulse_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }

    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor for error handling with token refresh
etlApi.interceptors.response.use(
  (response) => response,
  async (error) => {
    // Handle 401 Unauthorized - logout immediately (auth service handles token refresh)
    if (error.response?.status === 401) {
      console.warn('Authentication failed - redirecting to login')
      localStorage.removeItem('pulse_token')
      window.location.href = '/login'
    }

    // For 400 errors (business logic validation), don't log to console
    // The error will be handled by the calling code with user-friendly toast messages
    if (error.response?.status === 400) {
      // Silently pass the error to the caller without console logging
      return Promise.reject(error)
    }

    // For other errors (500, 404, etc.), reject normally
    return Promise.reject(error)
  }
)





// Work Item Types API
export const witsApi = {
  getWits: async () => {
    return await etlApi.get('/wits')
  },
  getWitMappings: async () => {
    return await etlApi.get('/wit-mappings')
  },
  getWitsHierarchies: async () => {
    return await etlApi.get('/wits-hierarchies')
  },
  createWitHierarchy: async (data: any) => {
    return await etlApi.post('/wits-hierarchies', data)
  },
  updateWitHierarchy: async (hierarchyId: number, data: any) => {
    return await etlApi.put(`/wits-hierarchies/${hierarchyId}`, data)
  },
  createWitMapping: async (data: any) => {
    return await etlApi.post('/wit-mappings', data)
  },
  updateWitMapping: async (mappingId: number, data: any) => {
    return await etlApi.put(`/wit-mappings/${mappingId}`, data)
  },
  deleteWitMapping: async (mappingId: number) => {
    return await etlApi.delete(`/wit-mappings/${mappingId}`)
  },
}

// Status Mappings API
export const statusesApi = {
  getStatuses: async () => {
    return await etlApi.get('/statuses')
  },
  getStatusMappings: async () => {
    return await etlApi.get('/status-mappings')
  },
  getWorkflows: async () => {
    return await etlApi.get('/workflows')
  },
  createStatusMapping: async (data: any) => {
    return await etlApi.post('/status-mappings', data)
  },
  updateStatusMapping: async (mappingId: number, data: any) => {
    return await etlApi.put(`/status-mappings/${mappingId}`, data)
  },
  createWorkflow: async (data: any) => {
    return await etlApi.post('/workflows', data)
  },
  updateWorkflow: async (workflowId: number, data: any) => {
    return await etlApi.put(`/workflows/${workflowId}`, data)
  },
  deleteStatusMapping: async (mappingId: number) => {
    return await etlApi.delete(`/status-mappings/${mappingId}`)
  },
  deleteWorkflow: async (workflowId: number) => {
    return await etlApi.delete(`/workflows/${workflowId}`)
  },
}

// Integrations API
export const integrationsApi = {
  getIntegrations: async () => {
    return await etlApi.get('/integrations')
  },
  getIntegration: async (integrationId: number) => {
    return await etlApi.get(`/integrations/${integrationId}`)
  },
  createIntegration: async (data: any) => {
    return await etlApi.post('/integrations', data)
  },
  updateIntegration: async (integrationId: number, data: any) => {
    return await etlApi.put(`/integrations/${integrationId}`, data)
  },
  deleteIntegration: async (integrationId: number) => {
    return await etlApi.delete(`/integrations/${integrationId}`)
  },
  uploadLogo: async (file: File) => {
    const formData = new FormData()
    formData.append('logo', file)
    return await etlApi.post('/integrations/upload-logo', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
  },
}

// Qdrant API
export const qdrantApi = {
  getDashboard: async () => {
    return await etlApi.get('/qdrant/dashboard')
  },
  getHealth: async () => {
    return await etlApi.get('/qdrant/health')
  },
  createAllCollections: async () => {
    return await etlApi.post('/qdrant/collections/create-all')
  },
}

// Projects API
export const projectsApi = {
  getProjects: async (integrationId?: number) => {
    const params = integrationId ? `?integration_id=${integrationId}` : '';
    return await etlApi.get(`/projects${params}`);
  },
  getProject: async (projectId: number) => {
    return await etlApi.get(`/projects/${projectId}`);
  }
}

// Custom Fields API (Phase 2.1)
export const customFieldsApi = {
  // Get list of custom fields from database for an integration
  listCustomFields: async (integrationId: number) => {
    return await etlApi.get(`/custom-fields/list/${integrationId}`)
  },

  // Get custom field mappings from custom_fields_mapping table
  getMappingsTable: async (integrationId: number) => {
    return await etlApi.get(`/custom-fields/mappings-table/${integrationId}`)
  },

  // Save custom field mappings to custom_fields_mapping table
  saveMappingsTable: async (integrationId: number, mappings: Record<string, number | null>) => {
    return await etlApi.put(`/custom-fields/mappings-table/${integrationId}`, {
      mappings
    })
  },

  // Get custom field mappings for an integration (legacy - from integration.custom_field_mappings)
  getMappings: async (integrationId: number) => {
    return await etlApi.get(`/custom-fields/mappings/${integrationId}`)
  },

  // Save custom field mappings for an integration (legacy - to integration.custom_field_mappings)
  saveMappings: async (integrationId: number, mappings: Record<string, any>) => {
    return await etlApi.put(`/custom-fields/mappings/${integrationId}`, {
      custom_field_mappings: mappings
    })
  },

  // Sync custom fields from Jira using createmeta API
  syncCustomFields: async (integrationId: number) => {
    return await etlApi.post(`/custom-fields/sync/${integrationId}`)
  },

  // Check sync status (whether transform worker has completed processing)
  getSyncStatus: async (integrationId: number) => {
    return await etlApi.get(`/custom-fields/sync-status/${integrationId}`)
  },
}

// Jobs API
export const jobsApi = {
  getJobs: async (tenantId: number) => {
    return await etlApi.get(`/jobs?tenant_id=${tenantId}`)
  },
  getJobDetails: async (jobId: number, tenantId: number) => {
    return await etlApi.get(`/jobs/${jobId}?tenant_id=${tenantId}`)
  },
  toggleJobActive: async (jobId: number, tenantId: number, active: boolean) => {
    return await etlApi.post(`/jobs/${jobId}/toggle-active?tenant_id=${tenantId}`, { active })
  },
  runJobNow: async (jobId: number, tenantId: number) => {
    return await etlApi.post(`/jobs/${jobId}/run-now?tenant_id=${tenantId}`)
  },
  updateJobSettings: async (jobId: number, tenantId: number, settings: { schedule_interval_minutes: number, retry_interval_minutes: number }) => {
    return await etlApi.post(`/jobs/${jobId}/settings?tenant_id=${tenantId}`, settings)
  },
  getJobWorkerStatus: async (jobId: number, tenantId: number) => {
    return await etlApi.get(`/jobs/${jobId}/worker-status?tenant_id=${tenantId}`)
  },
  resetJobStatus: async (jobId: number, tenantId: number) => {
    return await etlApi.post(`/jobs/${jobId}/reset?tenant_id=${tenantId}`)
  },
}

export { etlApi }
export default etlApi
