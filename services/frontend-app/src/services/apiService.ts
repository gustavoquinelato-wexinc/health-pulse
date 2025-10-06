/**
 * Enhanced API Service with ML fields support
 * Phase 1-6: Frontend Service Compatibility
 */

import {
  WorkItem,
  Pr,
  User,
  Project,
  WorkItemsResponse,
  PrsResponse,
  UsersResponse,
  ProjectsResponse,
  DatabaseHealthResponse,
  MLHealthResponse,
  ComprehensiveHealthResponse,
  LearningMemoryResponse,
  PredictionsResponse,
  AnomalyAlertsResponse,
  MLStatsResponse,
  ApiResponse,
  PaginationParams,
  FilterParams,
  ApiRequestOptions,
} from '../types';

// @ts-ignore - Import existing JS client for now
import apiTenant from '../utils/apiClient.js';

class ApiService {
  private baseUrl: string;
  private defaultIncludeMlFields: boolean;

  constructor(baseUrl: string = '', defaultIncludeMlFields: boolean = false) {
    this.baseUrl = baseUrl;
    this.defaultIncludeMlFields = defaultIncludeMlFields;
  }

  /**
   * Build query parameters with ML fields support
   */
  private buildQueryParams(
    params: PaginationParams & FilterParams & { include_ml_fields?: boolean } = {}
  ): string {
    const queryParams = new URLSearchParams();

    // Add pagination params
    if (params.limit !== undefined) queryParams.append('limit', params.limit.toString());
    if (params.offset !== undefined) queryParams.append('offset', params.offset.toString());
    if (params.page !== undefined) queryParams.append('page', params.page.toString());
    if (params.per_page !== undefined) queryParams.append('per_page', params.per_page.toString());

    // Add filter params
    if (params.search) queryParams.append('search', params.search);
    if (params.sort_by) queryParams.append('sort_by', params.sort_by);
    if (params.sort_order) queryParams.append('sort_order', params.sort_order);

    // Add ML fields param
    const includeMlFields = params.include_ml_fields ?? this.defaultIncludeMlFields;
    queryParams.append('include_ml_fields', includeMlFields.toString());

    return queryParams.toString();
  }

  /**
   * WorkItems API
   */
  async getWorkItems(
    tenantId: number,
    params: PaginationParams & FilterParams & {
      project_key?: string;
      status?: string;
      assignee?: string;
      include_ml_fields?: boolean;
    } = {}
  ): Promise<WorkItemsResponse> {
    const queryParams = this.buildQueryParams({
      ...params,
      tenant_id: tenantId,
    });

    const additionalParams = new URLSearchParams();
    if (params.project_key) additionalParams.append('project_key', params.project_key);
    if (params.status) additionalParams.append('status', params.status);
    if (params.assignee) additionalParams.append('assignee', params.assignee);
    additionalParams.append('tenant_id', tenantId.toString());

    const allParams = `${queryParams}&${additionalParams.toString()}`;
    return apiTenant.get(`/api/v1/work-items?${allParams}`);
  }

  async getWorkItem(workItemId: number, includeMlFields?: boolean): Promise<WorkItem> {
    const params = new URLSearchParams();
    const includeMl = includeMlFields ?? this.defaultIncludeMlFields;
    params.append('include_ml_fields', includeMl.toString());

    return apiTenant.get(`/api/v1/work-items/${workItemId}?${params.toString()}`);
  }

  async createWorkItem(workItemData: Partial<WorkItem>): Promise<WorkItem> {
    return apiTenant.post('/api/v1/work-items', workItemData);
  }

  async updateWorkItem(workItemId: number, workItemData: Partial<WorkItem>): Promise<WorkItem> {
    return apiTenant.put(`/api/v1/work-items/${workItemId}`, workItemData);
  }

  async deleteWorkItem(workItemId: number): Promise<{ message: string; work_item_id: number }> {
    return apiTenant.delete(`/api/v1/work-items/${workItemId}`);
  }

  async getWorkItemsStats(tenantId: number): Promise<any> {
    return apiTenant.get(`/api/v1/work-items/stats?tenant_id=${tenantId}`);
  }

  /**
   * Pull Requests API
   */
  async getPrs(
    tenantId: number,
    params: PaginationParams & FilterParams & {
      repository?: string;
      status?: string;
      user_name?: string;
      include_ml_fields?: boolean;
    } = {}
  ): Promise<PrsResponse> {
    const queryParams = this.buildQueryParams({
      ...params,
      tenant_id: tenantId,
    });

    const additionalParams = new URLSearchParams();
    if (params.repository) additionalParams.append('repository', params.repository);
    if (params.status) additionalParams.append('status', params.status);
    if (params.user_name) additionalParams.append('user_name', params.user_name);
    additionalParams.append('tenant_id', tenantId.toString());

    const allParams = `${queryParams}&${additionalParams.toString()}`;
    return apiTenant.get(`/api/v1/pull-requests?${allParams}`);
  }

