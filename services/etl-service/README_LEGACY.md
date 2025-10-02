# ⚠️ LEGACY ETL SERVICE - DO NOT USE FOR NEW DEVELOPMENT

## 🚨 IMPORTANT NOTICE

**This service is LEGACY and should NOT be modified or used for new feature development.**

### Status: DEPRECATED
- **Last Active**: October 2025
- **Replacement**: New ETL Architecture (see below)
- **Purpose**: Kept as reference and backup only

## 🔄 Migration to New ETL Architecture

All ETL functionality has been migrated to a modern React + FastAPI architecture:

### New ETL Frontend
**Location**: `services/etl-frontend/`
- **Framework**: React 18 + TypeScript + Vite
- **Port**: 5174 (development)
- **Features**: Modern UI, dark mode, responsive design, real-time updates

### New ETL Backend
**Location**: `services/backend-service/app/etl/`
- **Framework**: FastAPI (integrated with main backend)
- **Port**: 3001 (shared with main backend)
- **Base Path**: `/app/etl/*`
- **Features**: RESTful APIs, tenant isolation, JWT auth

## 📚 Documentation

For complete migration guide and new architecture details, see:
- **Migration Guide**: `docs/etl/NEW_ETL_ARCHITECTURE.md`
- **Architecture**: `docs/architecture.md`
- **Jobs & Orchestration**: `docs/jobs-orchestration.md`

## 🚫 What NOT to Do

- ❌ **DO NOT** add new features to this service
- ❌ **DO NOT** modify existing code in this service
- ❌ **DO NOT** start this service in production
- ❌ **DO NOT** reference this service in new documentation

## ✅ What TO Do

- ✅ **DO** check this service for business logic reference when implementing new features
- ✅ **DO** implement all new features in `etl-frontend` + `backend-service/app/etl/`
- ✅ **DO** follow the new architecture patterns
- ✅ **DO** read the migration guide before starting work

## 📁 Reference Structure

This service contains valuable reference implementations:

### Job Execution Logic
- `app/jobs/jira_job.py` - Jira data extraction
- `app/jobs/github_job.py` - GitHub data extraction
- `app/jobs/vectorization_job.py` - Vectorization processing
- `app/jobs/orchestrator.py` - Job orchestration

### Core Utilities
- `app/core/checkpoint_manager.py` - Checkpoint handling
- `app/core/recovery_manager.py` - Recovery logic
- `app/core/settings_manager.py` - Settings management

### Templates (Old UI)
- `app/templates/home.html` - Main dashboard
- `app/templates/components/` - Reusable components
- `app/templates/layouts/` - Page layouts

## 🔍 How to Use This Service (Reference Only)

When implementing a new feature in the new ETL architecture:

1. **Check this service first** for existing business logic
2. **Understand the implementation** and edge cases
3. **Implement in new architecture** using modern patterns
4. **Test thoroughly** in the new system

### Example: Implementing Jira Job in New Architecture

```bash
# 1. Review old implementation
cat services/etl-service/app/jobs/jira_job.py

# 2. Understand the logic
# - How does it handle pagination?
# - What error handling is in place?
# - How does checkpoint/recovery work?

# 3. Implement in new architecture
# Frontend: services/etl-frontend/src/components/JiraJobDetailsModal.tsx
# Backend: services/backend-service/app/etl/jobs.py (Jira endpoints)

# 4. Test in new system
cd services/etl-frontend
npm run dev
```

## 🗑️ Future Decommission

This service will be completely removed once:
- ✅ Full feature parity achieved in new architecture
- ✅ Production validation complete
- ✅ All documentation updated
- ✅ Team trained on new architecture

**Estimated Removal**: Q1 2026

## 📞 Questions?

If you have questions about:
- **Migration**: See `docs/etl/NEW_ETL_ARCHITECTURE.md`
- **New Architecture**: See `docs/architecture.md`
- **Implementation**: Contact the development team

---

**Remember**: This is a LEGACY service. All new development goes to the new ETL architecture!

