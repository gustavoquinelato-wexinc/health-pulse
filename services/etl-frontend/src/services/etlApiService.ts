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
}

// Integrations API
export const integrationsApi = {
  getIntegrations: async () => {
    return await etlApi.get('/integrations')
  },
}

// Qdrant API
export const qdrantApi = {
  getCollections: async () => {
    return await etlApi.get('/qdrant/collections')
  },
  getHealth: async () => {
    return await etlApi.get('/qdrant/health')
  },
}

export default etlApi