  async getPr(prId: number, includeMlFields?: boolean): Promise<Pr> {
    const params = new URLSearchParams();
    const includeMl = includeMlFields ?? this.defaultIncludeMlFields;
    params.append('include_ml_fields', includeMl.toString());
    
    return apiTenant.get(`/api/v1/pull-requests/${prId}?${params.toString()}`);
  }

  async createPr(prData: Partial<Pr>): Promise<Pr> {
    return apiTenant.post('/api/v1/pull-requests', prData);
  }

  async updatePr(prId: number, prData: Partial<Pr>): Promise<Pr> {
    return apiTenant.put(`/api/v1/pull-requests/${prId}`, prData);
  }

  async deletePr(prId: number): Promise<{ message: string; pr_id: number }> {
    return apiTenant.delete(`/api/v1/pull-requests/${prId}`);
  }

  async getPrsStats(tenantId: number): Promise<any> {
    return apiTenant.get(`/api/v1/pull-requests/stats?tenant_id=${tenantId}`);
  }

  /**
   * Projects API
   */
  async getProjects(
    tenantId: number,
    params: PaginationParams & FilterParams & {
      project_type?: string;
      include_ml_fields?: boolean;
    } = {}
  ): Promise<ProjectsResponse> {
    const queryParams = this.buildQueryParams({
      ...params,
      tenant_id: tenantId,
    });

    const additionalParams = new URLSearchParams();
    if (params.project_type) additionalParams.append('project_type', params.project_type);
    additionalParams.append('tenant_id', tenantId.toString());

    const allParams = `${queryParams}&${additionalParams.toString()}`;
    return apiTenant.get(`/api/v1/projects?${allParams}`);
  }

  async getProject(projectId: number, includeMlFields?: boolean): Promise<Project> {
    const params = new URLSearchParams();
    const includeMl = includeMlFields ?? this.defaultIncludeMlFields;
    params.append('include_ml_fields', includeMl.toString());
    
    return apiTenant.get(`/api/v1/projects/${projectId}?${params.toString()}`);
  }

  async getProjectByKey(projectKey: string, includeMlFields?: boolean): Promise<Project> {
    const params = new URLSearchParams();
    const includeMl = includeMlFields ?? this.defaultIncludeMlFields;
    params.append('include_ml_fields', includeMl.toString());
    
    return apiTenant.get(`/api/v1/projects/by-key/${projectKey}?${params.toString()}`);
  }

  async createProject(projectData: Partial<Project>): Promise<Project> {
    return apiTenant.post('/api/v1/projects', projectData);
  }

  async updateProject(projectId: number, projectData: Partial<Project>): Promise<Project> {
    return apiTenant.put(`/api/v1/projects/${projectId}`, projectData);
  }

  async deleteProject(projectId: number): Promise<{ message: string; project_id: number }> {
    return apiTenant.delete(`/api/v1/projects/${projectId}`);
  }

  async getProjectWorkItems(
    projectId: number,
    params: PaginationParams & { include_ml_fields?: boolean } = {}
  ): Promise<any> {
    const queryParams = this.buildQueryParams(params);
    return apiTenant.get(`/api/v1/projects/${projectId}/work-items?${queryParams}`);
  }

  async getProjectsStats(tenantId: number): Promise<any> {
    return apiTenant.get(`/api/v1/projects/stats?tenant_id=${tenantId}`);
  }

  /**
   * Users API
   */
  async getUsers(
    tenantId: number,
    params: PaginationParams & FilterParams & {
      active_only?: boolean;
      include_ml_fields?: boolean;
    } = {}
  ): Promise<UsersResponse> {
    const queryParams = this.buildQueryParams({
      ...params,
      tenant_id: tenantId,
    });

    const additionalParams = new URLSearchParams();
    if (params.active_only !== undefined) additionalParams.append('active_only', params.active_only.toString());
    additionalParams.append('tenant_id', tenantId.toString());

    const allParams = `${queryParams}&${additionalParams.toString()}`;
    return apiTenant.get(`/api/v1/users?${allParams}`);
  }

  async getUser(userId: number, includeMlFields?: boolean): Promise<User> {
    const params = new URLSearchParams();
    const includeMl = includeMlFields ?? this.defaultIncludeMlFields;
    params.append('include_ml_fields', includeMl.toString());
    
    return apiTenant.get(`/api/v1/users/${userId}?${params.toString()}`);
  }

  async getCurrentUser(includeMlFields?: boolean): Promise<User> {
    const params = new URLSearchParams();
    const includeMl = includeMlFields ?? this.defaultIncludeMlFields;
    params.append('include_ml_fields', includeMl.toString());
    
    return apiTenant.get(`/api/v1/users/me?${params.toString()}`);
  }

  async getUserSessions(
    userId: number,
    params: PaginationParams & { active_only?: boolean } = {}
  ): Promise<any> {
    const queryParams = this.buildQueryParams(params);
    const additionalParams = new URLSearchParams();
    if (params.active_only !== undefined) additionalParams.append('active_only', params.active_only.toString());

    const allParams = `${queryParams}&${additionalParams.toString()}`;
    return apiTenant.get(`/api/v1/users/${userId}/sessions?${allParams}`);
  }

