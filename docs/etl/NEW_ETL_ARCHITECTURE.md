# New ETL Architecture - Migration Guide

**⚠️ IMPORTANT: This document tracks the migration from the old ETL service to the new ETL architecture**

## 🏗️ Architecture Overview

### Old ETL Service (Legacy - Being Phased Out)
**Location**: `services/etl-service/`
- **Type**: Monolithic Python backend with Jinja2 templates
- **Frontend**: Server-side rendered HTML templates
- **Backend**: FastAPI with integrated frontend
- **Port**: 8002
- **Status**: ⚠️ **LEGACY - DO NOT MODIFY** (kept as reference/backup)

### New ETL Architecture (Current Development)
**Locations**: 
- **Frontend**: `services/etl-frontend/` (React/TypeScript)
- **Backend**: `services/backend-service/app/etl/` (FastAPI endpoints)

#### New Frontend (`etl-frontend`)
- **Framework**: React 18 + TypeScript + Vite
- **Port**: 5174 (development)
- **Styling**: Tailwind CSS with custom design system
- **State Management**: React Context (Auth, Theme)
- **Routing**: React Router v6
- **Features**:
  - ✅ Modern React components
  - ✅ Dark/Light mode support
  - ✅ Responsive design
  - ✅ Real-time job status updates
  - ✅ Integration logo auto-inversion for dark mode
  - ✅ Job cards with uppercase names
  - ✅ Collapsible sidebar navigation
  - ✅ Toast notifications
  - ✅ Modal dialogs for job details

#### New Backend (`backend-service/app/etl/`)
- **Framework**: FastAPI (integrated with main backend service)
- **Port**: 3001 (shared with main backend)
- **Base Path**: `/app/etl/`
- **Features**:
  - ✅ RESTful API endpoints
  - ✅ Tenant isolation
  - ✅ JWT authentication
  - ✅ Job management APIs
  - ✅ Integration management APIs
  - ✅ Status/hierarchy/workflow APIs

## 📋 Migration Status

### ✅ Completed Features (New ETL)

#### Frontend Pages
- ✅ **Home Page** (`/`) - Job cards with status, controls, and details
- ✅ **Work Item Types** (`/wits`) - WIT management with CRUD operations
- ✅ **Hierarchies** (`/hierarchies`) - Hierarchy level management
- ✅ **Statuses** (`/statuses`) - Status management with mappings
- ✅ **Workflows** (`/workflows`) - Workflow management
- ✅ **Integrations** (`/integrations`) - Integration provider management
- ✅ **Qdrant** (`/qdrant`) - Vector database management

#### Components
- ✅ **Header** - Tenant logo, theme toggle, user menu
- ✅ **CollapsedSidebar** - Navigation with icons and tooltips
- ✅ **JobCard** - Job display with status, actions, and countdown
- ✅ **IntegrationLogo** - Auto-inverting logos for dark mode
- ✅ **JobDetailsModal** - Generic job details modal
- ✅ **JiraJobDetailsModal** - Jira-specific job details
- ✅ **GitHubJobDetailsModal** - GitHub-specific job details
- ✅ **FabricJobDetailsModal** - Fabric-specific job details
- ✅ **ADJobDetailsModal** - AD-specific job details
- ✅ **JobSettingsModal** - Job schedule/retry configuration
- ✅ **ToastContainer** - Toast notifications
- ✅ **CreateModal** - Generic create modal
- ✅ **EditModal** - Generic edit modal
- ✅ **DependencyModal** - Dependency handling modal

#### Backend Endpoints
- ✅ **Jobs API** (`/app/etl/jobs/`)
  - GET `/jobs` - List all jobs
  - GET `/jobs/{job_id}` - Get job details
  - POST `/jobs/{job_id}/run` - Trigger job execution
  - POST `/jobs/{job_id}/toggle` - Toggle job active status
  - POST `/jobs/{job_id}/settings` - Update job settings
  - POST `/jobs/{job_id}/force-pending` - Force job to pending status

- ✅ **Integrations API** (`/app/etl/integrations/`)
  - GET `/integrations` - List all integrations
  - POST `/integrations` - Create integration
  - PUT `/integrations/{id}` - Update integration
  - DELETE `/integrations/{id}` - Delete integration
  - POST `/integrations/{id}/toggle` - Toggle integration active status

