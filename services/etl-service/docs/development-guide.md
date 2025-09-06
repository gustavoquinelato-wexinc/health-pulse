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

# Reset tables only (preserve data)
python scripts/reset_database.py --recreate-tables

# Initialize sample data
python scripts/reset_database.py --sample-data

# Backup before reset
python scripts/reset_database.py --backup --all
```

### **Available Options**
- `--all`: Complete database reset with sample data and integrations
- `--recreate-tables`: Drop and recreate all tables (preserves database)
- `--sample-data`: Insert sample tenants, users, and projects
- `--integrations`: Set up Jira and GitHub integration configurations (uses base_search for project filtering)
- `--backup`: Create backup before making changes
- `--force`: Skip confirmation prompts (use with caution)

### **What It Does**
1. **Database Connection**: Validates connection to PostgreSQL
2. **Table Management**: Creates or recreates all required tables
3. **Sample Data**: Inserts realistic test data for development
4. **Integration Setup**: Configures API connections for Jira and GitHub
5. **Verification**: Confirms all operations completed successfully

## 🧪 **Job Testing - `test_jobs.py`**

### **Quick Commands**

```bash
# Interactive menu (recommended)
python scripts/test_jobs.py

# Test specific job types
python scripts/test_jobs.py --jira-all
python scripts/test_jobs.py --github-all

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

### **Job Testing Features**
- **Real API Calls**: Tests against actual Jira and GitHub APIs
- **Data Validation**: Verifies extracted data structure and content
- **Performance Metrics**: Measures execution time and API call counts
- **Error Handling**: Tests error scenarios and recovery mechanisms
- **Debug Output**: Detailed logging for troubleshooting

## 🔐 **Security Key Generation - `generate_secret_key.py`**

### **Usage**
```bash
# Generate new JWT secret key
python scripts/generate_secret_key.py

# Generate with specific length
python scripts/generate_secret_key.py --length 64

# Generate multiple keys
python scripts/generate_secret_key.py --count 3
```

### **Key Features**
- **Cryptographically Secure**: Uses `secrets` module for secure random generation
- **Configurable Length**: Default 32 bytes, customizable
- **Multiple Formats**: Hex, base64, and raw binary output options
- **Environment Ready**: Output formatted for .env files

## 🔧 **Development Workflow**

### **Initial Setup**
```bash
# 1. Set up database
python scripts/reset_database.py --all

# 2. Test API connections
python scripts/test_jobs.py --test-connection

# 3. Run sample job
python scripts/test_jobs.py --jira-all
```

### **Daily Development**
```bash
# Start development server
python run_etl.py

# In another terminal, test changes
python scripts/test_jobs.py

# Reset data when needed
python scripts/reset_database.py --recreate-tables
```

### **Debugging Issues**
```bash
# Enable debug logging
python scripts/test_jobs.py --debug

# Check database state
python scripts/reset_database.py --verify

# Test specific components
python scripts/test_jobs.py --test-connection
```

## 🐛 **Common Issues & Solutions**

### **Database Connection Issues**
**Symptoms:**
- "Connection refused" errors
- "Database does not exist" messages
- Authentication failures

**Solution:**
```bash
# 1. Check PostgreSQL is running
# 2. Verify .env configuration
# 3. Test connection
python scripts/reset_database.py --test-connection

# 4. Recreate database if needed
python scripts/reset_database.py --all
```

### **API Authentication Failures**
**Symptoms:**
- 401 Unauthorized responses
- "Invalid credentials" errors
- API rate limiting messages

**Solution:**
```bash
# 1. Verify API credentials in .env
# 2. Test connections
python scripts/test_jobs.py --test-connection

# 3. Check API token permissions
# 4. Verify API endpoints are accessible
```

### **Job Execution Problems**
**Symptoms:**
- Jobs stuck in "RUNNING" state
- Timeout errors
- Incomplete data extraction

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

### **Structured Logging Features**
The ETL service now uses structured logging with colorful console output and categorized prefixes:

```bash
# Real-time structured logs with colors
[HTTP] Request method=GET url=http://localhost:8000/ headers_count=15
[WS] Connected job_name=Jira total_connections=1
[JIRA] Starting optimized Jira sync (ID: 123)
[BULK] Processing 9 issuetypes records for bulk insert
[ERROR] Request processing failed method=POST error=ValidationError
```

### **Log Locations**
```
logs/
├── etl_service_wex.log      # Main application log (client-specific)
├── test_jobs.log            # Job testing output
├── reset_database.log       # Database operations
└── [job_name]_[date].log    # Individual job logs
```

### **Useful Log Commands**
```bash
# Monitor real-time logs with colors (in terminal)
tail -f logs/etl_service_wex.log

# Search by category
grep "\[HTTP\]" logs/etl_service_wex.log     # HTTP requests
grep "\[WS\]" logs/etl_service_wex.log       # WebSocket connections
grep "\[JIRA\]" logs/etl_service_wex.log     # Jira job operations
grep "\[GITHUB\]" logs/etl_service_wex.log   # GitHub job operations
grep "\[ERROR\]" logs/etl_service_wex.log    # Error conditions

# Search for specific operations
grep "job_name=Jira" logs/etl_service_wex.log
grep "status_code=" logs/etl_service_wex.log
grep "total_connections=" logs/etl_service_wex.log

# View structured data
grep -o "method=[A-Z]*" logs/etl_service_wex.log
grep -o "response_time_ms=[0-9.]*" logs/etl_service_wex.log
```

## 🚀 **Performance Testing**

### **Load Testing**
```bash
# Test with large datasets
python scripts/test_jobs.py --github-all --debug

# Monitor resource usage
# Use system monitoring tools during execution

# Test concurrent jobs
# Run multiple test scripts simultaneously
```

### **API Rate Limiting**
```bash
# Test rate limit handling
python scripts/test_jobs.py --stress-test

# Monitor API usage
# Check logs for rate limit responses

# Adjust request timing
# Modify delay settings in job configurations
```

## 💡 **Best Practices**

- **Backup data** before running database utilities
- **Check .env file** is properly configured before testing
- **Use `--all` flag** for complete setup including integrations
- **Monitor resource usage** during large data operations
- **Document issues** and solutions for team knowledge

## 🔗 **Related Documentation**

- **[System Architecture](../../docs/architecture.md)** - Overall system design
- **[Security & Authentication](../../docs/security-authentication.md)** - Security implementation
- **[Jobs & Orchestration](../../docs/jobs-orchestration.md)** - Job management system
- **[System Settings](../../docs/system-settings.md)** - Configuration reference
- **[Installation & Setup](../../docs/installation-setup.md)** - Setup guide
- **[Log Management](log-management.md)** - Comprehensive logging system

---

**For platform-wide documentation, see:** [Main Documentation](../../docs/)
