# Cross-Services Scripts Guide

This guide covers scripts that operate across multiple services or provide system-wide functionality.

## Directory Structure

```
scripts/
├── install_requirements.py    # Centralized dependency management
├── migration_runner.py        # Migration execution utility (cross-service)
├── migrations/                 # Database migration scripts
│   └── 001_initial_schema.py  # Initial database schema migration
└── utilities/                  # Cross-service utility scripts
    └── [future utilities]      # Planned cross-service scripts
```

## Environment Requirements

### **Service-Specific Environment Files**

Each service now has its own complete environment file with no combination needed:

```bash
# Backend service (includes migration runner)
services/backend-service/.env

# ETL service
services/etl-service/.env

# Frontend service
services/frontend-app/.env
```

### **Migration System Location**

The migration system is now located in the backend service:

- **Migration Runner**: `services/backend-service/scripts/migration_runner.py`
- **Migrations Folder**: `services/backend-service/scripts/migrations/`
- **Configuration**: Uses backend service's own `.env` file

## Migration System

The migration system is now located in the backend service and provides a robust way to manage database schema changes across environments:

- **Forward Migrations**: Apply schema changes and data updates
- **Rollback Migrations**: Safely revert changes when needed
- **SQL-Based**: Uses raw SQL statements for maximum control and portability
- **Version Control**: Each migration is numbered and tracked

### Usage

**Prerequisites**: Ensure backend service has its own .env file:
```bash
# Backend service should have its own complete .env file
ls services/backend-service/.env
```

**Migration Commands** (run from backend service directory):
```bash
# Navigate to backend service
cd services/backend-service

# Check migration status
python scripts/migration_runner.py --status

# Apply all pending migrations
python scripts/migration_runner.py --apply-all

# Rollback to specific migration
python scripts/migration_runner.py --rollback-to 001

# Create new migration
python scripts/migration_runner.py --new "Add new feature"

# Apply specific migration manually
python scripts/migrations/001_initial_schema.py --apply

# Rollback specific migration manually
python scripts/migrations/001_initial_schema.py --rollback

# Get help
python scripts/migration_runner.py --help
```

**Common Error**: If you get validation errors about missing fields, ensure the backend service's .env file contains all required database configuration.

## Centralized Dependency Management

### **install_requirements.py**

Manages dependencies across all services with isolated virtual environments:

```bash
# Install all service dependencies
python scripts/install_requirements.py all

# Install specific service dependencies
python scripts/install_requirements.py etl-service
python scripts/install_requirements.py backend-service

# Force reinstall (useful for development)
python scripts/install_requirements.py etl-service --force

# Check what services are available
python scripts/install_requirements.py --help
```

### **How It Works**

1. **Per-Service Virtual Environments**: Each service gets its own isolated environment
2. **Centralized Management**: All dependency installation managed from root level
3. **Automatic Environment Creation**: Creates virtual environments if they don't exist
4. **Dependency Isolation**: Prevents version conflicts between services

### **Service Dependencies**

| Service | Virtual Environment | Requirements File |
|---------|-------------------|------------------|
| **ETL Service** | `services/etl-service/venv/` | `services/etl-service/requirements.txt` |
| **Backend Service** | `services/backend-service/venv/` | `services/backend-service/requirements.txt` |
| **Frontend** | N/A (uses npm) | `services/frontend-app/package.json` |

### **Development Workflow**

```bash
# 1. Install dependencies
python scripts/install_requirements.py all

# 2. Ensure each service has its own .env file
ls services/backend-service/.env
ls services/etl-service/.env
ls services/frontend-app/.env

# 3. Run migrations from backend service
cd services/backend-service
python scripts/migration_runner.py --apply-all

# 4. Start services manually
cd services/etl-service
python -m uvicorn app.main:app --reload

cd services/backend-service
python -m uvicorn app.main:app --reload

cd services/frontend-app
npm run dev
```

## Best Practices

1. **Always test migrations** on a copy of production data first
2. **Create rollback scripts** for every forward migration
3. **Use transactions** to ensure atomic operations
4. **Document breaking changes** in migration comments
5. **Backup databases** before running migrations in production

## Adding New Migrations

1. Create new migration file: `00X_description.py`
2. Implement `apply()` and `rollback()` functions
3. Use raw SQL statements for maximum compatibility
4. Test both forward and backward migrations
5. Update this guide with any special considerations

## Cross-Service Utilities

### Planned Utilities

- **Database Backup/Restore**: Scripts for backing up and restoring the entire database
- **Environment Setup**: Scripts for setting up development/staging environments
- **Data Export/Import**: Scripts for exporting data for analysis or importing from external sources
- **Health Checks**: Cross-service health monitoring and diagnostics
- **Configuration Management**: Scripts for managing configuration across services

### Usage Guidelines

1. **Cross-Service Focus**: Utilities should operate across multiple services or provide system-wide functionality
2. **Service-Specific Scripts**: Should remain in their respective service directories
3. **Documentation**: Each utility should include clear usage instructions
4. **Error Handling**: Robust error handling and user-friendly messages
5. **Configuration**: Use environment variables or config files for settings

### Adding New Utilities

1. Create the utility script in the `scripts/utilities/` directory
2. Add appropriate documentation and usage examples
3. Update this guide with a brief description
4. Test thoroughly across different environments
5. Consider adding the utility to CI/CD pipelines if applicable

## Related Documentation

- **[Migration Guide](MIGRATION_GUIDE.md)** - Detailed migration system documentation
- **[Architecture](ARCHITECTURE.md)** - System architecture overview
- **[ETL Development Guide](../services/etl-service/docs/DEVELOPMENT_GUIDE.md)** - Service-specific development

---

**For service-specific scripts, see individual service documentation.**
