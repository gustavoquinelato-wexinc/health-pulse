# Backend Service Scripts

This directory contains utility scripts for the Backend Service.

## Available Scripts

### `generate_secret_key.py`
Generates secure secret keys for the Backend Service configuration.

**Usage:**
```bash
python scripts/generate_secret_key.py
```

**Generates:**
- `JWT_SECRET_KEY` - For JWT token signing
- `SECRET_KEY` - General application secret
- `ENCRYPTION_KEY` - For data encryption (Fernet-compatible)

## Important Notes

### Database Management
- **Use Migrations**: Database schema and initial data are managed through migrations in `/scripts/migrations/`
- **No Reset Scripts**: Reset scripts have been removed in favor of proper migration management
- **Backend Service**: Contains ALL database tables (including user authentication)
- **ETL Service**: No longer manages authentication tables

### Security
- Keep generated keys secure and never commit them to version control
- Use different keys for different environments (dev, staging, prod)
- Store keys securely - if lost, encrypted data cannot be recovered

### Migration-Based Approach
Instead of reset scripts, use the migration system:
1. **Initial Setup**: Run `python scripts/migration_runner.py` to apply all migrations
2. **Schema Changes**: Create new migration files for database changes
3. **Data Changes**: Include data updates in migration scripts
4. **Clean State**: Drop database and re-run migrations for fresh start