- ✅ **WITs API** (`/app/etl/wits/`)
- ✅ **Hierarchies API** (`/app/etl/hierarchies/`)
- ✅ **Statuses API** (`/app/etl/statuses/`)
- ✅ **Workflows API** (`/app/etl/workflows/`)
- ✅ **Qdrant API** (`/app/etl/qdrant/`)

### 🚧 In Progress / Pending Features

#### Job Execution Engine
- ⚠️ **CHECK OLD ETL**: `services/etl-service/app/jobs/`
  - `jira_job.py` - Jira extraction logic
  - `github_job.py` - GitHub extraction logic
  - `vectorization_job.py` - Vectorization processing
  - `orchestrator.py` - Job orchestration logic

- 🔄 **NEW ARCHITECTURE PLAN**: RabbitMQ-based queue system
  - Extract phase: Push data to queue
  - Transform phase: Workers consume from queue
  - Load phase: Bulk insert to database
  - Vectorization phase: Queue for embedding generation

#### Job Details & Progress
- ⚠️ **CHECK OLD ETL**: `services/etl-service/app/templates/components/`
  - Job progress bars
  - Step-by-step progress tracking
  - Real-time status updates
  - Error message display

- 🔄 **NEW IMPLEMENTATION**: WebSocket-based progress updates
  - Event-driven progress notifications
  - Batched progress updates (every N items)
  - No active polling from frontend

#### Recovery & Checkpointing
- ⚠️ **CHECK OLD ETL**: `services/etl-service/app/core/`
  - `checkpoint_manager.py` - Checkpoint handling
  - `recovery_manager.py` - Recovery logic
  - Cursor-based pagination for GitHub
  - Date-based incremental sync for Jira

- 🔄 **NEW IMPLEMENTATION**: Database-driven checkpoints
  - `checkpoint_data` JSONB column in `etl_jobs` table
  - `last_run_started_at` for recovery mode
  - `last_success_at` for normal incremental sync

#### Orchestrator
- ⚠️ **CHECK OLD ETL**: `services/etl-service/app/jobs/orchestrator.py`
  - Job sequencing logic
  - Fast retry timing (15 min job-to-job)
  - Normal interval (1 hour cycle restart)
  - Active/inactive job filtering

- 🔄 **NEW IMPLEMENTATION**: Scheduled task (no database entry)
  - Respects `active` field on jobs and integrations
  - Skips paused jobs
  - Sets next job to READY with appropriate timing

## 🎨 UI/UX Enhancements (New ETL Only)

### Design System
- **Color Scheme**: CSS variables for theming (`--color-1` through `--color-5`)
- **Gradients**: Diagonal gradients with `--gradient-1-2`, `--on-gradient-1-2`
- **Dark Mode**: Subtle shadows (0.03 opacity vs 0.1 in light mode)
- **Typography**: Uppercase job names for consistency
- **Icons**: Lucide React icons throughout
- **Animations**: Framer Motion for smooth transitions

### Logo Handling
- **Auto-Inversion**: Dark logos automatically inverted to white in dark mode
- **Luminance Detection**: Calculates logo brightness and applies filter
- **Threshold**: 0.5 luminance threshold for inversion decision
- **No Debug Logs**: Console logs removed for production

### Layout
- **Fixed Header**: 72px minimum height to prevent layout shift
- **Fixed Logo Container**: 120px width to prevent logo movement
- **Sticky Elements**: Header and sidebar stay visible on scroll
- **Responsive**: Mobile-friendly with collapsible sidebar

## 📁 File Structure Comparison

### Old ETL Service
```
services/etl-service/
├── app/
│   ├── jobs/                    # Job execution logic
│   │   ├── jira_job.py
│   │   ├── github_job.py
│   │   ├── vectorization_job.py
│   │   └── orchestrator.py
│   ├── core/                    # Core utilities
│   │   ├── checkpoint_manager.py
│   │   ├── recovery_manager.py
│   │   └── settings_manager.py
│   ├── templates/               # Jinja2 HTML templates
│   │   ├── home.html
│   │   ├── components/
│   │   └── layouts/
│   ├── static/                  # CSS, JS, images
│   └── main.py                  # FastAPI app
└── requirements.txt
```

