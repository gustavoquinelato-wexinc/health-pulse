# Comprehensive AI Development Guide for Pulse Platform

**Essential guidance for AI assistants working on the Pulse Platform codebase**

## 🎯 Platform Overview

### Architecture Summary
- **Frontend**: React/TypeScript (Port 3000) - Executive dashboards, DORA metrics, responsive UI
- **Backend Service**: FastAPI (Port 3001) - User management, API gateway, authentication, analytics
- **ETL Service**: FastAPI (Port 8000) - Data processing, job orchestration, integrations
- **Auth Service**: FastAPI (Port 4000) - Centralized authentication, OAuth-like flow
- **Database**: PostgreSQL primary (5432) + replica (5433) with streaming replication
- **Cache**: Redis (6379) for sessions and caching

### Service Communication Flow
```
Frontend → Backend Service ← ETL Service
    ↓           ↓              ↓
    Auth Service → Database (Primary/Replica)
```

## 🔧 Development Standards

### Documentation Standards (Updated 2025-01-07)
- **Naming Convention**: All documentation uses lowercase with hyphens (e.g., `architecture.md`, `security-authentication.md`)
- **Location**: Core docs in `/docs/`, service-specific docs in `services/*/docs/`
- **Cross-References**: Always use lowercase file names in links
- **Consolidated Security**: All security content is in `docs/security-authentication.md`

### Environment Configuration
- **Root `.env`**: Used by Docker Compose, startup scripts, and service configuration loading
- **Service-Specific**: Each service can have its own `.env` but prioritizes root-level configuration
- **Multi-Instance**: Use `CLIENT_NAME` environment variable for client-specific ETL instances

### Database Patterns
- **Client Isolation**: ALL tables include `client_id` for multi-tenant separation
- **Queries**: Always filter by `client_id` in database operations
- **Migrations**: Update existing migration 001 instead of creating new migrations
- **Deactivated Records**: Exclude data connected to deactivated records at ANY level

### Authentication & Security
- **Centralized Auth**: All authentication flows through Backend Service
- **JWT Tokens**: Include `client_id` in token payload
- **Session Management**: Database-backed sessions with Redis caching
- **Cross-Service**: Services validate tokens through Backend Service, not directly
- **RBAC**: Role-based access control with granular permissions

## 🏗️ Service-Specific Guidelines

### Backend Service (Port 3001)
- **Purpose**: User identity, authentication, permissions ONLY
- **Database**: Primary for writes, replica for analytics reads
- **APIs**: Unified interface for frontend and ETL service
- **Auth**: JWT token validation and session management

### ETL Service (Port 8000)
- **Purpose**: Business data, analytics, job orchestration ONLY
- **Routes**: Use `/home` not `/dashboard`, no `/admin` prefix (entire service is admin-only)
- **Jobs**: NOT_STARTED, PENDING, RUNNING, FINISHED, ERROR, PAUSED statuses
- **Client Context**: Automatic client-specific logging with CLIENT_NAME environment variable
- **Scripts**: Keep `run_etl.py` and `run_etl.bat` - they provide clean shutdown handling

### Frontend (Port 3000)
- **Auth Flow**: JWT token management with shared sessions across services
- **Real-time**: WebSocket integration for live updates
- **Branding**: Client-specific color schemas and logos
- **Navigation**: Home/DORA Metrics/Engineering Analytics/Settings structure

## 🔄 Job Management & Orchestration

### Job Control Patterns
- **Force Stop**: Enable only when job is running, disable others, instant termination
- **State Management**: When one job finishes, keep other job as PAUSED if it was PAUSED
- **Recovery**: Separate 'sleep' orchestrator job for retry configuration (5-30 min intervals)
- **Cancellation**: Add checks at each pagination request for graceful termination

### Job Status Flow
```
NOT_STARTED → PENDING → RUNNING → FINISHED/ERROR
                ↓
              PAUSED (can resume to RUNNING)
```

