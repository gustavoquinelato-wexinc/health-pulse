/**
 * TypeScript type definitions for authentication
 * Enhanced with optional ML fields for Phase 1-5: Auth Service Compatibility
 */

import { User } from './api';

// Authentication request types
export interface LoginRequest {
  email: string;
  password: string;
  include_ml_fields?: boolean;
}

export interface CredentialValidationRequest {
  email: string;
  password: string;
  include_ml_fields?: boolean;
}

export interface UserInfoRequest {
  include_ml_fields?: boolean;
}

export interface SessionInfoRequest {
  include_ml_fields?: boolean;
}

// Authentication response types
export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
  ml_fields_included?: boolean;
}

export interface CredentialValidationResponse {
  valid: boolean;
  user?: User;
  error?: string;
  ml_fields_included?: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
  ml_fields_included?: boolean;
}

export interface TokenValidationResponse {
  valid: boolean;
  user?: User;
  ml_fields_included?: boolean;
}

export interface UserInfoResponse {
  user: User;
  ml_fields_included: boolean;
}

// Session types
export interface UserSession {
  id: number;
  user_id: number;
  token_hash: string;
  ip_address?: string;
  user_agent?: string;
  expires_at: string;
  created_at: string;
  last_updated_at: string;
  active: boolean;
  client_id: number;
  
  // NEW: Optional ML fields (Phase 1: Always undefined)
  embedding?: number[];
  ml_context?: any;
}

export interface SessionInfoResponse {
  sessions: UserSession[];
  ml_fields_included: boolean;
  user_id: number;
}

export interface CurrentSessionInfo {
  user_id: number;
  email: string;
  role: string;
  is_admin: boolean;
  client_id: number;
  issued_at: string;
  expires_at: string;
  issuer: string;
  ml_fields?: {
    embedding?: number[];
    ml_context?: any;
  };
}

export interface CurrentSessionResponse {
  session: CurrentSessionInfo;
  ml_fields_included: boolean;
  valid: boolean;
}

// Auth context types
export interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string, includeMlFields?: boolean) => Promise<void>;
  logout: () => void;
  refreshToken: () => Promise<void>;
  getUserInfo: (includeMlFields?: boolean) => Promise<User>;
  getSessionInfo: (includeMlFields?: boolean) => Promise<UserSession[]>;
  getCurrentSession: (includeMlFields?: boolean) => Promise<CurrentSessionInfo>;
}

// Auth provider props
export interface AuthProviderProps {
  children: React.ReactNode;
}

// Auth error types
export interface AuthError {
  message: string;
  code?: string;
  status?: number;
}

// JWT payload types
export interface JWTPayload {
  user_id: number;
  email: string;
  role: string;
  is_admin: boolean;
  client_id: number;
  iat: number;
  exp: number;
  iss?: string;
}

// Auth service configuration
export interface AuthConfig {
  baseUrl: string;
  tokenKey: string;
  refreshTokenKey?: string;
  tokenExpiration: number;
  autoRefresh: boolean;
  includeMlFields: boolean; // NEW: Default ML fields inclusion setting
}

// Auth middleware types
export interface AuthMiddlewareOptions {
  requireAuth?: boolean;
  requireAdmin?: boolean;
  includeMlFields?: boolean;
  redirectTo?: string;
}

// Protected route props
export interface ProtectedRouteProps {
  children: React.ReactNode;
  requireAdmin?: boolean;
  includeMlFields?: boolean;
  fallback?: React.ReactNode;
}

// Auth hook return types
export interface UseAuthReturn {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isAdmin: boolean;
  login: (email: string, password: string, includeMlFields?: boolean) => Promise<void>;
  logout: () => void;
  refreshToken: () => Promise<void>;
  getUserInfo: (includeMlFields?: boolean) => Promise<User>;
  getSessionInfo: (includeMlFields?: boolean) => Promise<UserSession[]>;
  getCurrentSession: (includeMlFields?: boolean) => Promise<CurrentSessionInfo>;
}

// Auth state types
export interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: AuthError | null;
  lastActivity: number;
  sessionExpiry: number;
}

// Auth action types
export type AuthAction =
  | { type: 'LOGIN_START' }
  | { type: 'LOGIN_SUCCESS'; payload: { user: User; token: string } }
  | { type: 'LOGIN_FAILURE'; payload: AuthError }
  | { type: 'LOGOUT' }
  | { type: 'REFRESH_TOKEN_SUCCESS'; payload: { token: string } }
  | { type: 'REFRESH_TOKEN_FAILURE'; payload: AuthError }
  | { type: 'UPDATE_USER'; payload: User }
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: AuthError | null }
  | { type: 'UPDATE_ACTIVITY' };

// Auth storage types
export interface AuthStorage {
  getToken: () => string | null;
  setToken: (token: string) => void;
  removeToken: () => void;
  getUser: () => User | null;
  setUser: (user: User) => void;
  removeUser: () => void;
  clear: () => void;
}

// Auth API client types
export interface AuthApiClient {
  login: (request: LoginRequest) => Promise<LoginResponse>;
  logout: () => Promise<void>;
  validateCredentials: (request: CredentialValidationRequest) => Promise<CredentialValidationResponse>;
  generateToken: (request: CredentialValidationRequest) => Promise<TokenResponse>;
  validateToken: (token: string, includeMlFields?: boolean) => Promise<TokenValidationResponse>;
  getUserInfo: (includeMlFields?: boolean) => Promise<UserInfoResponse>;
  getSessionInfo: (includeMlFields?: boolean) => Promise<SessionInfoResponse>;
  getCurrentSession: (includeMlFields?: boolean) => Promise<CurrentSessionResponse>;
  refreshToken: () => Promise<TokenResponse>;
}
