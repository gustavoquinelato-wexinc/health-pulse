# Pulse Platform - Agent Guidance Document

**For Augment Code Agents working on the Pulse Platform**

This document provides essential context, architectural decisions, and operational guidelines for agents working on this codebase. Read this document first before making any changes.

## 📖 **Required Reading - MANDATORY**

Before starting any work on the Pulse Platform, agents **MUST** familiarize themselves with the system architecture and design principles by reading these essential documents:

### **Primary Documentation (READ FIRST)**
1. **[README.md](../README.md)** - Complete platform overview including:
   - System architecture diagrams and component relationships
   - Quick start guide and configuration procedures
   - Development workflow and testing guidelines
   - Deployment and operational procedures
   - Troubleshooting and monitoring guidance

2. **[Documentation Index](DOCUMENTATION_INDEX.md)** - Navigation guide to all platform documentation

3. **[Architecture Guide](ARCHITECTURE.md)** - Detailed system architecture and design decisions

4. **[Migration Guide](MIGRATION_GUIDE.md)** - Database migration system and procedures

### **Development Documentation**
- **[Scripts Guide](SCRIPTS_GUIDE.md)** - Cross-service scripts and utilities
- **[ETL Development Guide](../services/etl-service/docs/DEVELOPMENT_GUIDE.md)** - ETL service development and testing
- **[Frontend Development Guide](../services/frontend-app/README.md)** - Frontend application development

### **Operational Documentation**
- **[Deployment Guide](DEPLOYMENT.md)** - Deployment procedures and environment management
- **[GitHub Job Guide](GITHUB_JOB_GUIDE.md)** - GitHub integration specifics
- **[Admin Page Template](ADMIN_PAGE_TEMPLATE.md)** - Standard patterns for admin interfaces

### **Service-Specific Documentation**
- **[ETL Service README](../services/etl-service/README.md)** - ETL service overview and features
- **[Frontend App README](../services/frontend-app/README.md)** - Frontend application guide
- **[Backend Service README](../services/backend-service/README.md)** - Backend API service guide

**⚠️ CRITICAL:** The README.md file and all documentation in the /docs folder contain the foundational understanding needed to work effectively with the platform's architecture, design patterns, and operational procedures. Failure to read these documents will result in architectural violations and inconsistent implementations.

## 🏗️ **System Architecture Context**

### **Platform Overview**
The Pulse Platform is a microservices-based analytics platform with specialized services:
- **ETL Service** (Python/FastAPI) - Data engineering: extraction, loading, job orchestration
- **Backend Service** (Python/FastAPI) - Analytics APIs, authentication, API gateway for React frontend
- **Frontend App** (React/Vite) - Modern React interface with analytics dashboards
- **AI Service** (Python/LangGraph) - AI orchestration and agent workflows
- **PostgreSQL** - Primary database with normalized schema
- **Redis** - Caching and session management

### **Key Architectural Decisions**
1. **Database-First Design**: All data models are defined in SQLAlchemy with proper relationships
2. **Python-First Analytics**: Backend service uses Python for superior data processing capabilities
3. **Service Separation**: ETL (data engineering) and Backend (data consumption/API gateway) are specialized services
4. **Job Orchestration**: ETL jobs use a sophisticated checkpoint and recovery system
5. **API Security**: Token-based authentication with role-based permissions
6. **Data Integrity**: Foreign key constraints and normalized relationships throughout
7. **Analytics Focus**: Platform optimized for complex calculations, DORA metrics, and executive dashboards

## 🏛️ **Architecture Rationale: Why Python for Backend Service**

### **Critical Decision: Python Over Node.js**
The backend service uses Python instead of Node.js for compelling technical reasons:

#### **1. Analytics Workload Optimization**
- **Complex Calculations**: DORA metrics, statistical analysis, data aggregations
- **Data Processing Libraries**: NumPy, Pandas, SciPy for advanced analytics
- **Database Operations**: SQLAlchemy for complex analytical queries
- **Performance**: Python's data science ecosystem is highly optimized

