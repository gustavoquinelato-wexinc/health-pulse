# ETL Service - Development & Testing Guide

A comprehensive guide for developing, testing, and debugging the ETL service using available scripts and tools.

## 🗂️ **Script Overview**

The `/scripts` folder contains essential executable utilities for managing and testing the ETL service:

```
scripts/
├── reset_database.py      # Database management and initialization
├── test_jobs.py          # Job testing and debugging
└── generate_secret_key.py # Security key generation
```

## 🗄️ **Database Management - `reset_database.py`**

### **Quick Commands**

```bash
# Complete setup (recommended for development)
python scripts/reset_database.py --all

# Interactive mode with step-by-step prompts
python scripts/reset_database.py

# Drop tables only (cleanup)
python scripts/reset_database.py --drop-only

# Recreate schema without integrations
python scripts/reset_database.py --recreate-tables
```

### **What `--all` Does (Recommended)**
✅ **Complete Development Setup:**
1. Drops all existing tables and sequences
2. Recreates database schema from models
3. Initializes default client and workflow configuration
4. Creates issuetype hierarchies and mappings
5. Sets up integrations (Jira, GitHub, Aha!, Azure DevOps)
6. Initializes job schedules and system settings
7. Creates user permissions structure

### **Interactive Mode Features**
When run without flags, provides guided setup:
- Database connection verification
- Step-by-step confirmation prompts
- Selective initialization options
- Real-time progress feedback
- Error handling with recovery suggestions

### **Integration Initialization**
Integrations are automatically configured from environment variables:
- **Jira**: `JIRA_URL`, `JIRA_USERNAME`, `JIRA_TOKEN`
- **GitHub**: `GITHUB_TOKEN`
- **Aha!**: `AHA_TOKEN`, `AHA_URL` (optional)
- **Azure DevOps**: `AZDO_TOKEN`, `AZDO_URL` (optional)

## 🧪 **Job Testing - `test_jobs.py`**

### **Testing Commands**

```bash
# Interactive testing menu (recommended)
python scripts/test_jobs.py

# Test API connections only
python scripts/test_jobs.py --test-connection

# Enable verbose debug logging
python scripts/test_jobs.py --debug

# Force unlock stuck jobs
python scripts/test_jobs.py --breakpoint
```

### **Interactive Testing Menu**
```
📋 AVAILABLE TEST OPTIONS:
🎫 JIRA JOBS:
   1. Extract issue types and projects (ISSUETYPES mode)
   2. Extract statuses and project links (STATUSES mode)  
   3. Extract issues, changelogs, dev_status (ISSUES mode)
   4. Execute custom JQL query (CUSTOM_QUERY mode)
   5. Full Jira extraction (ALL mode)

🐙 GITHUB JOBS:
   6. Extract repositories and basic info (REPOS mode)
   7. Extract pull requests and reviews (PULL_REQUESTS mode)
   8. Full GitHub extraction (ALL mode)

🔗 CONNECTION TESTS:
   9. Test all API connections
   10. Exit
```

### **Connection Testing Features**
- ✅ Environment configuration validation
- ✅ Jira API connectivity and authentication
- ✅ GitHub API connectivity and rate limits
- ✅ Database connection verification
- ✅ Integration record validation
- ✅ Detailed error reporting with solutions

## 🔐 **Security - `generate_secret_key.py`**

```bash
# Generate new encryption key
python scripts/generate_secret_key.py
```

Generates secure 32-byte encryption keys for:
- Token encryption in database
- Session management
- API authentication

## 🚀 **Development Workflow**

### **1. Initial Setup**
```bash
# Navigate to ETL service
cd pulse-platform/services/etl-service

# Activate virtual environment
# Windows: venv\Scripts\activate
# Linux/Mac: source venv/bin/activate

# Complete database setup
python scripts/reset_database.py --all

# Verify connections
python scripts/test_jobs.py --test-connection
```

