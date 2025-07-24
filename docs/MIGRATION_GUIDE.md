# Database Migration System Guide

This guide covers the SQL-based migration system for managing database schema changes across environments.

## Overview

The migration system provides a robust, SQL-based approach to database schema management that:

- ✅ Uses raw SQL statements for maximum control and portability
- ✅ Supports both forward (apply) and backward (rollback) operations
- ✅ Tracks migration history and status
- ✅ Provides atomic transaction-based operations
- ✅ Works across different database systems

## Directory Structure

```
scripts/
├── migration_runner.py         # Migration execution utility (cross-service)
├── migrations/                  # Database migration system
│   ├── 001_initial_schema.py  # Initial database schema migration
│   └── [future migrations]    # Additional numbered migrations
└── utilities/                  # Cross-service utility scripts
    └── [future utilities]     # Planned cross-service scripts
```

## Migration File Structure

Each migration file follows this pattern:

```python
"""
Migration: 001 - Initial Schema
Description: Creates all initial tables and inserts seed data
"""

def apply(connection):
    """Apply the migration (forward)"""
    # SQL statements to apply changes
    pass

def rollback(connection):
    """Rollback the migration (backward)"""
    # SQL statements to revert changes
    pass

if __name__ == "__main__":
    # Command line interface for individual migration
    pass
```

## Usage

### Individual Migration

```bash
# Apply migration
python scripts/migrations/001_initial_schema.py --apply

# Rollback migration
python scripts/migrations/001_initial_schema.py --rollback

# Check migration status
python scripts/migrations/001_initial_schema.py --status
```

### Migration Runner

```bash
# Apply all pending migrations
python scripts/migration_runner.py --apply-all

# Rollback to specific migration
python scripts/migration_runner.py --rollback-to 001

# Show migration status
python scripts/migration_runner.py --status
```

## Database Connection

Migrations use the same database configuration as the ETL service:
- Connection details from environment variables
- Automatic transaction management
- Error handling and rollback on failure

## Best Practices

1. **Test thoroughly** - Always test on development data first
2. **Atomic operations** - Use transactions for all-or-nothing changes
3. **Backup first** - Create database backups before production migrations
4. **Document changes** - Include clear descriptions and comments
5. **Rollback ready** - Ensure every migration can be safely reverted

## Quick Start

### 1. Apply Initial Schema

```bash
# Apply the initial database schema and seed data
python scripts/migrations/001_initial_schema.py --apply

# Check if migration was applied successfully
python scripts/migrations/001_initial_schema.py --status
```

### 2. Using Migration Runner

```bash
# Show status of all migrations
python scripts/migration_runner.py --status

# Apply all pending migrations
python scripts/migration_runner.py --apply-all

# Rollback to a specific migration
python scripts/migration_runner.py --rollback-to 001
```

## Migration System Features

### Individual Migration Management

Each migration file is self-contained and can be run independently:

```bash
# Apply a specific migration
python scripts/migrations/001_initial_schema.py --apply

# Rollback a specific migration
python scripts/migrations/001_initial_schema.py --rollback

# Check migration status
python scripts/migrations/001_initial_schema.py --status
```

### Centralized Migration Runner

The migration runner provides system-wide migration management:

- **Status Tracking**: Shows which migrations are applied/pending
- **Batch Operations**: Apply multiple migrations in sequence
- **Rollback Management**: Safely rollback to any previous state
- **History Tracking**: Maintains detailed migration history

### Migration History Tracking

The system automatically tracks migration state in the `migration_history` table:
- **Migration Records**: Each migration creates a record when applied
- **Applied Timestamps**: Exact time when migration was applied
- **Status Tracking**: 'applied' or 'rolled_back' status
- **Rollback Handling**: Complete rollback drops migration_history table
- **Fallback Detection**: Can detect applied migrations even without history table