#### **2. Service Specialization Strategy**
```
ETL Service (Data Engineering)     Backend Service (Data Analytics & API Gateway)
├── Data extraction & loading      ├── Complex calculations & metrics
├── Job orchestration             ├── Dashboard data preparation
├── External API integrations     ├── Query optimization & caching
├── Checkpoint recovery           ├── Frontend API gateway
└── Data quality validation       └── Real-time analytics serving
```

#### **3. Technology Alignment**
- **Shared Ecosystem**: Both ETL and Backend services use Python data stack
- **Code Reuse**: Database models, utilities, and patterns can be shared
- **Skill Consolidation**: Single language expertise for data operations
- **Library Compatibility**: Seamless integration of analytics libraries

#### **4. Analytics Use Cases**
- **DORA Metrics**: Lead time, deployment frequency, MTTR calculations
- **GitHub Analytics**: Code quality metrics, PR analysis, contributor insights
- **Portfolio Analytics**: Cross-project aggregations and correlations
- **C-Level Dashboards**: Executive KPIs and business intelligence
- **ETL Configuration**: Settings management and job coordination

**⚠️ CRITICAL**: Never suggest Node.js for analytics workloads. Python's data science ecosystem provides significant advantages for the platform's analytical requirements.

## ⚙️ **Configuration Management**

### **Centralized Environment Configuration**
The platform uses a **single, centralized `.env` file** at the root level for all services:

```
pulse-platform/
├── .env                    # ✅ SINGLE source of truth for all configuration
├── .env.example           # Template with all required variables
├── services/
│   ├── etl-service/       # ❌ NO local .env files
│   ├── backend-service/   # ❌ NO local .env files
│   └── frontend-app/      # ❌ NO local .env files
```

### **Configuration Principles**
1. **Single Source of Truth**: All environment variables in root `.env` file
2. **Service Sections**: Variables organized by service (ETL, Analytics, Frontend, etc.)
3. **Shared Variables**: Database, Redis, and security settings shared across services
4. **Docker Integration**: Root `.env` automatically loaded by docker-compose
5. **Development Consistency**: Same configuration for all developers

### **Critical Rules**
- **NEVER create service-specific `.env` files** - use only the root `.env`
- **ALWAYS reference root `.env`** in documentation and setup instructions
- **UPDATE root `.env.example`** when adding new configuration variables
- **VALIDATE configuration** through the centralized file during setup

**⚠️ IMPORTANT**: If you find any service-specific `.env` files, remove them and consolidate into the root `.env` file.

## 🗄️ **Database Schema Principles**

### **Critical Schema Rules**
1. **Foreign Key Relationships**: Always use proper FK constraints, never store redundant data
3. **Client Isolation**: All data is client-scoped with proper client_id foreign keys
4. **Audit Fields**: All entities have active, created_at, last_updated_at, and active fields
5. **Normalized Design**: Avoid data duplication, use proper relationship tables

### **Recent Schema Changes**
- **Issue Type Mappings**: Removed redundant `hierarchy_level` column, now uses FK to `issuetype_hierarchies`
- **Integration Management**: Consolidated into migration and reset_database scripts
- **Permission System**: Role-based with resource-action granularity

### **Recent Critical Fixes (2025-07-22)**
- **GitHub Checkpoint Recovery**: Fixed critical bug where rate limit exceptions weren't properly saving checkpoint data
- **Nested Pagination Recovery**: Enhanced checkpoint system to handle interruptions during commit/review/comment processing
- **Jira Processor**: Fixed `hierarchy_level` attribute error by updating to use relationship-based access
- **Admin Statistics**: Added missing database tables (relationship tables, user sessions, etc.) to admin page counts
- **Enhanced Deactivation System**: Implemented sophisticated deactivation workflow with dependency management and metrics exclusion strategy
- **Admin Page Authentication**: Fixed Issue Type Hierarchies page authentication by copying proper `getAuthToken()` function from working pages

