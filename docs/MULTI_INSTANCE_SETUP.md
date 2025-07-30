# 🚀 Multi-Instance ETL Setup Guide

This guide explains how to set up and run multiple ETL instances for different clients using the simplified multi-instance architecture.

## 📋 **Quick Start**

### **Option 1: Automated Setup (Recommended)**

```bash
# Linux/Mac
chmod +x start-multi-instance.sh
./start-multi-instance.sh

# Windows
start-multi-instance.bat
```

### **Option 2: Docker Compose**

```bash
# Start all services
docker-compose -f docker-compose.multi-client.yml up -d

# Check logs
docker-compose -f docker-compose.multi-client.yml logs -f

# Stop services
docker-compose -f docker-compose.multi-client.yml down
```

### **Option 3: Manual Setup**

1. **Prepare environment files:**
   ```bash
   # Create combined environment file for migration runner (if needed)
   cat .env.shared .env.etl.wex > .env

   # Install dependencies using centralized management
   python scripts/install_requirements.py etl-service
   python scripts/install_requirements.py backend-service
   ```

2. **Start Backend Service:**
   ```bash
   cd services/backend-service
   cat ../../.env.shared ../../.env.backend > .env
   python -m uvicorn app.main:app --host 0.0.0.0 --port 3001 --reload
   ```

3. **Start ETL instances for different clients:**
   ```bash
   # For WEX client instance
   cd services/etl-service
   cat ../../.env.shared ../../.env.etl.wex > .env
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

   # For TechCorp client instance (in another terminal)
   cd services/etl-service
   cat ../../.env.shared ../../.env.etl.techcorp > .env
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
   ```

4. **Start Frontend (optional):**
   ```bash
   cd services/frontend-app
   npm install
   npm run dev
   ```

## 🎯 **Service URLs**

| Service | URL | Purpose |
|---------|-----|---------|
| **WEX ETL** | http://localhost:8000 | ETL for WEX client only |
| **TechCorp ETL** | http://localhost:8001 | ETL for TechCorp client only |
| **Backend** | http://localhost:3001 | Shared authentication service |
| **PostgreSQL** | localhost:5432 | Shared database |

## 🔧 **Environment Configuration**

### **Root-Level Environment Files**

- **`.env.etl.wex`** - WEX client configuration
- **`.env.etl.techcorp`** - TechCorp client configuration
- **`.env`** - Main environment (includes client config)
- **`.env.example`** - Template for new setups
- **`.env.production`** - Production configuration template

### **Key Client Configuration Variables**

```bash
# Client Configuration (Multi-Instance Approach)
CLIENT_NAME=WEX      # Client name (looked up in database, case-insensitive)
ETL_PORT=8000        # Port for this ETL instance
```

**Note:** The `CLIENT_ID` is automatically looked up from the database using the `CLIENT_NAME` (case-insensitive). This makes configuration more human-readable and less error-prone.

## 📝 **Setup Instructions**

### **1. Initial Setup**

```bash
# 1. Copy the main environment file
cp .env.example .env

# 2. Configure your database and API credentials in .env
# Edit POSTGRES_*, JIRA_*, GITHUB_* variables

# 3. Choose your client configuration approach:
```

### **2. Client Configuration Options**

**Option A: Use Pre-configured Files**
```bash
# For WEX client
cp .env.etl.wex services/etl-service/.env

# For TechCorp client  
cp .env.etl.techcorp services/etl-service/.env
```

**Option B: Manual Configuration**
```bash
# Edit services/etl-service/.env and set:
CLIENT_NAME=WEX      # Must match database client name (case-insensitive)
ETL_PORT=8000
```

### **3. Start Services**

```bash
# Automated (recommended)
./start-multi-instance.sh

# Or manual
cd services/etl-service
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 🧪 **Testing**

```bash
# Test both instances
python test_per_client_orchestrators.py

# Test client name lookup
python test_client_name_lookup.py

# 🚨 CRITICAL: Test client isolation security
python test_client_isolation_security.py

# Expected output:
# ✅ WEX ETL instance is healthy (Port 8000)
# ✅ TechCorp ETL instance is healthy (Port 8001)
# ✅ Client isolation security verified
```

## 🏗️ **Architecture Benefits**

### **✅ Simplicity**
- Each ETL instance serves only one client
- No complex cross-client logic
- Easy to understand and debug

### **✅ True Isolation**
- Process-level separation
- Independent scaling
- Fault isolation

### **✅ Industry Standard**
- Netflix/Uber pattern
- Microservices approach
- Production ready

## 🚀 **Production Deployment**

For production, deploy separate ETL instances:

```bash
# Instance 1: WEX Client
CLIENT_NAME=WEX PORT=8000 python -m uvicorn app.main:app

# Instance 2: TechCorp Client
CLIENT_NAME=TechCorp PORT=8001 python -m uvicorn app.main:app
```

## 🔍 **Troubleshooting**

### **Port Conflicts**
- WEX ETL: Port 8000
- TechCorp ETL: Port 8001
- Backend: Port 3001

### **Environment Issues**
- Ensure client environment files are copied to `services/etl-service/.env`
- Check CLIENT_ID and CLIENT_NAME are set correctly
- Verify database connection settings

### **Client Not Found Error**
```
❌ Client 'TechCorp' not found or inactive. Available active clients: ['WEX']
```
- Ensure client exists in database and is active
- Check CLIENT_NAME matches database client name (case-insensitive)
- Verify client is marked as active in the database