### New ETL Architecture
```
services/etl-frontend/           # React frontend
├── src/
│   ├── components/              # React components
│   │   ├── Header.tsx
│   │   ├── CollapsedSidebar.tsx
│   │   ├── JobCard.tsx
│   │   ├── IntegrationLogo.tsx
│   │   └── *Modal.tsx
│   ├── pages/                   # Page components
│   │   ├── HomePage.tsx
│   │   ├── WitsPage.tsx
│   │   ├── StatusesPage.tsx
│   │   └── ...
│   ├── contexts/                # React contexts
│   │   ├── AuthContext.tsx
│   │   └── ThemeContext.tsx
│   ├── hooks/                   # Custom hooks
│   │   ├── useToast.ts
│   │   └── useLogoFilter.ts
│   ├── utils/                   # Utilities
│   │   └── imageColorUtils.ts
│   └── index.css                # Tailwind CSS
├── public/
│   └── assets/
│       └── integrations/        # Integration logos
└── package.json

services/backend-service/app/etl/  # Backend endpoints
├── jobs.py                      # Job management endpoints
├── integrations.py              # Integration endpoints
├── wits.py                      # WIT endpoints
├── hierarchies.py               # Hierarchy endpoints
├── statuses.py                  # Status endpoints
├── workflows.py                 # Workflow endpoints
└── qdrant.py                    # Qdrant endpoints
```

## 🔄 Migration Checklist

### For Developers
When implementing new features, always:

1. ✅ **Check Old ETL First**
   - Review `services/etl-service/` for existing implementation
   - Understand the business logic and edge cases
   - Note any special handling or workarounds

2. ✅ **Implement in New Architecture**
   - Frontend: Add to `services/etl-frontend/`
   - Backend: Add to `services/backend-service/app/etl/`
   - Never modify `services/etl-service/` (legacy backup)

3. ✅ **Follow New Patterns**
   - Use React components, not Jinja2 templates
   - Use REST APIs, not server-side rendering
   - Use TypeScript for type safety
   - Use Tailwind CSS for styling

4. ✅ **Test Thoroughly**
   - Test in both light and dark modes
   - Test with different tenant configurations
   - Test error handling and edge cases
   - Verify responsive design

## 📝 Notes for New Developers

### Starting Development
```bash
# Old ETL (DO NOT USE FOR NEW FEATURES)
cd services/etl-service
# Just for reference - don't start this service

# New ETL Frontend
cd services/etl-frontend
npm install
npm run dev  # Runs on http://localhost:5174

# Backend (already running)
cd services/backend-service
# Backend runs on http://localhost:3001
# ETL endpoints are at /app/etl/*
```

### Key Differences
| Aspect | Old ETL | New ETL |
|--------|---------|---------|
| Frontend | Jinja2 templates | React + TypeScript |
| Backend | Monolithic FastAPI | Modular FastAPI endpoints |
| Styling | Custom CSS | Tailwind CSS |
| State | Server-side | React Context |
| API | Integrated | RESTful |
| Port | 8002 | 5174 (dev), 3001 (backend) |
| Status | Legacy | Active Development |

### Common Pitfalls
- ❌ Don't modify `services/etl-service/` - it's legacy
- ❌ Don't mix old and new ETL code
- ❌ Don't forget to check old ETL for business logic
- ✅ Always implement in new architecture
- ✅ Always test in both themes
- ✅ Always use TypeScript types

## 🎯 Future Roadmap

### Phase 1: Core Migration (Current)
- ✅ Basic UI pages and components
- ✅ Job management APIs
- ✅ Integration management
- 🔄 Job execution engine with RabbitMQ

### Phase 2: Advanced Features
- ⏳ Real-time progress tracking
- ⏳ WebSocket integration
- ⏳ Advanced error handling
- ⏳ Retry mechanisms

### Phase 3: Optimization
- ⏳ Performance tuning
- ⏳ Caching strategies
- ⏳ Database optimization
- ⏳ Load testing

### Phase 4: Decommission Old ETL
- ⏳ Full feature parity achieved
- ⏳ Production validation complete
- ⏳ Remove `services/etl-service/`
- ⏳ Update all documentation

---

**Last Updated**: 2025-10-02
**Status**: Active Development
**Contact**: Development Team