### **Recent Critical Fixes (2025-07-23)**
- **Session Management Enhancement**: Implemented comprehensive session termination and validation system with automatic redirect on session expiry
- **Self-Termination Detection**: Added special handling for users terminating their own sessions with immediate redirect and cleanup
- **Active Sessions Management**: Added admin interface for viewing and managing all active user sessions with individual and bulk termination
- **Enhanced Authentication Error Handling**: Implemented `authenticatedFetch()` wrapper for consistent 401 response handling across all admin functions
- **Session Termination Security Fix**: Fixed critical issue where JWT tokens remained valid after session termination by adding `active` field check in token verification
- **Frontend Flash Prevention**: Added loading screen and immediate session validation to prevent flash of content before redirect on invalid sessions
- **Role-Based Access Control**: Implemented comprehensive RBAC for health endpoints and API documentation with proper UI hiding for non-admin users
- **Session Invalidation Fix**: Enhanced logout process to properly invalidate sessions in database, not just clear client-side storage
- **Smart Redirect Logic**: Fixed redirect behavior so authenticated users accessing forbidden resources go to dashboard (not login) with clear error messages
- **System Health UI Protection**: Hidden System Health section from non-admin users to prevent API errors and improve UX

## 🔧 **Development Workflow Standards**

### **Code Changes**
1. **Database First**: Always update models before API endpoints
2. **Migration Strategy**: Use raw SQL migrations for production control and properly update the reset_databse.py inside the /services/etl-service/scripts folder
3. **API Consistency**: Follow existing patterns for CRUD operations
4. **Error Handling**: Implement proper exception handling and user-friendly messages
5. **Testing**: Always suggest testing after code changes

### **Documentation Standards**
1. **Single Source of Truth**: Avoid duplicate documentation
2. **Clear Hierarchy**: Platform docs in `/docs`, service docs in `/services/[service]/docs/`
3. **Descriptive Names**: Use `[TOPIC]_GUIDE.md` format, avoid generic `README.md` in subdirectories
4. **Cross-References**: Always update related documentation when making changes
5. **Current Information**: Keep documentation synchronized with code changes

## 🧪 **Testing and Cleanup Guidelines**

### **Test Script Management**
1. **Default Behavior**: Always delete test scripts after execution unless explicitly asked to keep them
2. **Temporary Files**: Clean up any temporary files created during development
3. **Workspace Hygiene**: Keep the workspace clean and organized
4. **Exception**: Only keep test files when user explicitly requests it or for permanent test suites

### **Development Testing**
1. **Incremental Testing**: Test individual components before full integration
2. **Database Testing**: Use `reset_database.py --all` for clean development environments
3. **API Testing**: Use `test_jobs.py` for ETL job testing and debugging
4. **Connection Testing**: Always verify API connections before job execution

## 📊 **ETL Service Specifics**

### **Job Management**
1. **Orchestration**: Jobs use a 60-minute main orchestrator with retry mechanisms
2. **Recovery Strategy**: Failed jobs can trigger shorter-interval retry orchestrators
3. **Enhanced Checkpointing**: GitHub job supports multi-level checkpoint-based recovery:
   - **PR-level recovery**: Resume from specific pull request pagination cursor
   - **Nested recovery**: Resume from commit, review, or comment pagination within a PR
   - **Rate limit resilience**: Automatic checkpoint saves when API limits are hit
   - **Complete state preservation**: No data loss during interruptions
4. **Cancellation**: Implement cancellation checks in long-running operations
5. **Status Management**: Use proper job state transitions (PENDING → RUNNING → FINISHED/FAILED)

### **Deactivation and Metrics Strategy**
1. **Deactivation Philosophy**: Records are deactivated (active=False) rather than deleted to preserve referential integrity
2. **Metrics Exclusion Rule**: ALL metrics calculations must exclude data connected to deactivated records at ANY level
3. **Relationship Chain Filtering**: If a flow step is deactivated, exclude all issues → statuses → status mappings → flow step
4. **Data Quality Separation**: Provide separate views for data quality analysis that include inactive records
5. **User Control**: Enhanced deactivation modals allow users to choose dependency handling strategies