  async getUserPermissions(userId: number): Promise<any> {
    return apiTenant.get(`/api/v1/users/${userId}/permissions`);
  }

  async getUsersStats(tenantId: number): Promise<any> {
    return apiTenant.get(`/api/v1/users/stats?tenant_id=${tenantId}`);
  }

  /**
   * Health Check APIs
   */
  async getBasicHealth(): Promise<any> {
    return apiTenant.get('/health');
  }

  async getDatabaseHealth(): Promise<DatabaseHealthResponse> {
    return apiTenant.get('/health/database');
  }

  async getMLHealth(): Promise<MLHealthResponse> {
    return apiTenant.get('/health/ml');
  }

  async getComprehensiveHealth(): Promise<ComprehensiveHealthResponse> {
    return apiTenant.get('/health/comprehensive');
  }

  /**
   * ML Monitoring APIs (Admin only)
   */
  async getLearningMemory(
    tenantId: number,
    params: PaginationParams & { error_type?: string } = {}
  ): Promise<LearningMemoryResponse> {
    const queryParams = this.buildQueryParams(params);
    const additionalParams = new URLSearchParams();
    if (params.error_type) additionalParams.append('error_type', params.error_type);
    additionalParams.append('tenant_id', tenantId.toString());

    const allParams = `${queryParams}&${additionalParams.toString()}`;
    return apiTenant.get(`/api/v1/ml/learning-memory?${allParams}`);
  }

  async getPredictions(
    tenantId: number,
    params: PaginationParams & { model_name?: string; prediction_type?: string } = {}
  ): Promise<PredictionsResponse> {
    const queryParams = this.buildQueryParams(params);
    const additionalParams = new URLSearchParams();
    if (params.model_name) additionalParams.append('model_name', params.model_name);
    if (params.prediction_type) additionalParams.append('prediction_type', params.prediction_type);
    additionalParams.append('tenant_id', tenantId.toString());

    const allParams = `${queryParams}&${additionalParams.toString()}`;
    return apiTenant.get(`/api/v1/ml/predictions?${allParams}`);
  }

  async getAnomalyAlerts(
    tenantId: number,
    params: PaginationParams & { acknowledged?: boolean; severity?: string } = {}
  ): Promise<AnomalyAlertsResponse> {
    const queryParams = this.buildQueryParams(params);
    const additionalParams = new URLSearchParams();
    if (params.acknowledged !== undefined) additionalParams.append('acknowledged', params.acknowledged.toString());
    if (params.severity) additionalParams.append('severity', params.severity);
    additionalParams.append('tenant_id', tenantId.toString());

    const allParams = `${queryParams}&${additionalParams.toString()}`;
    return apiTenant.get(`/api/v1/ml/anomaly-alerts?${allParams}`);
  }

  async getMLStats(tenantId: number, days: number = 30): Promise<MLStatsResponse> {
    return apiTenant.get(`/api/v1/ml/stats?tenant_id=${tenantId}&days=${days}`);
  }

  async getMLMonitoringHealth(tenantId: number): Promise<any> {
    return apiTenant.get(`/api/v1/ml/health?tenant_id=${tenantId}`);
  }

  /**
   * Authentication APIs with ML fields support
   */
  async login(email: string, password: string, includeMlFields?: boolean): Promise<any> {
    const includeMl = includeMlFields ?? this.defaultIncludeMlFields;
    return apiTenant.post('/api/v1/auth/login', {
      email,
      password,
      include_ml_fields: includeMl,
    });
  }

  async logout(): Promise<any> {
    return apiTenant.post('/api/v1/auth/logout');
  }

  async validateToken(includeMlFields?: boolean): Promise<any> {
    const params = new URLSearchParams();
    const includeMl = includeMlFields ?? this.defaultIncludeMlFields;
    params.append('include_ml_fields', includeMl.toString());

    return apiTenant.get(`/api/v1/auth/validate?${params.toString()}`);
  }

  async getUserInfo(includeMlFields?: boolean): Promise<any> {
    const params = new URLSearchParams();
    const includeMl = includeMlFields ?? this.defaultIncludeMlFields;
    params.append('include_ml_fields', includeMl.toString());

    return apiTenant.get(`/api/v1/auth/user-info?${params.toString()}`);
  }

  async refreshToken(): Promise<any> {
    return apiTenant.post('/api/v1/auth/refresh');
  }

  /**
   * Configuration methods
   */
  setDefaultIncludeMlFields(include: boolean): void {
    this.defaultIncludeMlFields = include;
  }

  getDefaultIncludeMlFields(): boolean {
    return this.defaultIncludeMlFields;
  }
}

// Create singleton instance
const apiService = new ApiService(
  import.meta.env.VITE_API_BASE_URL || '',
  import.meta.env.VITE_ENABLE_ML_FIELDS === 'true' || false
);

export default apiService;
