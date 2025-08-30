/**
 * Enhanced API Service with ML fields support
 * Phase 1-6: Frontend Service Compatibility
 */

import {
  Issue,
  PullRequest,
  User,
  Project,
  IssuesResponse,
  PullRequestsResponse,
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
import apiClient from '../utils/apiClient.js';

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
   * Issues API
   */
  async getIssues(
    clientId: number,
    params: PaginationParams & FilterParams & {
      project_key?: string;
      status?: string;
      assignee?: string;
      include_ml_fields?: boolean;
    } = {}
  ): Promise<IssuesResponse> {
    const queryParams = this.buildQueryParams({
      ...params,
      client_id: clientId,
    });
    
    const additionalParams = new URLSearchParams();
    if (params.project_key) additionalParams.append('project_key', params.project_key);
    if (params.status) additionalParams.append('status', params.status);
    if (params.assignee) additionalParams.append('assignee', params.assignee);
    additionalParams.append('client_id', clientId.toString());

    const allParams = `${queryParams}&${additionalParams.toString()}`;
    return apiClient.get(`/api/v1/issues?${allParams}`);
  }

  async getIssue(issueId: number, includeMlFields?: boolean): Promise<Issue> {
    const params = new URLSearchParams();
    const includeMl = includeMlFields ?? this.defaultIncludeMlFields;
    params.append('include_ml_fields', includeMl.toString());
    
    return apiClient.get(`/api/v1/issues/${issueId}?${params.toString()}`);
  }

  async createIssue(issueData: Partial<Issue>): Promise<Issue> {
    return apiClient.post('/api/v1/issues', issueData);
  }

  async updateIssue(issueId: number, issueData: Partial<Issue>): Promise<Issue> {
    return apiClient.put(`/api/v1/issues/${issueId}`, issueData);
  }

  async deleteIssue(issueId: number): Promise<{ message: string; issue_id: number }> {
    return apiClient.delete(`/api/v1/issues/${issueId}`);
  }

  async getIssuesStats(clientId: number): Promise<any> {
    return apiClient.get(`/api/v1/issues/stats?client_id=${clientId}`);
  }

  /**
   * Pull Requests API
   */
  async getPullRequests(
    clientId: number,
    params: PaginationParams & FilterParams & {
      repository?: string;
      status?: string;
      user_name?: string;
      include_ml_fields?: boolean;
    } = {}
  ): Promise<PullRequestsResponse> {
    const queryParams = this.buildQueryParams({
      ...params,
      client_id: clientId,
    });
    
    const additionalParams = new URLSearchParams();
    if (params.repository) additionalParams.append('repository', params.repository);
    if (params.status) additionalParams.append('status', params.status);
    if (params.user_name) additionalParams.append('user_name', params.user_name);
    additionalParams.append('client_id', clientId.toString());

    const allParams = `${queryParams}&${additionalParams.toString()}`;
    return apiClient.get(`/api/v1/pull-requests?${allParams}`);
  }

  async getPullRequest(prId: number, includeMlFields?: boolean): Promise<PullRequest> {
    const params = new URLSearchParams();
    const includeMl = includeMlFields ?? this.defaultIncludeMlFields;
    params.append('include_ml_fields', includeMl.toString());
    
    return apiClient.get(`/api/v1/pull-requests/${prId}?${params.toString()}`);
  }

  async createPullRequest(prData: Partial<PullRequest>): Promise<PullRequest> {
    return apiClient.post('/api/v1/pull-requests', prData);
  }

  async updatePullRequest(prId: number, prData: Partial<PullRequest>): Promise<PullRequest> {
    return apiClient.put(`/api/v1/pull-requests/${prId}`, prData);
  }

  async deletePullRequest(prId: number): Promise<{ message: string; pr_id: number }> {
    return apiClient.delete(`/api/v1/pull-requests/${prId}`);
  }

  async getPullRequestsStats(clientId: number): Promise<any> {
    return apiClient.get(`/api/v1/pull-requests/stats?client_id=${clientId}`);
  }

  /**
   * Projects API
   */
  async getProjects(
    clientId: number,
    params: PaginationParams & FilterParams & {
      project_type?: string;
      include_ml_fields?: boolean;
    } = {}
  ): Promise<ProjectsResponse> {
    const queryParams = this.buildQueryParams({
      ...params,
      client_id: clientId,
    });
    
    const additionalParams = new URLSearchParams();
    if (params.project_type) additionalParams.append('project_type', params.project_type);
    additionalParams.append('client_id', clientId.toString());

    const allParams = `${queryParams}&${additionalParams.toString()}`;
    return apiClient.get(`/api/v1/projects?${allParams}`);
  }

  async getProject(projectId: number, includeMlFields?: boolean): Promise<Project> {
    const params = new URLSearchParams();
    const includeMl = includeMlFields ?? this.defaultIncludeMlFields;
    params.append('include_ml_fields', includeMl.toString());
    
    return apiClient.get(`/api/v1/projects/${projectId}?${params.toString()}`);
  }

  async getProjectByKey(projectKey: string, includeMlFields?: boolean): Promise<Project> {
    const params = new URLSearchParams();
    const includeMl = includeMlFields ?? this.defaultIncludeMlFields;
    params.append('include_ml_fields', includeMl.toString());
    
    return apiClient.get(`/api/v1/projects/by-key/${projectKey}?${params.toString()}`);
  }

  async createProject(projectData: Partial<Project>): Promise<Project> {
    return apiClient.post('/api/v1/projects', projectData);
  }

  async updateProject(projectId: number, projectData: Partial<Project>): Promise<Project> {
    return apiClient.put(`/api/v1/projects/${projectId}`, projectData);
  }

  async deleteProject(projectId: number): Promise<{ message: string; project_id: number }> {
    return apiClient.delete(`/api/v1/projects/${projectId}`);
  }

  async getProjectIssues(
    projectId: number,
    params: PaginationParams & { include_ml_fields?: boolean } = {}
  ): Promise<any> {
    const queryParams = this.buildQueryParams(params);
    return apiClient.get(`/api/v1/projects/${projectId}/issues?${queryParams}`);
  }

  async getProjectsStats(clientId: number): Promise<any> {
    return apiClient.get(`/api/v1/projects/stats?client_id=${clientId}`);
  }

  /**
   * Users API
   */
  async getUsers(
    clientId: number,
    params: PaginationParams & FilterParams & {
      active_only?: boolean;
      include_ml_fields?: boolean;
    } = {}
  ): Promise<UsersResponse> {
    const queryParams = this.buildQueryParams({
      ...params,
      client_id: clientId,
    });
    
    const additionalParams = new URLSearchParams();
    if (params.active_only !== undefined) additionalParams.append('active_only', params.active_only.toString());
    additionalParams.append('client_id', clientId.toString());

    const allParams = `${queryParams}&${additionalParams.toString()}`;
    return apiClient.get(`/api/v1/users?${allParams}`);
  }

  async getUser(userId: number, includeMlFields?: boolean): Promise<User> {
    const params = new URLSearchParams();
    const includeMl = includeMlFields ?? this.defaultIncludeMlFields;
    params.append('include_ml_fields', includeMl.toString());
    
    return apiClient.get(`/api/v1/users/${userId}?${params.toString()}`);
  }

  async getCurrentUser(includeMlFields?: boolean): Promise<User> {
    const params = new URLSearchParams();
    const includeMl = includeMlFields ?? this.defaultIncludeMlFields;
    params.append('include_ml_fields', includeMl.toString());
    
    return apiClient.get(`/api/v1/users/me?${params.toString()}`);
  }

  async getUserSessions(
    userId: number,
    params: PaginationParams & { active_only?: boolean } = {}
  ): Promise<any> {
    const queryParams = this.buildQueryParams(params);
    const additionalParams = new URLSearchParams();
    if (params.active_only !== undefined) additionalParams.append('active_only', params.active_only.toString());

    const allParams = `${queryParams}&${additionalParams.toString()}`;
    return apiClient.get(`/api/v1/users/${userId}/sessions?${allParams}`);
  }

  async getUserPermissions(userId: number): Promise<any> {
    return apiClient.get(`/api/v1/users/${userId}/permissions`);
  }

  async getUsersStats(clientId: number): Promise<any> {
    return apiClient.get(`/api/v1/users/stats?client_id=${clientId}`);
  }

  /**
   * Health Check APIs
   */
  async getBasicHealth(): Promise<any> {
    return apiClient.get('/health');
  }

  async getDatabaseHealth(): Promise<DatabaseHealthResponse> {
    return apiClient.get('/health/database');
  }

  async getMLHealth(): Promise<MLHealthResponse> {
    return apiClient.get('/health/ml');
  }

  async getComprehensiveHealth(): Promise<ComprehensiveHealthResponse> {
    return apiClient.get('/health/comprehensive');
  }

  /**
   * ML Monitoring APIs (Admin only)
   */
  async getLearningMemory(
    clientId: number,
    params: PaginationParams & { error_type?: string } = {}
  ): Promise<LearningMemoryResponse> {
    const queryParams = this.buildQueryParams(params);
    const additionalParams = new URLSearchParams();
    if (params.error_type) additionalParams.append('error_type', params.error_type);
    additionalParams.append('client_id', clientId.toString());

    const allParams = `${queryParams}&${additionalParams.toString()}`;
    return apiClient.get(`/api/v1/ml/learning-memory?${allParams}`);
  }

  async getPredictions(
    clientId: number,
    params: PaginationParams & { model_name?: string; prediction_type?: string } = {}
  ): Promise<PredictionsResponse> {
    const queryParams = this.buildQueryParams(params);
    const additionalParams = new URLSearchParams();
    if (params.model_name) additionalParams.append('model_name', params.model_name);
    if (params.prediction_type) additionalParams.append('prediction_type', params.prediction_type);
    additionalParams.append('client_id', clientId.toString());

    const allParams = `${queryParams}&${additionalParams.toString()}`;
    return apiClient.get(`/api/v1/ml/predictions?${allParams}`);
  }

  async getAnomalyAlerts(
    clientId: number,
    params: PaginationParams & { acknowledged?: boolean; severity?: string } = {}
  ): Promise<AnomalyAlertsResponse> {
    const queryParams = this.buildQueryParams(params);
    const additionalParams = new URLSearchParams();
    if (params.acknowledged !== undefined) additionalParams.append('acknowledged', params.acknowledged.toString());
    if (params.severity) additionalParams.append('severity', params.severity);
    additionalParams.append('client_id', clientId.toString());

    const allParams = `${queryParams}&${additionalParams.toString()}`;
    return apiClient.get(`/api/v1/ml/anomaly-alerts?${allParams}`);
  }

  async getMLStats(clientId: number, days: number = 30): Promise<MLStatsResponse> {
    return apiClient.get(`/api/v1/ml/stats?client_id=${clientId}&days=${days}`);
  }

  async getMLMonitoringHealth(clientId: number): Promise<any> {
    return apiClient.get(`/api/v1/ml/health?client_id=${clientId}`);
  }

  /**
   * Authentication APIs with ML fields support
   */
  async login(email: string, password: string, includeMlFields?: boolean): Promise<any> {
    const includeMl = includeMlFields ?? this.defaultIncludeMlFields;
    return apiClient.post('/api/v1/auth/login', {
      email,
      password,
      include_ml_fields: includeMl,
    });
  }

  async logout(): Promise<any> {
    return apiClient.post('/api/v1/auth/logout');
  }

  async validateToken(includeMlFields?: boolean): Promise<any> {
    const params = new URLSearchParams();
    const includeMl = includeMlFields ?? this.defaultIncludeMlFields;
    params.append('include_ml_fields', includeMl.toString());

    return apiClient.get(`/api/v1/auth/validate?${params.toString()}`);
  }

  async getUserInfo(includeMlFields?: boolean): Promise<any> {
    const params = new URLSearchParams();
    const includeMl = includeMlFields ?? this.defaultIncludeMlFields;
    params.append('include_ml_fields', includeMl.toString());

    return apiClient.get(`/api/v1/auth/user-info?${params.toString()}`);
  }

  async refreshToken(): Promise<any> {
    return apiClient.post('/api/v1/auth/refresh');
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