### **Data Processing**
1. **Pagination**: Always implement pagination for large datasets
2. **Rate Limiting**: Respect API rate limits with proper backoff strategies
3. **Data Validation**: Validate data integrity before database insertion
4. **Error Recovery**: Implement graceful error handling and recovery mechanisms
5. **Logging**: Use structured logging with appropriate log levels

## 🎨 **Frontend Development**

### **UI Consistency for ETL Service**
1. **Dark Theme**: All modals and admin interfaces use dark theme (`#1a1a1a` background)
2. **Bootstrap 5**: Use Bootstrap 5 components and utilities consistently
3. **Icon Standards**: Use Font Awesome 6 icons throughout
4. **Color Coding**: Implement consistent color schemes (e.g., level badges: blue/green/red)
5. **Responsive Design**: Ensure mobile-friendly layouts

### **Admin Interface Standards for ETL Service**
1. **CRUD Operations**: Follow established patterns for create/read/update/delete
2. **Search and Filter**: Implement real-time search and filtering capabilities
3. **Sortable Tables**: Make table columns sortable where appropriate
4. **Confirmation Dialogs**: Always confirm destructive operations
5. **Usage Validation**: Prevent deletion of records that are referenced by others

## 🔒 **Security and Permissions**

### **Authentication**
1. **Token-Based**: Use Bearer tokens for API authentication
2. **Session Management**: Implement proper session handling and expiration
3. **Permission Checks**: Always verify permissions before allowing operations
4. **Client Isolation**: Ensure users only access their client's data
5. **Audit Logging**: Log all administrative actions

### **Role-Based Access Control (RBAC)**
1. **Admin-Only Features**: Health endpoints (`/api/v1/health`), API docs (`/docs`), and System Health UI section are restricted to admin users only
2. **UI Element Hiding**: Non-admin users don't see menu items or UI sections they can't access (prevents confusion and API errors)
3. **Server-Side Protection**: All restricted endpoints have proper authentication middleware protection, not just UI hiding
4. **Smart Redirects**: Authenticated users accessing forbidden resources are redirected to dashboard (not login) with clear error messages
5. **Session Invalidation**: Logout properly invalidates sessions in database, not just client-side cleanup
6. **Access Matrix**:
   - **Anonymous**: No access to protected features, redirected to login
   - **View/User**: Dashboard access only, no admin features
   - **Admin**: Full access to all features including health monitoring and API documentation

### **Data Protection**
1. **Encryption**: Encrypt sensitive data like API tokens
2. **Input Validation**: Validate and sanitize all user inputs
3. **SQL Injection**: Use parameterized queries and ORM methods
4. **CORS**: Configure CORS properly for cross-origin requests
5. **Environment Variables**: Never hardcode sensitive information

## 📁 **File Organization**

### **Documentation Structure**
```
/README.md                           # Main application overview
/docs/
├── DOCUMENTATION_INDEX.md           # Navigation index
├── AGENT_GUIDANCE.md               # This document
├── ARCHITECTURE.md                 # System architecture
├── MIGRATION_GUIDE.md              # Database migrations
└── SCRIPTS_GUIDE.md                # Cross-service scripts

/services/[service]/
├── README.md                       # Service overview
└── docs/                          # Service-specific documentation
```

### **Code Organization**
1. **Service Boundaries**: Keep service-specific code within service directories
2. **Shared Utilities**: Cross-service utilities in `/scripts`
3. **Configuration**: Environment-based configuration with `.env` files
4. **Migrations**: Database migrations in `/scripts/migrations`
5. **Documentation**: Follow the established hierarchy

## 🚨 **Common Pitfalls to Avoid**

### **Database Issues**
1. **Don't**: Store redundant data that can be derived from relationships
2. **Don't**: Use string matching for relationships (use FKs)
3. **Don't**: Skip transaction management in migrations
4. **Don't**: Forget to flush sessions when querying newly created records
5. **Don't**: Ignore foreign key constraints

### **API Development**
1. **Don't**: Skip authentication and permission checks
2. **Don't**: Return sensitive information in API responses
3. **Don't**: Ignore error handling and user feedback
4. **Don't**: Forget to validate input data
5. **Don't**: Use inconsistent response formats

