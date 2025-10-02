# Frontend Application - Pulse Platform

A modern React-based frontend application for the Pulse Platform analytics dashboard.

## 🎯 Overview

The Frontend Application provides an intuitive interface for:
- **Analytics Dashboards**: DORA metrics, GitHub analytics, portfolio views
- **ETL Management**: Configuration and monitoring of data pipelines
- **Real-time Monitoring**: Live job status and progress tracking
- **Executive Reporting**: C-level KPIs and business intelligence

## 🏗️ Architecture

### **Technology Stack**
- **React 18** with TypeScript for type safety
- **Vite** for fast development and building
- **Tailwind CSS** for utility-first styling
- **Framer Motion** for smooth animations
- **React Router** for client-side routing
- **React Hook Form** for form management
- **Axios** for API communication

### **Backend Integration**
- **Analytics Backend**: Python/FastAPI service on port 3001
- **Authentication**: JWT token-based authentication
- **Real-time Updates**: WebSocket connections for live data
- **API Communication**: RESTful APIs with comprehensive error handling

### **Design System**
- **Modern Minimalist Design**: Clean, professional interface
- **5-Color Schema System**: Standardized color system with default and custom modes
- **Light/Dark Mode**: Database-persisted theme preferences
- **Typography**: Inter font for excellent readability
- **Client Customization**: Per-client color schemas and branding
- **Accessibility**: WCAG compliant components
- **Responsive**: Mobile-first responsive design

## 🚀 Quick Start

### **Prerequisites**
- Node.js 18+ and npm
- Analytics Backend running on port 3001

### **Development Setup**

#### **Quick Setup (Recommended)**
```bash
# From project root - sets up ALL services including frontend
python scripts/setup_development.py

# Then start frontend
cd services/frontend-app
npm run dev
```

#### **Manual Setup (Alternative)**
```bash
cd services/frontend-app

# Install dependencies
npm install

# Start development server
npm run dev

# Access application
open http://localhost:5173
```

### **Production Build**
```bash
# Build for production
npm run build

# Preview production build
npm run preview
```

## 📊 Key Features

### **Analytics Dashboards**
- **DORA Metrics**: Lead time, deployment frequency, MTTR, change failure rate
- **GitHub Analytics**: Code quality, PR analysis, contributor insights
- **Portfolio View**: Cross-project metrics and correlations
- **Executive KPIs**: C-level business intelligence dashboards

### **ETL Management**
- **Configuration Interface**: Manage ETL settings and parameters
- **Job Control**: Start, stop, and monitor data pipeline jobs
- **Progress Tracking**: Real-time job status and progress indicators
- **Log Viewing**: Access and analyze ETL job logs

### **User Experience**
- **Real-time Updates**: Live data refresh and notifications
- **Interactive Charts**: Dynamic visualizations with drill-down capabilities
- **Responsive Design**: Optimized for desktop, tablet, and mobile
- **Professional UI**: Modern, clean interface optimized for analytics

## 🔧 Configuration

### **Environment Variables**
Configuration is managed through the **centralized `.env` file** at the root level (`../../.env`).

Frontend-specific variables (prefixed with `VITE_`):
```env
# API Configuration
VITE_API_BASE_URL=http://localhost:3001
VITE_ETL_SERVICE_URL=http://localhost:8000
VITE_AI_SERVICE_URL=http://localhost:8001

# Feature Flags
VITE_ENABLE_REAL_TIME=true
VITE_ENABLE_AI_FEATURES=true
```

**Important**: Frontend configuration can use either service-specific `.env` file (`services/frontend-app/.env`) or root `.env` file. Service-specific takes priority.

## 📚 Documentation

- **[Architecture Guide](../../docs/architecture.md)** - System architecture and design
- **[Design System](../../docs/design-system.md)** - UI/UX guidelines and color system
- **[Frontend Architecture](docs/architecture.md)** - Frontend-specific architecture details
- **[Sidebar Implementation](docs/sidebar-implementation.md)** - Navigation system details

## 🔗 Integration Points

### **Analytics Backend (Primary)**
- Authentication and user management
- Dashboard data and complex analytics
- ETL configuration management
- Real-time status updates

### **ETL Service (Direct)**
- Job monitoring and control
- Log access and management
- Real-time progress tracking

### **AI Service (Future)**
- AI-powered insights and recommendations
- Predictive analytics integration

---

**Note**: This is a clean slate setup. The frontend will be rebuilt to integrate with the new Python Analytics Backend architecture for optimal performance and maintainability.