#### Migration History Table Structure:
```sql
CREATE TABLE migration_history (
    id SERIAL PRIMARY KEY,
    migration_number VARCHAR(10) UNIQUE NOT NULL,
    migration_name VARCHAR(255) NOT NULL,
    applied_at TIMESTAMP DEFAULT NOW(),
    rollback_at TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'applied'
);
```

## Database Schema Created

The initial migration (001) creates:

### Core Tables
- `clients` - Client organization management
- `users` - User authentication and management
- `user_sessions` - JWT session management
- `user_permissions` - Fine-grained access control
- `integrations` - External system integrations (Jira, GitHub, etc.)
- `projects` - Project management

### Workflow Tables
- `flow_steps` - Standardized workflow steps
- `status_mappings` - Maps raw statuses to flow steps
- `issuetype_mappings` - Maps raw issue types to standardized types
- `issuetypes` - Issue type definitions
- `statuses` - Status definitions

### Data Tables
- `issues` - Main issues table with 20 custom fields and workflow analysis columns
- `issue_changelogs` - Issue change history tracking
- `repositories` - Git repository metadata
- `pull_requests` - Pull request data with review metrics
- `pull_request_reviews` - PR review submissions
- `pull_request_commits` - Individual commits in PRs
- `pull_request_comments` - PR discussion comments
- `jira_pull_request_links` - Links between Jira issues and PRs

### System Tables
- `system_settings` - Application configuration
- `job_schedules` - ETL job orchestration
- `migration_history` - Migration tracking

### Relationship Tables
- `projects_issuetypes` - Project-issuetype relationships
- `projects_statuses` - Project-status relationships

### Indexes and Constraints
- Primary keys on all tables
- Foreign key constraints for data integrity
- Performance indexes on frequently queried columns
- Unique constraints on external IDs and keys

### Seed Data
- WEX client configuration
- Complete workflow flow steps (12 steps: Backlog → Done)
- Comprehensive status mappings (50+ mappings)
- Complete issuetype mappings (27+ mappings with hierarchy levels)

## Migration vs Reset Database

### Migration System (Recommended for Production)
```bash
python scripts/migrations/001_initial_schema.py --apply
```

**Advantages:**
- ✅ Production-ready with proper transaction handling
- ✅ Rollback capability for safe operations
- ✅ Migration history tracking
- ✅ Raw SQL for maximum control
- ✅ Database-agnostic approach

### Reset Database (Development Only)
```bash
python services/etl-service/scripts/reset_database.py
```

**Advantages:**
- ✅ Quick development setup
- ✅ SQLAlchemy convenience methods
- ✅ Integrated with ETL service

**Limitations:**
- ❌ No rollback capability
- ❌ No migration tracking
- ❌ Drops all data
- ❌ Development-focused only

## Best Practices

### For Development
1. Use migration system for schema changes
2. Test migrations on sample data first
3. Always create rollback procedures
4. Document breaking changes

### For Production
1. **Always backup** database before migrations
2. **Test migrations** on staging environment first
3. **Use transactions** for atomic operations
4. **Monitor migration** execution and performance
5. **Have rollback plan** ready before applying

### Creating New Migrations
1. Number sequentially: `002_add_new_feature.py`
2. Include both `apply()` and `rollback()` functions
3. Use raw SQL statements for compatibility
4. Test both forward and backward operations
5. Document any manual steps required

## Troubleshooting

### Migration Fails
1. Check database connection and permissions
2. Review error messages for SQL issues
3. Verify migration dependencies
4. Use rollback to return to known good state

### Rollback Issues
1. Ensure rollback SQL is correct
2. Check for data dependencies
3. Verify foreign key constraints
4. Consider manual cleanup if needed

### Status Inconsistencies
1. Check migration_history table directly
2. Verify actual table existence
3. Use migration runner status for overview
4. Manually update migration_history if needed

## Future Enhancements

- **Dependency Management**: Handle migration dependencies
- **Data Migrations**: Support for data transformation migrations
- **Environment-Specific**: Different migrations for different environments
- **Validation**: Pre/post migration validation checks
- **Backup Integration**: Automatic backup before migrations
