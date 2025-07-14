# PostgreSQL Migration Guide

This guide covers the migration from Snowflake to PostgreSQL for the ETL Service.

## 🎯 **Benefits of PostgreSQL Migration**

- **Performance**: Eliminates N+1 query issues caused by network latency
- **Local Development**: Run database locally in Docker
- **Cost**: No cloud database costs for development/testing
- **Simplicity**: Standard SQL without Snowflake-specific syntax
- **Better SQLAlchemy Support**: Native PostgreSQL support

## 🚀 **Migration Steps**

### 1. **Start PostgreSQL Database**

```bash
# Start PostgreSQL and pgAdmin
cd services/etl-service
docker-compose -f docker-compose.postgres.yml up -d

# Check status
docker-compose -f docker-compose.postgres.yml ps
```

### 2. **Update Environment Configuration**

```bash
# Copy the PostgreSQL environment template
cp .env.postgres.example .env

# Edit .env with your actual values
# Update JIRA_URL, JIRA_USERNAME, JIRA_TOKEN, etc.
```

### 3. **Install New Dependencies**

```bash
# Install PostgreSQL dependencies
pip install -r requirements.txt

# Or if using virtual environment
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

### 4. **Initialize Database**

```bash
# Reset and initialize the database
python utils/reset_database.py --all

# Initialize integrations
python utils/initialize_integrations.py
```

### 5. **Test the Migration**

```bash
# Test database connection and job execution
python utils/test_jira_jobs.py --debug-job
```

## 🔧 **Database Access**

### **pgAdmin Web Interface**
- URL: http://localhost:8080
- Email: admin@kairus.com
- Password: admin

### **Direct PostgreSQL Connection**
- Host: localhost
- Port: 5432
- Database: kairus_etl
- Username: postgres
- Password: postgres

## 📊 **Performance Improvements Expected**

- **N+1 Query Elimination**: Local database removes network latency
- **Faster Bulk Operations**: PostgreSQL optimized for bulk inserts/updates
- **Better Connection Pooling**: Native SQLAlchemy support
- **Reduced Memory Usage**: No Snowflake connector overhead

## 🔄 **Rollback Plan**

If you need to rollback to Snowflake:

1. Restore the original `requirements.txt`
2. Restore the original `config.py` and `database.py`
3. Update `.env` with Snowflake credentials
4. Restart the service

## 🐛 **Troubleshooting**

### **Connection Issues**
```bash
# Check if PostgreSQL is running
docker-compose -f docker-compose.postgres.yml ps

# Check logs
docker-compose -f docker-compose.postgres.yml logs postgres
```

### **Permission Issues**
```bash
# Reset PostgreSQL data
docker-compose -f docker-compose.postgres.yml down -v
docker-compose -f docker-compose.postgres.yml up -d
```

### **Port Conflicts**
If port 5432 is already in use, update the port mapping in `docker-compose.postgres.yml`:
```yaml
ports:
  - "5433:5432"  # Use port 5433 instead
```

Then update `POSTGRES_PORT=5433` in your `.env` file.
