# ETL Service Scripts

This folder contains essential executable scripts for managing and testing the ETL service.

## 📁 Available Utilities

### 🗄️ Database Management

#### `reset_database.py`
Resets the database by dropping and recreating all tables with fresh data.

```bash
# Complete reset with integration initialization
python scripts/reset_database.py --all

# Reset database only (no integration setup)
python scripts/reset_database.py
```

#### `initialize_integrations.py`
Initializes integration records (Jira, GitHub, Aha!, Azure DevOps) in the database.

```bash
# Initialize all configured integrations
python scripts/initialize_integrations.py

# Force re-initialize existing integrations
python scripts/initialize_integrations.py --force

# Initialize specific integration only
python scripts/initialize_integrations.py --integration jira
```

### 🔐 Security

#### `generate_secret_key.py`
Generates secure encryption keys for the application configuration.

```bash
python scripts/generate_secret_key.py
```

### 🧪 Testing & Debugging

#### `test_jobs.py`
Unified testing script for debugging and testing ETL jobs using the same functions as production.

**Basic Usage:**
```bash
# Interactive manual testing (default)
python scripts/test_jobs.py

# Test API connections only
python scripts/test_jobs.py --test-connection

# Enable debug logging
python scripts/test_jobs.py --debug

# Force unlock if job is stuck
python scripts/test_jobs.py --breakpoint
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
   cd pulse-platform/services/etl-service
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
   python scripts/reset_database.py --all

   # 2. Test the ETL pipeline
   python scripts/test_jobs.py --auto
   ```

## ⚠️ Important Notes

- **Always backup your data** before running database utilities
- **Use `--all` flag** with reset_database.py for complete setup
- **Check logs** in the `logs/` directory for detailed information
- **Ensure .env file** is properly configured before running tests
- **Run initialize_integrations.py** if integrations aren't automatically created

## 🔧 Development

When adding new utility scripts:

1. Place them in this `scripts/` folder
2. Add proper documentation and help text
3. Include error handling and logging
4. Update this README with usage instructions
5. Follow the existing code style and patterns

## 📝 Logging

All utilities log to:
- **Console**: Real-time output
- **File**: `logs/` directory (script-specific log files)

Use `--debug` flag for verbose logging when troubleshooting.
