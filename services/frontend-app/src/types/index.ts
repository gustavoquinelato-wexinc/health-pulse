/**
 * Central export file for all TypeScript type definitions
 * Phase 1-6: Frontend Service Compatibility
 */

// API types
export type {
  // Core model types
  WorkItem,
  Pr,
  User,
  Project,
  
  // ML monitoring types
  AILearningMemory,
  AIPrediction,
  MLAnomalyAlert,
  
  // API response types
  WorkItemsResponse,
  PrsResponse,
  ProjectsResponse,
  UsersResponse,
  
  // Health check types
  DatabaseHealthResponse,
  MLHealthResponse,
  ComprehensiveHealthResponse,
  
  // ML monitoring response types
  LearningMemoryResponse,
  PredictionsResponse,
  AnomalyAlertsResponse,
  MLStatsResponse,
} from './api';

// Auth types
export type {
  // Request types
  LoginRequest,
  CredentialValidationRequest,
  UserInfoRequest,
  SessionInfoRequest,
  
  // Response types
  LoginResponse,
  CredentialValidationResponse,
  TokenResponse,
  TokenValidationResponse,
  UserInfoResponse,
  
  // Session types
  UserSession,
  SessionInfoResponse,
  CurrentSessionInfo,
  CurrentSessionResponse,
  
  // Context types
  AuthContextType,
  AuthProviderProps,
  
  // Error types
  AuthError,
  
  // JWT types
  JWTPayload,
  
  // Configuration types
  AuthConfig,
  AuthMiddlewareOptions,
  ProtectedRouteProps,
  
  // Hook types
  UseAuthReturn,
  
  // State management types
  AuthState,
  AuthAction,
  
  // Storage types
  AuthStorage,
  
  // API client types
  AuthApiTenant,
} from './auth';

// Common utility types
export interface ApiResponse<T = any> {
  data?: T;
  error?: string;
  message?: string;
  status: number;
  success: boolean;
  ml_fields_included?: boolean;
}

export interface PaginationParams {
  limit?: number;
  offset?: number;
  page?: number;
  per_page?: number;
}

export interface FilterParams {
  search?: string;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  include_ml_fields?: boolean;
}

export interface ApiRequestOptions {
  headers?: Record<string, string>;
  timeout?: number;
  retries?: number;
  include_ml_fields?: boolean;
}

// Component prop types
export interface BaseComponentProps {
  className?: string;
  children?: React.ReactNode;
  'data-testid'?: string;
}

export interface LoadingProps extends BaseComponentProps {
  size?: 'sm' | 'md' | 'lg';
  variant?: 'spinner' | 'dots' | 'pulse';
}

export interface ErrorProps extends BaseComponentProps {
  error: Error | string;
  retry?: () => void;
  showDetails?: boolean;
}

// Theme types
export interface ThemeConfig {
  mode: 'light' | 'dark' | 'auto';
  primaryColor: string;
  secondaryColor: string;
  accentColor: string;
  fontFamily: string;
  fontSize: 'sm' | 'md' | 'lg';
  borderRadius: 'none' | 'sm' | 'md' | 'lg';
  animations: boolean;
  reducedMotion: boolean;
  highContrast: boolean;
  colorblindSafe: boolean;
}

export interface ThemeContextType {
  theme: ThemeConfig;
  setTheme: (theme: Partial<ThemeConfig>) => void;
  toggleMode: () => void;
  resetTheme: () => void;
}

// Navigation types
export interface NavItem {
  id: string;
  label: string;
  path: string;
  icon?: string;
  badge?: string | number;
  children?: NavItem[];
  requireAuth?: boolean;
  requireAdmin?: boolean;
  external?: boolean;
}

export interface BreadcrumbItem {
  label: string;
  path?: string;
  active?: boolean;
}

// Form types
export interface FormField {
  name: string;
  label: string;
  type: 'text' | 'email' | 'password' | 'number' | 'select' | 'textarea' | 'checkbox' | 'radio';
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  options?: Array<{ label: string; value: string | number }>;
  validation?: {
    min?: number;
    max?: number;
    pattern?: string;
    custom?: (value: any) => string | undefined;
  };
}

export interface FormConfig {
  fields: FormField[];
  submitLabel?: string;
  resetLabel?: string;
  onSubmit: (data: Record<string, any>) => Promise<void> | void;
  onReset?: () => void;
  loading?: boolean;
  disabled?: boolean;
}

// Table types
export interface TableColumn<T = any> {
  key: keyof T | string;
  label: string;
  sortable?: boolean;
  filterable?: boolean;
  width?: string | number;
  align?: 'left' | 'center' | 'right';
  render?: (value: any, row: T, index: number) => React.ReactNode;
}

export interface TableConfig<T = any> {
  columns: TableColumn<T>[];
  data: T[];
  loading?: boolean;
  error?: string;
  pagination?: {
    current: number;
    total: number;
    pageSize: number;
    onChange: (page: number, pageSize: number) => void;
  };
  selection?: {
    selectedKeys: string[];
    onChange: (selectedKeys: string[]) => void;
  };
  actions?: Array<{
    key: string;
    label: string;
    icon?: string;
    onClick: (row: T) => void;
    disabled?: (row: T) => boolean;
  }>;
}

// Chart types
export interface ChartDataPoint {
  x: string | number | Date;
  y: number;
  label?: string;
  color?: string;
}

export interface ChartSeries {
  name: string;
  data: ChartDataPoint[];
  color?: string;
  type?: 'line' | 'bar' | 'area' | 'scatter';
}

export interface ChartConfig {
  title?: string;
  subtitle?: string;
  series: ChartSeries[];
  xAxis?: {
    title?: string;
    type?: 'category' | 'datetime' | 'numeric';
    format?: string;
  };
  yAxis?: {
    title?: string;
    format?: string;
    min?: number;
    max?: number;
  };
  legend?: {
    show?: boolean;
    position?: 'top' | 'bottom' | 'left' | 'right';
  };
  tooltip?: {
    show?: boolean;
    format?: string;
  };
}

// Notification types
export interface Notification {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message?: string;
  duration?: number;
  persistent?: boolean;
  actions?: Array<{
    label: string;
    onClick: () => void;
  }>;
}

export interface NotificationContextType {
  notifications: Notification[];
  addNotification: (notification: Omit<Notification, 'id'>) => void;
  removeNotification: (id: string) => void;
  clearNotifications: () => void;
}

// WebSocket types
export interface WebSocketMessage {
  type: string;
  payload: any;
  timestamp: number;
  id?: string;
}

export interface WebSocketConfig {
  url: string;
  protocols?: string[];
  reconnect?: boolean;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  heartbeat?: {
    interval: number;
    message: string;
  };
}

// Environment types
export interface EnvironmentConfig {
  NODE_ENV: 'development' | 'production' | 'test';
  API_BASE_URL: string;
  APP_TITLE: string;
  ETL_SERVICE_URL: string;
  AI_SERVICE_URL: string;
  ENABLE_REAL_TIME: boolean;
  ENABLE_AI_FEATURES: boolean;
  ENABLE_ML_FIELDS: boolean; // NEW: ML fields feature flag
}