### **2. Development Cycle**
```bash
# Make code changes...

# Test specific functionality
python scripts/test_jobs.py

# Reset if needed
python scripts/reset_database.py --recreate-tables

# Full integration test
python scripts/test_jobs.py --debug
```

### **3. Debugging Workflow**
```bash
# 1. Check connections first
python scripts/test_jobs.py --test-connection

# 2. Run with debug logging
python scripts/test_jobs.py --debug

# 3. Reset if database issues
python scripts/reset_database.py --all

# 4. Check logs
tail -f logs/etl_service.log
```

## 🔍 **Common Debugging Scenarios**

### **API Connection Issues**
**Symptoms:** Timeouts, auth failures, rate limits

**Solution:**
```bash
# 1. Verify environment variables
cat .env | grep -E "(JIRA|GITHUB)"

# 2. Test connections
python scripts/test_jobs.py --test-connection

# 3. Check integration records
python scripts/test_jobs.py --debug
```

### **Database Issues**
**Symptoms:** Table not found, schema mismatch, data integrity

**Solution:**
```bash
# 1. Complete reset
python scripts/reset_database.py --all

# 2. Verify database connection
docker-compose exec postgres psql -U pulse_user -d pulse_db -c "\dt"

# 3. Check logs
grep -i error logs/etl_service.log
```

### **Job Execution Failures**
**Symptoms:** Jobs fail to start, incomplete extraction, checkpoint issues

**Solution:**
```bash
# 1. Check job locks
python scripts/test_jobs.py --breakpoint

# 2. Debug execution
python scripts/test_jobs.py --debug

# 3. Reset and retry
python scripts/reset_database.py --recreate-tables
```

## 📊 **Log Analysis**

### **Log Locations**
```
logs/
├── etl_service.log           # Main application log
├── test_jobs.log            # Job testing output
├── reset_database.log       # Database operations
└── [job_name]_[date].log    # Individual job logs
```

### **Useful Log Commands**
```bash
# Monitor real-time logs
tail -f logs/etl_service.log

# Search for errors
grep -i error logs/etl_service.log

# Check API calls
grep -i "api\|request\|response" logs/etl_service.log

# View recent job activity
grep -i "job\|extraction" logs/etl_service.log | tail -20
```

## 🎯 **Best Practices**

### **Development Guidelines**
1. **Always start fresh:** Use `--all` for clean development environment
2. **Test connections first:** Verify API connectivity before job testing
3. **Use debug mode:** Enable `--debug` for detailed troubleshooting
4. **Monitor logs:** Keep log files open during development
5. **Incremental testing:** Test individual components before full pipeline

### **Testing Strategy**
1. **Unit Testing:** Individual API calls and functions
2. **Integration Testing:** Job execution and data flow
3. **End-to-End Testing:** Complete pipeline with real data
4. **Error Testing:** Failure scenarios and recovery mechanisms
5. **Performance Testing:** Large datasets and rate limiting

### **Code Quality**
1. **Follow patterns:** Use existing script structure and error handling
2. **Add documentation:** Include help text and usage examples
3. **Handle errors:** Implement proper exception handling and logging
4. **Update docs:** Keep this guide current with new features

## ⚠️ **Important Notes**

- **Backup data** before running database utilities
- **Check .env file** is properly configured before testing
- **Use `--all` flag** for complete setup including integrations
- **Monitor resource usage** during large data operations
- **Document issues** and solutions for team knowledge

## 🔗 **Related Documentation**

- **[System Architecture](../../docs/ARCHITECTURE.md)** - Overall system design
- **[Migration Guide](../../docs/MIGRATION_GUIDE.md)** - Database migration system
- **[Scripts Guide](../../docs/SCRIPTS_GUIDE.md)** - Cross-service scripts and utilities
- **[Log Management](LOG_MANAGEMENT.md)** - Comprehensive logging system

---

**For platform-wide documentation, see:** [Documentation Index](../../docs/DOCUMENTATION_INDEX.md)
