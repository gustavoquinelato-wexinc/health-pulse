# ETL Service Utilities

This folder contains essential utility scripts for managing and testing the ETL service.

## 📁 Available Utilities

### 🗄️ Database Management

#### `reset_database.py`
Resets the database by dropping and recreating all tables with fresh data.

```bash
# Complete reset with integration initialization
python utils/reset_database.py --all

# Reset database only (no integration setup)
python utils/reset_database.py
```

#### `initialize_integrations.py`
Initializes integration records (Jira, GitHub, Aha!, Azure DevOps) in the database.

```bash
# Initialize all configured integrations
python utils/initialize_integrations.py

# Force re-initialize existing integrations
python utils/initialize_integrations.py --force

# Initialize specific integration only
python utils/initialize_integrations.py --integration jira
```

### 🔐 Security

#### `generate_secret_key.py`
Generates secure encryption keys for the application configuration.

```bash
python utils/generate_secret_key.py
```

### 🧪 Testing & Debugging

#### `test_jira_jobs.py`
Comprehensive test script for debugging and testing Jira ETL jobs manually.

**Basic Usage:**
```bash
# Test Jira connection only
python utils/test_jira_jobs.py --test-connection

# Debug job execution step-by-step
python utils/test_jira_jobs.py --debug-job

# Step-by-step debugging with breakpoints
python utils/test_jira_jobs.py --step-by-step

# Test scheduler configuration
python utils/test_jira_jobs.py --test-scheduler

# Force unlock if job is stuck
python utils/test_jira_jobs.py --force-unlock
```

**Features:**
- ✅ Environment configuration validation
- ✅ Jira connection testing
- ✅ Database connection verification
- ✅ Manual job execution with debugging
- ✅ Step-by-step debugging capabilities
- ✅ Job locking mechanism testing
- ✅ Detailed logging and error reporting

## 🚀 Quick Start

1. **Navigate to ETL service directory:**
   ```bash
   cd kairus-platform/services/etl-service
   ```

2. **Ensure virtual environment is activated:**
   ```bash
   # Windows
   venv\Scripts\activate

   # Linux/Mac
   source venv/bin/activate
   ```

3. **Common workflow:**
   ```bash
   # 1. Reset database and initialize integrations
   python utils/reset_database.py --all

   # 2. Test the ETL pipeline
   python utils/test_jira_jobs.py --debug-job
   ```

## ⚠️ Important Notes

- **Always backup your data** before running database utilities
- **Use `--all` flag** with reset_database.py for complete setup
- **Check logs** in the `logs/` directory for detailed information
- **Ensure .env file** is properly configured before running tests
- **Run initialize_integrations.py** if integrations aren't automatically created

## 🔧 Development

When adding new utility scripts:

1. Place them in this `utils/` folder
2. Add proper documentation and help text
3. Include error handling and logging
4. Update this README with usage instructions
5. Follow the existing code style and patterns

## 📝 Logging

All utilities log to:
- **Console**: Real-time output
- **File**: `logs/` directory (script-specific log files)

Use `--debug` flag for verbose logging when troubleshooting.