## 🎨 UI/UX Standards

### Design System
- **Target**: Enterprise B2B SaaS for C-level executives
- **Colors**: 5-color schema (#C8102E, #253746, #00C7B1, #A2DDF8, #FFBF3F)
- **Storage**: Colors in system_settings table with color_schema_mode field
- **Typography**: Inter font, clean minimalism
- **Themes**: Light/dark mode with client customization

### Component Standards
- **Modals**: Consistent black/dark background style
- **Buttons**: Universal CRUD colors (btn-crud-create for green, etc.)
- **Controls**: Smaller control buttons than status badges
- **Forms**: Dropdown lists over text inputs for predefined options
- **Headers**: ETL service uses 'PEM' branding, page headers in CAPS

## 📁 File Management Standards

### Test Files
- **Delete After Validation**: Always remove test scripts after execution unless explicitly asked to keep
- **Clean Workspace**: Remove temporary files and maintain clean repository

### Docker Configuration
- **Production Ready**: All Dockerfiles include security best practices (non-root users, health checks)
- **Environment**: Proper environment variable handling
- **Dependencies**: Optimized build process with proper caching

### Requirements Management
- **Centralized**: Use `python scripts/install_requirements.py <service|all>`
- **Virtual Environments**: Per-service isolation
- **Package Managers**: NEVER edit package files manually - always use package managers

## 🔍 Development Workflow

### Before Making Changes
1. **Read Documentation**: Always review `/docs/` for architecture understanding
2. **Codebase Retrieval**: Use for detailed information about code you want to edit
3. **Service Patterns**: Follow established patterns from the guides
4. **Client Context**: Ensure all operations respect client isolation

### Making Edits
1. **Conservative Approach**: Respect existing codebase patterns
2. **Database First**: Design with proper FK relationships
3. **Security**: All ETL functionality requires admin credentials
4. **Testing**: Suggest writing/updating tests after code changes

### Configuration Changes
1. **Environment Variables**: Store in `.env` files, not hardcoded
2. **Database Settings**: Use system_settings table for per-client customization
3. **Service URLs**: Make ETL endpoints configurable via .env

## 🚨 Critical Reminders

### Security
- **Never Commit Secrets**: Use .gitignore and pre-commit hooks
- **Client Isolation**: Every database query must filter by client_id
- **Authentication**: All cross-service communication through Backend Service
- **Permissions**: Validate user permissions for all operations

### Multi-Tenancy
- **Client-Specific Logging**: Separate logs per client across all services
- **Data Isolation**: Complete separation at database, application, and configuration levels
- **Feature Flags**: Client-specific feature enablement
- **Branding**: Per-client logos and color schemes

### Performance
- **Database**: Use replica for read-heavy analytics operations
- **Caching**: Leverage Redis for session and data caching
- **API Limits**: Monitor and respect external API rate limits
- **Resource Usage**: Consider resource usage during large operations

## 📚 Essential Documentation References

### Primary Reading (ALWAYS CONSULT)
- `docs/architecture.md` - System design and topology
- `docs/security-authentication.md` - Security implementation (consolidated)
- `docs/jobs-orchestration.md` - Job management and orchestration
- `docs/system-settings.md` - Configuration reference
- `docs/installation-setup.md` - Setup and deployment

### Service-Specific Guides
- `services/etl-service/docs/development-guide.md` - ETL development and testing
- `services/etl-service/docs/log-management.md` - Logging system
- `services/frontend-app/docs/` - Frontend architecture and design system
- `services/backend-service/README.md` - Backend service capabilities

### Key Architectural Decisions
- Multi-tenant SaaS with complete client isolation
- Centralized authentication with distributed validation
- Primary-replica database setup for performance
- Client-specific logging and configuration
- Enterprise-grade security and RBAC

---

**Remember**: This platform serves enterprise clients with C-level executives. Every decision should reflect enterprise-grade quality, security, and user experience.
