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

// Add request interceptor to include auth token
etlApi.interceptors.request.use(
  (config) => {
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

// Response interceptor for error handling
etlApi.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token expired or invalid
      localStorage.removeItem('pulse_token')
      window.location.href = '/login'
    }
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
}

export default etlApi
