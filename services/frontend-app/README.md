# Frontend App - Kairus Platform Dashboard

The Frontend App is a modern React/Next.js application that provides the user interface for the Kairus Platform. It offers dashboards, analytics, and management interfaces for software engineering intelligence.

## 🎯 Features

### Core Functionality
- **Interactive Dashboards**: Real-time data visualization
- **ETL Job Management**: Monitor and control data extraction jobs
- **AI Insights**: Display machine learning predictions and analytics
- **Project Analytics**: Comprehensive project performance metrics
- **Team Performance**: Team productivity and quality insights

### Technical Features
- **Next.js 14**: React framework with App Router
- **TypeScript**: Type-safe development
- **Tailwind CSS**: Utility-first CSS framework
- **Chart.js/Recharts**: Data visualization components
- **React Query**: Server state management
- **Zustand**: Client state management

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend App  │    │ Backend Service │    │   ETL Service   │
│                 │◄──►│      (BFF)      │◄──►│                 │
│  - Dashboard    │    │  - Auth         │    │  - Data Ext.    │
│  - Analytics    │    │  - Aggregation  │    │  - Jobs         │
│  - Management   │    │  - Business     │    │  - Monitoring   │
│  - Monitoring   │    │    Logic        │    └─────────────────┘
└─────────────────┘    │                 │    ┌─────────────────┐
                       │                 │◄──►│   AI Service    │
                       │                 │    │                 │
                       └─────────────────┘    │  - ML Models    │
                                              │  - Analytics    │
                                              │  - Predictions  │
                                              └─────────────────┘
```

## 📁 Project Structure

```
frontend-app/
├── src/
│   ├── app/                    # Next.js App Router
│   │   ├── layout.tsx          # Root layout
│   │   ├── page.tsx            # Home page
│   │   ├── dashboard/          # Dashboard pages
│   │   ├── analytics/          # Analytics pages
│   │   ├── etl/               # ETL management pages
│   │   └── auth/              # Authentication pages
│   ├── components/
│   │   ├── ui/                # Reusable UI components
│   │   ├── charts/            # Chart components
│   │   ├── forms/             # Form components
│   │   └── layout/            # Layout components
│   ├── lib/
│   │   ├── api.ts             # API client
│   │   ├── auth.ts            # Authentication utilities
│   │   ├── utils.ts           # Utility functions
│   │   └── validations.ts     # Form validations
│   ├── hooks/
│   │   ├── useAuth.ts         # Authentication hook
│   │   ├── useApi.ts          # API hooks
│   │   └── useLocalStorage.ts # Local storage hook
│   ├── store/
│   │   ├── auth.store.ts      # Authentication store
│   │   ├── dashboard.store.ts # Dashboard store
│   │   └── settings.store.ts  # Settings store
│   ├── types/
│   │   ├── auth.types.ts      # Authentication types
│   │   ├── api.types.ts       # API response types
│   │   └── dashboard.types.ts # Dashboard types
│   └── styles/
│       └── globals.css        # Global styles
├── public/
│   ├── icons/
│   └── images/
├── package.json
├── next.config.js
├── tailwind.config.js
├── tsconfig.json
├── Dockerfile
├── .env.example
└── README.md
```

## 🚀 Quick Start

### Using Docker (Recommended)

1. **From the monorepo root**:
```bash
cd kairus-platform
docker-compose up frontend-app
```

2. **Access the application**:
- Frontend: http://localhost:3001

### Local Development

1. **Install dependencies**:
```bash
cd services/frontend-app
npm install
```

2. **Configure environment**:
```bash
cp .env.example .env.local
# Edit .env.local with your configuration
```

3. **Run the development server**:
```bash
npm run dev
```

## 📊 Pages and Features

### Dashboard
- **Overview**: Key metrics and KPIs
- **Projects**: Project status and progress
- **Teams**: Team performance metrics
- **Real-time Updates**: Live data refresh

### Analytics
- **Project Analytics**: Detailed project insights
- **Team Performance**: Productivity and quality metrics
- **Trend Analysis**: Historical data trends
- **Predictive Insights**: AI-powered predictions

### ETL Management
- **Job Monitoring**: ETL job status and logs
- **Integration Management**: Configure data sources
- **Data Quality**: Data validation and quality metrics
- **Scheduling**: Manage automated jobs

### AI Insights
- **Model Performance**: ML model metrics
- **Predictions**: Timeline and risk predictions
- **Recommendations**: Process improvement suggestions
- **Anomaly Detection**: Unusual pattern alerts

## 🎨 UI Components

### Charts and Visualizations
- Line charts for trends
- Bar charts for comparisons
- Pie charts for distributions
- Heatmaps for correlation data
- Gauge charts for KPIs

### Data Tables
- Sortable columns
- Filtering and search
- Pagination
- Export functionality
- Real-time updates

### Forms and Inputs
- Validation with error messages
- Auto-complete inputs
- Date/time pickers
- File upload components
- Multi-select dropdowns

## 🔧 Configuration

### Environment Variables

```bash
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:3000
NEXT_PUBLIC_ETL_SERVICE_URL=http://localhost:8000
NEXT_PUBLIC_AI_SERVICE_URL=http://localhost:8001

# Authentication
NEXT_PUBLIC_AUTH_ENABLED=true
NEXT_PUBLIC_JWT_STORAGE_KEY=kairus_token

# Features
NEXT_PUBLIC_ENABLE_ANALYTICS=true
NEXT_PUBLIC_ENABLE_AI_INSIGHTS=true
NEXT_PUBLIC_ENABLE_ETL_MANAGEMENT=true

# UI Configuration
NEXT_PUBLIC_THEME=light
NEXT_PUBLIC_REFRESH_INTERVAL=30000
```

### Tailwind Configuration

Custom theme configuration for Kairus branding:

```javascript
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          500: '#3b82f6',
          900: '#1e3a8a'
        },
        secondary: {
          50: '#f8fafc',
          500: '#64748b',
          900: '#0f172a'
        }
      }
    }
  }
}
```

## 🔐 Authentication

### JWT Token Management
- Automatic token refresh
- Secure token storage
- Route protection
- Session management

### Protected Routes
- Dashboard pages require authentication
- Public pages: login, register, landing
- Role-based access control
- Automatic redirects

## 📱 Responsive Design

- Mobile-first approach
- Tablet and desktop optimizations
- Touch-friendly interfaces
- Adaptive layouts

## 🧪 Testing

```bash
# Run all tests
npm test

# Run tests in watch mode
npm run test:watch

# Run E2E tests
npm run test:e2e

# Run tests with coverage
npm run test:coverage
```

## 🚀 Deployment

### Production Build

```bash
npm run build
npm start
```

### Docker Deployment

```bash
docker build -t kairus-frontend .
docker run -p 3001:3001 kairus-frontend
```

### Static Export (Optional)

```bash
npm run build
npm run export
```

## 📈 Performance

- Code splitting with Next.js
- Image optimization
- Lazy loading components
- Caching strategies
- Bundle size optimization

## 🎯 User Experience

- Loading states and skeletons
- Error boundaries and fallbacks
- Toast notifications
- Keyboard navigation
- Accessibility compliance (WCAG 2.1)

---

**Part of the Kairus Platform - Software Engineering Intelligence**
