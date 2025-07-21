# ETL Service - Testing & Debugging Guide

This guide covers testing and debugging procedures for the ETL service using the available scripts and tools.

## 🗄️ **Database Management - `reset_database.py`**

### **Available Options**

```bash
# Interactive mode (default) - prompts for each step
python scripts/reset_database.py

# Complete reset with all options (non-interactive)
python scripts/reset_database.py --all

# Just drop tables (non-interactive)
python scripts/reset_database.py --drop-only

# Drop and recreate tables (non-interactive)
python scripts/reset_database.py --recreate-tables

# Initialize integrations only (requires existing tables)
python scripts/reset_database.py --init-integrations

# Create sample data only (requires existing tables and integrations)
python scripts/reset_database.py --sample-data
```

### **What Each Option Does**

#### **`--all` (Complete Reset)**
- Drops all existing tables
- Recreates database schema
- Initializes Jira and GitHub integrations
- Creates sample data for testing
- **Use this for a fresh start**

#### **`--drop-only`**
- Drops all tables from the database
- Useful for complete cleanup

#### **`--recreate-tables`**
- Drops existing tables
- Recreates database schema
- Does not initialize integrations or sample data

#### **`--init-integrations`**
- Creates Jira and GitHub integration records
- Requires existing database schema

#### **`--sample-data`**
- Creates sample projects, issues, and repositories
- Requires existing schema and integrations

### **Interactive Mode**

When run without options, provides an interactive menu:

```
🗄️  Database Reset Tool
======================

Current database: pulse_db
Host: localhost:5432

Available operations:
1. Drop all tables
2. Recreate database schema
3. Initialize integrations
4. Create sample data
5. Complete reset (all above)
6. Exit

Choose operation (1-6):
```

## 🧪 **Job Testing - `test_jobs.py`**

### **Available Options**

```bash
# Interactive manual testing (default)
python scripts/test_jobs.py

# Test API connections only
python scripts/test_jobs.py --test-connection

# Enable debug logging
python scripts/test_jobs.py --debug
```

### **Testing Modes**

#### **Interactive Mode (Default)**
- Presents menu of available test operations
- Allows selection of specific jobs or operations
- Provides detailed feedback and error handling

```
🧪 ETL Jobs Testing Tool
========================

Available Tests:
1. Test API Connections
2. Test Jira Extraction (Manual Mode)
3. Test GitHub Extraction (Manual Mode)
4. Test Full ETL Pipeline
5. View Integration Status
6. Exit

Choose test (1-6):
```

#### **Connection Testing (`--test-connection`)**
- Tests Jira API connectivity and authentication
- Tests GitHub API connectivity and rate limits
- Validates integration configurations
- Reports connection status and any issues

#### **Debug Mode (`--debug`)**
- Enables detailed debug logging
- Shows SQL queries and API requests
- Provides comprehensive error traces
- Useful for troubleshooting integration issues

## 🔍 **Common Debugging Scenarios**

### **1. API Connection Issues**

**Symptoms:**
- Connection timeouts
- Authentication failures
- Rate limit errors

**Debugging Steps:**
```bash
# Test connections
python scripts/test_jobs.py --test-connection

# Check integration configuration with debug
python scripts/test_jobs.py --debug

# Verify environment variables
cat .env | grep -E "(JIRA|GITHUB)"
```

### **2. Database Issues**

**Symptoms:**
- Table not found errors
- Schema mismatch
- Data integrity issues

**Debugging Steps:**
```bash
# Reset database completely
python scripts/reset_database.py --all

# Check database connection
docker-compose exec postgres psql -U pulse_user -d pulse_db

# Verify schema
docker-compose exec postgres psql -U pulse_user -d pulse_db -c "\dt"
```

### **3. Job Execution Failures**

**Symptoms:**
- Jobs fail to start
- Incomplete data extraction
- Checkpoint recovery issues

**Debugging Steps:**
```bash
# Run with debug logging
python scripts/test_jobs.py --debug

# Reset and retry
python scripts/reset_database.py --recreate-tables
python scripts/test_jobs.py
```

## 📊 **Log Analysis**

### **Log Locations**
- `logs/etl_service.log` - Main application log
- `logs/test_jira_jobs.log` - Jira job testing log
- `logs/initialize_integrations.log` - Integration setup log

### **Common Log Analysis**
```bash
# Search for errors
grep -i error logs/etl_service.log

# Check API calls
grep -i "api" logs/etl_service.log

# Monitor job progress
tail -f logs/etl_service.log
```

## 🚀 **Quick Troubleshooting**

### **Reset Everything (Nuclear Option)**
```bash
# Complete fresh start
python scripts/reset_database.py --all
python scripts/test_jobs.py --test-connection
```

### **Connection Issues**
```bash
# Verify environment
cat .env

# Test basic connectivity
python scripts/test_jobs.py --test-connection
```

### **Database Issues**
```bash
# Check database status
docker-compose ps postgres

# Connect to database
docker-compose exec postgres psql -U pulse_user -d pulse_db
```

### **Performance Monitoring**
```bash
# Monitor resource usage
docker stats

# Check database performance
docker-compose exec postgres psql -U pulse_user -d pulse_db -c "SELECT * FROM pg_stat_activity WHERE state = 'active';"
```

## 🎯 **Best Practices**

### **Development Workflow**
1. **Start Fresh:** Always begin with `--all` reset
2. **Test Connections:** Verify API connectivity first
3. **Incremental Testing:** Test individual components before full pipeline
4. **Monitor Logs:** Keep logs open during testing
5. **Document Issues:** Record any problems and solutions

### **Testing Strategy**
1. **Unit Testing:** Test individual API calls
2. **Integration Testing:** Test job execution
3. **End-to-End Testing:** Test complete pipeline
4. **Performance Testing:** Test with realistic data volumes
5. **Error Testing:** Test failure scenarios and recovery

---

**For platform-wide documentation, see:** `/docs/README.md`
