# Pulse Platform Deployment Guide

This guide covers deployment of the unified Pulse Platform with embedded ETL management.

## 🏗️ **Platform Architecture Overview**

The Pulse Platform is a unified engineering analytics platform that seamlessly integrates ETL management capabilities through iframe embedding.

```
┌─────────────────────────────────────────────────────────────────┐
│                    Pulse Platform                              │
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐                   │
│  │   Frontend      │    │   Backend       │                   │
│  │   (Port 5173)   │◄──►│   (Port 3001)   │                   │
│  │                 │    │                 │                   │
│  │  ┌─────────────┐│    │                 │                   │
│  │  │ ETL iframe  ││◄───┼─────────────────┼───────────────────┤
│  │  │ (embedded)  ││    │                 │                   │
│  │  └─────────────┘│    │                 │                   │
│  └─────────────────┘    └─────────────────┘                   │
│                                   │                           │
│                          ┌─────────────────┐                   │
│                          │   ETL Service   │                   │
│                          │   (Port 8000)   │                   │
│                          └─────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
                                   │
                      ┌─────────────────┐
                      │   PostgreSQL    │
                      │   (Port 5432)   │
                      └─────────────────┘
```

## 🚀 **Deployment Steps**

### **1. Environment Setup**

Create environment files for each service:

**Root `.env`:**
```bash
# Database Configuration
DATABASE_URL=postgresql://pulse_user:pulse_password@localhost:5432/pulse_db

# JWT Configuration
JWT_SECRET_KEY=your-super-secure-jwt-secret-key-here

# Client Configuration
CLIENT_NAME=WEX
```

**Frontend `.env`:**
```bash
VITE_API_BASE_URL=http://localhost:3001
VITE_ETL_BASE_URL=http://localhost:8000
VITE_CLIENT_NAME=WEX
```

**Backend `.env`:**
```bash
PORT=3001
DATABASE_URL=postgresql://pulse_user:pulse_password@localhost:5432/pulse_db
JWT_SECRET_KEY=your-super-secure-jwt-secret-key-here
CLIENT_NAME=WEX
```

**ETL `.env`:**
```bash
DATABASE_URL=postgresql://pulse_user:pulse_password@localhost:5432/pulse_db
JWT_SECRET_KEY=your-super-secure-jwt-secret-key-here
CLIENT_NAME=WEX
BACKEND_SERVICE_URL=http://localhost:3001
```

### **2. Database Setup**

```bash
# Run migrations from backend service
cd services/backend-service
python scripts/migration_runner.py --apply-all

# Verify database setup
psql -h localhost -U pulse_user -d pulse_db -c "\dt"
```

### **3. Service Startup**

**Start all services in order:**

```bash
# 1. Backend Service (Authentication Hub)
cd services/backend-service
npm install
npm run dev

# 2. ETL Service (Embedded Component)
cd services/etl-service
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 3. Frontend Platform (Main Interface)
cd services/frontend-app
npm install
npm run dev
```

### **4. Verification**

**Platform Access:**
- Main Platform: http://localhost:5173
- Backend API: http://localhost:3001
- ETL Service: http://localhost:8000 (embedded only)

**Test Authentication:**
1. Login via Platform Frontend
2. Verify admin users can access ETL Management
3. Verify non-admin users cannot see ETL menu

## 🔧 **Configuration**

### **Client-Specific Deployment**

For different clients, update the following:

**1. Environment Variables:**
```bash
CLIENT_NAME=TECHCORP  # or other client name
```

**2. Client Logos:**
```bash
# Add client logo to both services
cp client-logo.png services/frontend-app/public/
cp client-logo.png services/etl-service/app/static/
```

**3. Update Logo Mapping:**
```typescript
// In both frontend and ETL service
const clientLogos = {
  'wex': '/wex-logo-image.png',
  'techcorp': '/techcorp-logo.png',  // Add new client
};
```

### **Production Deployment**

**Environment Updates:**
```bash
# Production URLs
VITE_API_BASE_URL=https://api.pulse-platform.com
VITE_ETL_BASE_URL=https://etl.pulse-platform.com
BACKEND_SERVICE_URL=https://api.pulse-platform.com

# Production Database
DATABASE_URL=postgresql://user:pass@prod-db:5432/pulse_prod

# Secure JWT Secret
JWT_SECRET_KEY=production-secure-secret-key
```

**Docker Deployment:**
```yaml
# docker-compose.yml
version: '3.8'
services:
  frontend:
    build: ./services/frontend-app
    ports:
      - "80:80"
    environment:
      - VITE_API_BASE_URL=https://api.pulse-platform.com
      - VITE_ETL_BASE_URL=https://etl.pulse-platform.com

  backend:
    build: ./services/backend-service
    ports:
      - "3001:3001"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}

  etl:
    build: ./services/etl-service
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - BACKEND_SERVICE_URL=http://backend:3001

  database:
    image: postgres:15
    environment:
      - POSTGRES_DB=pulse_db
      - POSTGRES_USER=pulse_user
      - POSTGRES_PASSWORD=pulse_password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

## 🔐 **Security Considerations**

### **Authentication Security**
- JWT tokens shared across all platform components
- Admin-only access to ETL management
- Secure token passing via URL parameters (HTTPS only in production)
- Session invalidation across entire platform

### **iframe Security**
```html
<!-- ETL iframe with security attributes -->
<iframe
  src="https://etl.pulse-platform.com/dashboard?embedded=true&token=..."
  sandbox="allow-same-origin allow-scripts allow-forms"
  referrerpolicy="strict-origin-when-cross-origin"
/>
```

### **CORS Configuration**
```javascript
// Backend CORS for embedded ETL
app.use(cors({
  origin: [
    'http://localhost:5173',  // Frontend dev
    'https://pulse-platform.com',  // Frontend prod
    'http://localhost:8000',  // ETL dev
    'https://etl.pulse-platform.com'  // ETL prod
  ],
  credentials: true
}));
```

## 📊 **Monitoring**

### **Health Checks**
- Frontend: http://localhost:5173/health
- Backend: http://localhost:3001/api/v1/health
- ETL: http://localhost:8000/api/v1/health

### **Platform Metrics**
- User authentication success/failure rates
- ETL job completion rates
- iframe loading performance
- Cross-service communication latency

## 🔄 **Updates & Maintenance**

### **Rolling Updates**
1. Update Backend Service (authentication hub)
2. Update ETL Service (embedded component)
3. Update Frontend Platform (main interface)

### **Database Migrations**
```bash
# Run migrations across all services
cd scripts
python migration_runner.py --service all
```

This deployment guide ensures a smooth setup of the unified Pulse Platform with embedded ETL management capabilities.
