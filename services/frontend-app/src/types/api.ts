/**
 * TypeScript type definitions for API responses and models
 * Enhanced with optional ML fields for Phase 1-6: Frontend Service Compatibility
 */

// Core model interfaces with optional ML fields
export interface WorkItem {
  // All existing fields (unchanged)
  id: number;
  key: string;
  summary: string;
  description?: string;
  priority?: string;
  status_name: string;
  wit_name: string;
  assignee?: string;
  assignee_id?: number;
  reporter?: string;
  reporter_id?: number;
  created?: string;
  updated?: string;
  resolved?: string;
  due_date?: string;
  story_points?: number;
  epic_link?: string;
  parent_key?: string;
  level_number: number;
  work_started_at?: string;
  work_first_completed_at?: string;
  work_last_completed_at?: string;
  total_lead_time_seconds?: number;
  project_id?: number;
  status_id?: number;
  wit_id?: number;
  parent_id?: number;
  comment_count: number;
  created_at: string;
  updated_at: string;
  active: boolean;
  tenant_id: number;
  
  // Custom fields (existing)
  custom_field_01?: string;
  custom_field_02?: string;
  custom_field_03?: string;
  custom_field_04?: string;
  custom_field_05?: string;
  custom_field_06?: string;
  custom_field_07?: string;
  custom_field_08?: string;
  custom_field_09?: string;
  custom_field_10?: string;
  custom_field_11?: string;
  custom_field_12?: string;
  custom_field_13?: string;
  custom_field_14?: string;
  custom_field_15?: string;
  custom_field_16?: string;
  custom_field_17?: string;
  custom_field_18?: string;
  custom_field_19?: string;
  custom_field_20?: string;
  
  // NEW: Optional ML fields (Phase 1: Always undefined)
  embedding?: number[];
  ml_estimated_story_points?: number;
  ml_estimation_confidence?: string;
}

export interface Pr {
  // All existing fields (unchanged)
  id: number;
  external_id: string;
  external_repo_id: string;
  repository_id?: number;
  number: number;
  name: string;
  user_name?: string;
  body?: string;
  discussion_comment_count?: number;
  review_comment_count?: number;
  reviewers?: number;
  status?: string;
  url?: string;
  pr_created_at?: string;
  pr_updated_at?: string;
  merged_at?: string;
  commit_count?: number;
  additions?: number;
  deletions?: number;
  changed_files?: number;
  first_review_at?: string;
  rework_commit_count?: number;
  review_cycles?: number;
  created_at: string;
  last_updated_at: string;
  active: boolean;
  tenant_id: number;
  
  // NEW: Optional ML fields (Phase 1: Always undefined)
  embedding?: number[];
  ml_rework_probability?: number;
  ml_risk_level?: string;
}

export interface User {
  // All existing fields (unchanged)
  id: number;
  email: string;
  first_name?: string;
  last_name?: string;
  role: string;
  is_admin: boolean;
  auth_provider: string;
  okta_user_id?: string;
  theme_mode: string;
  high_contrast_mode: boolean;
  reduce_motion: boolean;
  colorblind_safe_palette: boolean;
  accessibility_level: string;
  profile_image_filename?: string;
  last_login_at?: string;
  created_at: string;
  last_updated_at: string;
  active: boolean;
  tenant_id: number;
  
  // NEW: Optional ML fields (Phase 1: Always undefined)
  embedding?: number[];
}

export interface Project {
  // All existing fields (unchanged)
  id: number;
  external_id: string;
  key: string;
  name: string;
  project_type?: string;
  description?: string;
  lead?: string;
  url?: string;
  created_at: string;
  last_updated_at: string;
  active: boolean;
  tenant_id: number;
  
  // NEW: Optional ML fields (Phase 1: Always undefined)
  embedding?: number[];
}