### **Documentation**
1. **Don't**: Create duplicate documentation
2. **Don't**: Use generic names like `README.md` in subdirectories
3. **Don't**: Forget to update cross-references when moving files
4. **Don't**: Leave outdated information in documentation
5. **Don't**: Skip documentation updates when changing code

### **Frontend Development**
1. **Don't**: Create inconsistent admin page layouts - follow the established card-based design pattern
2. **Don't**: Forget to add new admin pages to all navigation menus across admin templates
3. **Don't**: Use different authentication patterns - always copy from working admin pages
4. **Don't**: Skip the middleware protection check - ensure all admin routes are properly protected
5. **Don't**: Create custom styling that breaks the design system - use existing Bootstrap classes

### **Authentication in Admin Pages**
1. **CRITICAL**: Always copy the `getAuthToken()` function from working admin pages (e.g., Flow Steps)
2. **Don't**: Create custom authentication logic that only checks localStorage
3. **Do**: Use the standard pattern that checks both localStorage AND cookies
4. **Template**: Copy this exact `getAuthToken()` function for new admin pages:
   ```javascript
   function getAuthToken() {
       // Try localStorage first (for compatibility)
       let token = localStorage.getItem('pulse_token') || localStorage.getItem('token');
       // If not in localStorage, try to get from cookie
       if (!token) {
           const cookies = document.cookie.split(';');
           for (let cookie of cookies) {
               const [name, value] = cookie.trim().split('=');
               if (name === 'pulse_token' || name === 'access_token') {
                   token = value;
                   break;
               }
           }
       }
       return token;
   }
   ```
5. **Why**: The authentication system uses cookies (`pulse_token`), not localStorage. Pages that only check localStorage will fail authentication even when users are properly logged in.

### **Session Management and Termination (2025-07-23)**
1. **Automatic Session Validation**: Implement periodic session validation (every 30 seconds) to detect expired sessions
2. **Self-Termination Detection**: Always check if a user is terminating their own session and provide appropriate warnings
3. **Immediate Redirect**: When a user terminates their own session, redirect immediately to login page with session cleanup
4. **Enhanced Error Handling**: Use `authenticatedFetch()` wrapper for consistent 401 response handling across all API calls
5. **Visual Indicators**: Highlight current user's session in admin tables with "YOU" badge and warning background
6. **Session Cleanup**: Always clear localStorage, cookies, and stop validation intervals on logout/redirect
7. **Template Pattern**: For session management in admin pages, use this pattern:
   ```javascript
   // Session validation with automatic redirect
   async function validateSession() {
       const response = await fetch('/api/v1/admin/stats', {
           headers: { 'Authorization': `Bearer ${getAuthToken()}` }
       });
       if (response.status === 401) {
           redirectToLogin('Session expired or invalid');
           return false;
       }
       return response.ok;
   }

   // Clean redirect function
   function redirectToLogin(reason) {
       localStorage.removeItem('pulse_token');
       document.cookie = 'pulse_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
       clearInterval(sessionValidationInterval);
       window.location.href = `/login?error=session_expired&reason=${encodeURIComponent(reason)}`;
   }

   // Enhanced fetch with auth handling
   async function authenticatedFetch(url, options = {}) {
       const token = getAuthToken();
       if (!token) { redirectToLogin('No token'); return null; }
       const response = await fetch(url, {
           ...options,
           headers: { ...options.headers, 'Authorization': `Bearer ${token}` }
       });
       if (response.status === 401) { redirectToLogin('Session invalid'); return null; }
       return response;
   }
   ```
8. **Why**: Users expect immediate feedback when their session is terminated, and automatic redirect when sessions expire during normal usage.

