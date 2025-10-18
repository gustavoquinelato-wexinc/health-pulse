// ETL Frontend TypeScript Interfaces
// Phase 2.1: Database Foundation & UI Management

// Base entity interfaces
export interface BaseEntity {
  id: number;
  active: boolean;
  created_at: string;
  last_updated_at: string;
}

export interface IntegrationBaseEntity extends BaseEntity {
  integration_id: number;
  tenant_id: number;
}

// Core entities
export interface Tenant extends BaseEntity {
  name: string;
  website?: string;
  assets_folder?: string;
  logo_filename?: string;
  color_schema_mode?: string;
}

export interface Integration extends BaseEntity {
  name: string; // Integration name/provider: 'Jira', 'GitHub', 'WEX AI Gateway', etc.
  integration_type: string; // 'Data', 'AI', 'Embedding', 'System'
  username?: string;
  password?: string;
  base_url?: string;
  settings?: Record<string, any>; // Unified settings (replaces base_search, ai_model, ai_model_config, cost_config)
  fallback_integration_id?: number;
  logo_filename?: string;
  custom_field_mappings?: Record<string, any>; // Phase 2.1: Custom field mappings
  tenant_id: number;
}

export interface Project extends IntegrationBaseEntity {
  external_id?: string;
  key: string;
  name: string;
  project_type?: string;
}

export interface WorkItem extends IntegrationBaseEntity {
  external_id?: string;
  key?: string;
  project_id?: number;
  team?: string;
  summary?: string;
  description?: string;
  acceptance_criteria?: string;
  wit_id?: number;
  status_id?: number;
  resolution?: string;
  story_points?: number;
  assignee?: string;
  labels?: string;
  created?: string;
  updated?: string;
  work_first_committed_at?: string;
  work_first_started_at?: string;
  work_last_started_at?: string;
  work_first_completed_at?: string;
  work_last_completed_at?: string;
  priority?: string;
  parent_external_id?: string;
  code_changed?: boolean;
  total_work_starts?: number;
  total_completions?: number;
  total_backlog_returns?: number;
  total_work_time_seconds?: number;
  total_review_time_seconds?: number;
  total_cycle_time_seconds?: number;
  total_lead_time_seconds?: number;
  workflow_complexity_score?: number;
  rework_indicator?: boolean;
  direct_completion?: boolean;
  
  // Custom fields (20 optimized columns)
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

}



// Custom field from database
export interface CustomField {
  id: number;
  external_id: string;  // e.g., "customfield_10001"
  name: string;         // e.g., "Agile Team"
  field_type: string;   // e.g., "team", "string", "option"
  operations: string[]; // e.g., ["set"], ["add", "remove"]
}

// Custom field mapping interfaces
export interface CustomFieldMapping {
  jira_field_id: string;
  jira_field_name: string;
  mapped_column?: string; // custom_field_01 through custom_field_20, or 'overflow'
  is_active: boolean;
}

export interface CustomFieldMappingConfig {
  project_id: number;
  integration_id: number;
  mappings: CustomFieldMapping[];
  last_updated: string;
}

// API response interfaces
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  message?: string;
  error?: string;
}

export interface PaginatedResponse<T> {
  success: boolean;
  data: T[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}



// Custom field mapping API interfaces
export interface SaveCustomFieldMappingRequest {
  integration_id: number;
  custom_field_mappings: Record<string, any>;
}

export interface GetCustomFieldMappingResponse {
  integration_id: number;
  custom_field_mappings: Record<string, any>;
  available_columns: string[]; // ['custom_field_01', 'custom_field_02', ...]
  mapped_columns: string[]; // Currently used columns
}