// NEW: ML monitoring types (for future admin interfaces)
export interface AILearningMemory {
  id: number;
  error_type: string;
  user_intent: string;
  failed_query: string;
  specific_issue: string;
  suggested_fix: string;
  confidence: number;
  learning_context?: any;
  created_at: string;
  last_updated_at: string;
  active: boolean;
  tenant_id: number;
}

export interface AIPrediction {
  id: number;
  model_name: string;
  model_version?: string;
  input_data: string;
  prediction_result: string;
  confidence_score?: number;
  actual_outcome?: string;
  accuracy_score?: number;
  prediction_type: string;
  validated_at?: string;
  created_at: string;
  last_updated_at: string;
  active: boolean;
  tenant_id: number;
}

export interface MLAnomalyAlert {
  id: number;
  model_name: string;
  severity: string;
  alert_data: any;
  acknowledged: boolean;
  acknowledged_by?: number;
  acknowledged_at?: string;
  created_at: string;
  last_updated_at: string;
  active: boolean;
  tenant_id: number;
}

// API Response types with ML field indicators
export interface WorkItemsResponse {
  work_items: WorkItem[];
  count: number;
  total_count: number;
  offset: number;
  limit: number;
  ml_fields_included: boolean;
  filters?: {
    project_key?: string;
    status?: string;
    assignee?: string;
  };
}

export interface PrsResponse {
  pull_requests: Pr[];
  count: number;
  total_count: number;
  offset: number;
  limit: number;
  ml_fields_included: boolean;
  filters?: {
    repository?: string;
    status?: string;
    user_name?: string;
  };
}

export interface ProjectsResponse {
  projects: Project[];
  count: number;
  total_count: number;
  offset: number;
  limit: number;
  ml_fields_included: boolean;
  filters?: {
    project_type?: string;
    search?: string;
  };
}

export interface UsersResponse {
  users: User[];
  count: number;
  total_count: number;
  offset: number;
  limit: number;
  ml_fields_included: boolean;
  filters?: {
    search?: string;
    active_only?: boolean;
  };
}

// Health check types
export interface DatabaseHealthResponse {
  status: string;
  database_connection: string;
  ml_tables: Record<string, string>;
  vector_columns: Record<string, number | string>;
  timestamp: string;
}

export interface MLHealthResponse {
  status: string;
  postgresml: {
    available: boolean;
    version?: string;
    error?: string;
  };
  pgvector: {
    available: boolean;
    error?: string;
  };
  vector_columns_accessible: boolean;
  replica_connection: string;
  timestamp: string;
}

export interface ComprehensiveHealthResponse {
  status: string;
  service: string;
  version: string;
  timestamp: string;
  components: {
    basic: {
      status: string;
      database: string;
    };
    database: DatabaseHealthResponse;
    ml_infrastructure: MLHealthResponse;
  };
  summary: {
    total_components: number;
    healthy_components: number;
    degraded_components: number;
    unhealthy_components: number;
  };
}

// ML Monitoring API Response types
export interface LearningMemoryResponse {
  learning_memories: AILearningMemory[];
  count: number;
  total_count: number;
  offset: number;
  limit: number;
  filters: {
    error_type?: string;
    tenant_id: number;
  };
}

export interface PredictionsResponse {
  predictions: AIPrediction[];
  count: number;
  total_count: number;
  offset: number;
  limit: number;
  filters: {
    model_name?: string;
    prediction_type?: string;
    tenant_id: number;
  };
}

export interface AnomalyAlertsResponse {
  anomaly_alerts: MLAnomalyAlert[];
  count: number;
  total_count: number;
  offset: number;
  limit: number;
  filters: {
    acknowledged?: boolean;
    severity?: string;
    tenant_id: number;
  };
}

export interface MLStatsResponse {
  period: {
    days: number;
    start_date: string;
    end_date: string;
  };
  summary: {
    learning_memories: number;
    predictions: number;
    anomaly_alerts: number;
    unacknowledged_alerts: number;
  };
  model_usage: Array<{
    model_name: string;
    prediction_count: number;
  }>;
  tenant_id: number;
}