### **Proper Logout Implementation (2025-07-23)**
1. **Multi-Step Process**: Logout must invalidate sessions both client-side AND server-side
2. **API Call First**: Always call `/auth/logout` API endpoint to invalidate session in database
3. **Client Cleanup**: Clear localStorage tokens and cookies after API call
4. **Graceful Degradation**: Continue with client cleanup even if API call fails
5. **Template Pattern**: Use this logout function pattern:
   ```javascript
   async function logout() {
       try {
           // First, call API logout to invalidate session in database
           const token = getAuthToken();
           if (token) {
               await fetch('/auth/logout', {
                   method: 'POST',
                   headers: {
                       'Authorization': `Bearer ${token}`,
                       'Content-Type': 'application/json'
                   }
               });
           }
       } catch (error) {
           console.warn('API logout failed, proceeding with client-side cleanup:', error);
       }

       // Clear localStorage
       localStorage.removeItem('pulse_token');

       // Call server-side logout to clear cookies properly
       window.location.href = '/logout';
   }
   ```
6. **Why**: Prevents session reuse with old tokens and ensures proper security cleanup

### **Smart Redirect Logic (2025-07-23)**
1. **Authentication vs Authorization**: Distinguish between "not logged in" and "not authorized"
2. **Redirect Rules**:
   - **Anonymous users** → Login page (`/login?error=authentication_required`)
   - **Authenticated users without permission** → Dashboard (`/dashboard?error=permission_denied&resource=X`)
3. **Error Message Display**: Dashboard should detect URL error parameters and show user-friendly messages
4. **URL Cleanup**: Remove error parameters from URL after displaying message (without page reload)
5. **Template Pattern**: For permission-denied redirects in server code:
   ```python
   # WRONG - sends authenticated users to login
   return RedirectResponse(url="/login?error=permission_denied", status_code=302)

   # CORRECT - keeps authenticated users in dashboard context
   return RedirectResponse(url="/dashboard?error=permission_denied&resource=docs", status_code=302)
   ```
6. **Why**: Authenticated users should stay in the authenticated context, not be kicked back to login unnecessarily

### **ETL/Job Development**
1. **Don't**: Return empty `checkpoint_data: {}` in exception handlers - always include relevant checkpoint information
2. **Don't**: Forget to save checkpoints immediately when rate limits are hit during nested processing
3. **Don't**: Access removed model attributes (e.g., `hierarchy_level` on `IssuetypeMapping`) - use relationships instead
4. **Don't**: Skip nested pagination checkpoint saves - interruptions can happen at any level
5. **Don't**: Forget to include all database tables in admin statistics - missing tables create incomplete reporting

### **Metrics and Analytics Development**
1. **CRITICAL**: Always exclude deactivated records from metrics calculations at ALL levels of the relationship chain
2. **Don't**: Include issues linked to deactivated flow steps, status mappings, or issue type hierarchies in metrics
3. **Don't**: Calculate metrics on data connected to inactive configuration records
4. **Do**: Implement proper active-only filtering in all analytical queries
5. **Do**: Provide separate "data quality" views that include inactive records for troubleshooting

## 🎯 **Best Practices Summary**

### **Before Starting Work**
1. Read this document completely
2. Understand the current system architecture
3. Check existing patterns and follow them
4. Verify database schema and relationships
5. Review related documentation

### **During Development**
1. Follow established coding patterns
2. Implement proper error handling
3. Add appropriate logging
4. Test incrementally
5. Keep workspace clean

### **After Completing Work**
1. Update relevant documentation
2. Clean up test files (unless requested to keep)
3. Verify all cross-references are correct
4. Suggest testing to the user
5. Ensure code follows project standards

## 🔄 **Continuous Improvement**

### **Learning from Changes**
1. Document significant architectural decisions
2. Update this guidance based on new discoveries
3. Share knowledge about effective patterns
4. Identify and eliminate anti-patterns
5. Maintain consistency across the platform

### **Agent Collaboration**
1. Follow established patterns from previous agents
2. Build upon existing work rather than recreating
3. Maintain consistency in approach and style
4. Document new patterns for future agents
5. Respect the existing architecture and design decisions

---

**Remember**: This platform has evolved through careful architectural decisions. Respect the existing patterns, maintain consistency, and always prioritize data integrity and user experience.

**For detailed technical information, see**: [Documentation Index](DOCUMENTATION_INDEX.md)
