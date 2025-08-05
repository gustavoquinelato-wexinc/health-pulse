# Frontend App Guide

This guide covers the unified Pulse Platform frontend application, including cross-service ETL navigation, UI/UX standards, and client-side functionality.

## 🏗️ **Platform Architecture**

### **Unified Frontend Platform**
The Pulse Platform frontend is now a comprehensive engineering analytics platform that seamlessly integrates ETL management capabilities:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Pulse Platform Frontend                     │
│                      (React + Vite + TS)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  📊 DORA Metrics Dashboard                                      │
│  📈 Engineering Analytics                                       │
│  🔧 Settings Management                                         │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              🔧 ETL Management (Admin Only)                │ │
│  │                                                             │ │
│  │  POST Navigation: /auth/navigate → ETL Service             │ │
│  │                                                             │ │
│  │  • Job Orchestration Dashboard                             │ │
│  │  • Data Pipeline Configuration                             │ │
│  │  • Real-time Progress Monitoring                           │ │
│  │  • Integration Management                                  │ │
│  │  • Admin Panel Access                                      │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### **Key Integration Features**
- **Seamless Authentication**: Shared JWT tokens across platform and ETL
- **Role-Based Access**: ETL management visible only to admin users
- **Unified Branding**: Client-specific logos and themes
- **Responsive Design**: Consistent experience across all screen sizes
- **Real-time Updates**: WebSocket integration for live job monitoring

## 🔗 **ETL Navigation Patterns**

### **Cross-Service Navigation**
The ETL service is accessed via secure POST-based navigation with token authentication:

```typescript
// ETL Navigation Integration
const handleETLDirectNavigation = async (openInNewTab = false) => {
  const token = localStorage.getItem('pulse_token')
  if (!token) {
    console.error('No authentication token found')
    return
  }

  try {
    const ETL_SERVICE_URL = import.meta.env.VITE_ETL_SERVICE_URL || 'http://localhost:8000'

    // POST token to ETL service for authentication
    const response = await fetch(`${ETL_SERVICE_URL}/auth/navigate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        token: token,
        return_url: window.location.href
      }),
      credentials: 'include'
    })

    if (response.ok) {
      const data = await response.json()
      if (data.redirect_url) {
        if (openInNewTab) {
          window.open(`${ETL_SERVICE_URL}${data.redirect_url}`, '_blank')
        } else {
          window.location.href = `${ETL_SERVICE_URL}${data.redirect_url}`
        }
      }
    }
  } catch (error) {
    console.error('Failed to navigate to ETL service:', error)
  }
}
```

### **Authentication Integration**
```typescript
// Header Button with Cross-Service Navigation
{user?.role === 'admin' && (
  <motion.a
    href={`${ETL_SERVICE_URL}/home?token=${encodeURIComponent(localStorage.getItem('pulse_token') || '')}`}
    onClick={(e) => {
      e.preventDefault();
      const openInNewTab = e.ctrlKey || e.metaKey;
      handleETLDirectNavigation(openInNewTab);
    }}
    onAuxClick={(e) => {
      if (e.button === 1) { // Middle click
        e.preventDefault();
        handleETLDirectNavigation(true);
      }
    }}
    className="p-2 rounded-lg bg-tertiary hover:bg-primary transition-colors inline-block"
    title="ETL Management"
  >
    <img src="/archive-solid-svgrepo-com.svg" alt="ETL Management" width="20" height="20" />
  </motion.a>
)}
```

### **Navigation Integration**
```typescript
// Sidebar Navigation with ETL
const sidebarItems = [
  { name: 'Home', path: '/home', icon: HomeIcon },
  { name: 'DORA Metrics', path: '/dora', icon: ChartIcon,
    submenu: [
      { name: 'Deployment Frequency', path: '/dora/deployment-frequency' },
      { name: 'Lead Time', path: '/dora/lead-time' },
      { name: 'MTTR', path: '/dora/mttr' },
      { name: 'Change Failure Rate', path: '/dora/change-failure-rate' }
    ]
  },
  { name: 'Engineering Analytics', path: '/analytics', icon: AnalyticsIcon },
  // ETL Management - Admin Only
  ...(user?.is_admin ? [
    { name: 'ETL Management', path: '/etl', icon: DatabaseIcon }
  ] : []),
  { name: 'Settings', path: '/settings', icon: SettingsIcon }
];
```

### **Theme Synchronization**
```typescript
// Theme passing to embedded ETL
useEffect(() => {
  const iframe = document.querySelector('iframe[title="ETL Management"]') as HTMLIFrameElement;
  if (iframe) {
    const newUrl = getETLUrl('dashboard');
    if (iframe.src !== newUrl) {
      iframe.src = newUrl; // Updates theme/colorMode in real-time
    }
  }
}, [theme, colorMode]);
```

## 🎨 UI/UX Standards

### **Design System**
- **Framework**: Tailwind CSS with custom design tokens
- **Typography**: Inter font family for modern, clean appearance
- **Color System**: 5-color schema system with default and custom modes
- **Theme Support**: Light/dark mode with database persistence
- **Client Customization**: Per-client color schemas and theme preferences

### **5-Color Schema System**
The platform uses a standardized 5-color system that provides consistency while allowing customization:

```css
/* Default 5-Color Schema */
:root {
    --color-1: #2862EB;  /* Blue - Primary */
    --color-2: #763DED;  /* Purple - Secondary */
    --color-3: #059669;  /* Emerald - Success */
    --color-4: #0EA5E9;  /* Sky Blue - Info */
    --color-5: #F59E0B;  /* Amber - Warning */
}

/* Custom Color Schema Override (WEX Brand) */
[data-color-schema="custom"] {
    --color-1: #C8102E;  /* WEX Red */
    --color-2: #253746;  /* Dark Blue */
    --color-3: #00C7B1;  /* Teal */
    --color-4: #A2DDF8;  /* Light Blue */
    --color-5: #FFBF3F;  /* Yellow */
}
```

### **Component Standards**
- **Modals**: Consistent black/dark background styling
- **Cards**: Clean minimalism over glassmorphism effects
- **Buttons**: Accessible with proper focus states
- **Forms**: Validation feedback with clear error messages

## 🔐 Authentication Flow

### **Bidirectional Authentication System**
The Frontend supports bidirectional authentication where users can log in from either Frontend or ETL service and maintain seamless access across both services.

#### **ETL Service Login Detection**
```typescript
// Listen for authentication from ETL service
useEffect(() => {
  const handleMessage = (event: MessageEvent) => {
    if (event.data.type === 'AUTH_SUCCESS') {
      // User logged in from ETL service
      const { token, user } = event.data
      localStorage.setItem('pulse_token', token)
      setUser(user)
      // Refresh page to load full user context
      window.location.reload()
    }
  }

  window.addEventListener('message', handleMessage)
  return () => window.removeEventListener('message', handleMessage)
}, [])
```

### **Token Management**
```javascript
// Multi-source token retrieval
function getAuthToken() {
    // Priority: localStorage → cookies → sessionStorage
    let token = localStorage.getItem('pulse_token');
    
    if (!token) {
        // Parse cookies manually for pulse_token
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'pulse_token') {
                token = value;
                break;
            }
        }
    }
    
    return token;
}
```

### **Logout Implementation**
```javascript
async function logout() {
    try {
        // 1. Get token BEFORE clearing storage
        const token = getAuthToken();
        
        if (token) {
            // 2. Call Backend Service to invalidate session
            const response = await fetch('http://localhost:3001/api/v1/admin/auth/invalidate-session', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.ok) {
                console.log('✅ Session invalidated successfully');
            }
        }
    } catch (error) {
        console.warn('Session invalidation error:', error);
    }
    
    // 3. Clear localStorage
    localStorage.removeItem('pulse_token');
    
    // 4. ETL service logout for cookie clearing and redirect
    window.location.href = '/logout';
}
```

### **Authentication Validation**
```javascript
async function checkAuth() {
    const token = getAuthToken();
    if (!token) {
        redirectToLogin('No authentication token found');
        return false;
    }
    
    try {
        const response = await fetch('/api/v1/auth/validate', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        return response.ok;
    } catch (error) {
        console.error('Auth validation error:', error);
        redirectToLogin('Session validation failed');
        return false;
    }
}
```

## 🧭 Navigation & Layout

### **Sidebar Structure**
```
Home
DORA Metrics
├── Deployment Frequency
├── Lead Time for Changes  
├── Mean Time to Recovery
└── Change Failure Rate
Engineering Analytics
Settings
```

### **Sidebar Implementation**
```javascript
// Hover submenu with precise timing
function initializeSidebar() {
    const doraItem = document.querySelector('[data-submenu="dora"]');
    const submenu = document.querySelector('.dora-submenu');
    let hoverTimeout;
    
    doraItem.addEventListener('mouseenter', () => {
        clearTimeout(hoverTimeout);
        submenu.style.display = 'block';
    });
    
    doraItem.addEventListener('mouseleave', () => {
        hoverTimeout = setTimeout(() => {
            submenu.style.display = 'none';
        }, 200); // 200ms grace period
    });
}
```

### **Header Layout**
- **Left**: WEX client image/logo
- **Center**: Page title and breadcrumbs
- **Right**: User menu, notifications, settings
- **Responsive**: Collapsible on mobile devices

## 📊 State Management

### **Session State**
```javascript
// Global session state
let currentUser = null;
let sessionValid = false;

// Session management
async function loadUserInfo() {
    try {
        const token = getAuthToken();
        const response = await fetch('/api/v1/auth/user-info', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
            currentUser = await response.json();
            updateUIForUser(currentUser);
        }
    } catch (error) {
        console.error('Failed to load user info:', error);
    }
}
```

### **Real-time State Updates**
```javascript
// WebSocket state synchronization
websocket.onmessage = function(event) {
    const data = JSON.parse(event.data);
    
    switch (data.type) {
        case 'job_status':
            updateJobStatus(data.job_type, data.status);
            break;
        case 'progress_update':
            updateProgress(data.job_type, data.progress);
            break;
        case 'system_health':
            updateSystemHealth(data.health);
            break;
    }
};
```

## 🔄 Real-time Features

### **WebSocket Integration**
```javascript
class WebSocketManager {
    constructor() {
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
    }
    
    connect() {
        try {
            this.ws = new WebSocket('ws://localhost:3000/ws');
            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.reconnectAttempts = 0;
            };
            
            this.ws.onclose = () => {
                console.log('WebSocket disconnected');
                this.attemptReconnect();
            };
            
            this.ws.onmessage = (event) => {
                this.handleMessage(JSON.parse(event.data));
            };
        } catch (error) {
            console.error('WebSocket connection failed:', error);
            this.attemptReconnect();
        }
    }
    
    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            setTimeout(() => {
                this.reconnectAttempts++;
                this.connect();
            }, this.reconnectDelay * this.reconnectAttempts);
        }
    }
}
```

### **Auto-refresh Configuration**
```javascript
// Configurable refresh intervals
const refreshIntervals = {
    '30000': '30 seconds',
    '60000': '1 minute',
    '300000': '5 minutes',
    '0': 'Disabled'
};

function setupAutoRefresh() {
    const select = document.getElementById('refreshInterval');
    let refreshTimer = null;
    
    select.addEventListener('change', function() {
        if (refreshTimer) {
            clearInterval(refreshTimer);
            refreshTimer = null;
        }
        
        const interval = parseInt(this.value);
        if (interval > 0) {
            refreshTimer = setInterval(() => {
                refreshData();
                refreshSystemHealth();
            }, interval);
        }
    });
}
```

## 📱 Responsive Design

### **Mobile-First Approach**
```css
/* Mobile-first responsive design */
.sidebar {
    transform: translateX(-100%);
    transition: transform 0.3s ease;
}

@media (min-width: 768px) {
    .sidebar {
        transform: translateX(0);
        position: relative;
    }
}

/* Responsive navigation */
.nav-toggle {
    display: block;
}

@media (min-width: 768px) {
    .nav-toggle {
        display: none;
    }
}
```

### **Accessibility Standards**
```html
<!-- Proper ARIA labels -->
<button aria-label="Toggle navigation" aria-expanded="false">
    <span class="sr-only">Toggle navigation</span>
</button>

<!-- Focus management -->
<div role="dialog" aria-labelledby="modal-title" aria-modal="true">
    <h2 id="modal-title">Modal Title</h2>
</div>

<!-- Keyboard navigation -->
<nav role="navigation" aria-label="Main navigation">
    <ul role="menubar">
        <li role="none">
            <a href="#" role="menuitem">Home</a>
        </li>
    </ul>
</nav>
```

## 🎭 Theme & Customization

### **Light/Dark Mode with Database Persistence**
```javascript
// Modern theme management with database persistence
import { useTheme } from '../contexts/ThemeContext'

function ThemeToggle() {
    const { theme, toggleTheme } = useTheme()

    return (
        <button onClick={toggleTheme}>
            {theme === 'light' ? '🌙' : '☀️'}
        </button>
    )
}

// Theme context automatically:
// 1. Loads theme from database on startup
// 2. Saves theme to database when changed
// 3. Applies theme to document.documentElement
// 4. Persists across browser sessions
```

### **Color Schema Modes**
The platform supports two color schema modes:

```css
/* Default Mode - Built-in professional colors */
:root {
    --color-1: #2862EB;  /* Blue - Primary */
    --color-2: #763DED;  /* Purple - Secondary */
    --color-3: #059669;  /* Emerald - Success */
    --color-4: #0EA5E9;  /* Sky Blue - Info */
    --color-5: #F59E0B;  /* Amber - Warning */
}

/* Custom Mode - Client-specific brand colors */
[data-color-schema="custom"] {
    --color-1: #C8102E;  /* Client Primary */
    --color-2: #253746;  /* Client Secondary */
    --color-3: #00C7B1;  /* Client Accent */
    --color-4: #A2DDF8;  /* Client Info */
    --color-5: #FFBF3F;  /* Client Warning */
}
```

### **Using Colors in Components**
```jsx
// Use the 5-color system in components
function StatusBadge({ status, children }) {
    const colorMap = {
        success: 'var(--color-3)',
        warning: 'var(--color-5)',
        info: 'var(--color-4)',
        primary: 'var(--color-1)',
        secondary: 'var(--color-2)'
    }

    return (
        <span
            className="px-2 py-1 rounded text-white text-xs"
            style={{ backgroundColor: colorMap[status] }}
        >
            {children}
        </span>
    )
}

// Or use Tailwind classes
<div className="bg-color-1 text-white p-4">
    Primary colored content
</div>
```

## 🔧 Performance Patterns

### **Lazy Loading**
```javascript
// Lazy load heavy components
async function loadDashboardModule() {
    const { DashboardComponent } = await import('./dashboard.js');
    return new DashboardComponent();
}

// Intersection Observer for lazy loading
const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            loadComponent(entry.target);
            observer.unobserve(entry.target);
        }
    });
});
```

### **Debounced Search**
```javascript
// Debounced search implementation
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

const debouncedSearch = debounce(async (searchTerm) => {
    const results = await searchAPI(searchTerm);
    updateSearchResults(results);
}, 300);
```

## 🚨 Error Handling

### **Global Error Handler**
```javascript
// Global error handling
window.addEventListener('error', (event) => {
    console.error('Global error:', event.error);
    showErrorNotification('An unexpected error occurred');
});

// Promise rejection handling
window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled promise rejection:', event.reason);
    showErrorNotification('A network error occurred');
});
```

### **API Error Handling**
```javascript
async function apiCall(url, options = {}) {
    try {
        const response = await fetch(url, {
            ...options,
            headers: {
                'Authorization': `Bearer ${getAuthToken()}`,
                'Content-Type': 'application/json',
                ...options.headers
            }
        });
        
        if (response.status === 401) {
            redirectToLogin('Session expired');
            return null;
        }
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('API call failed:', error);
        showErrorNotification('Failed to load data');
        return null;
    }
}
```

## 🚨 Common Patterns & Pitfalls

### **Authentication**
- ✅ **Do** check multiple token sources (localStorage, cookies)
- ✅ **Do** invalidate session before clearing storage
- ✅ **Do** handle 401 responses with redirect to login
- ✅ **Do** listen for postMessage authentication from ETL service
- ✅ **Do** use Backend Service for ETL navigation setup
- ✅ **Do** handle bidirectional authentication flows
- ❌ **Don't** clear localStorage before calling logout API
- ❌ **Don't** ignore authentication errors
- ❌ **Don't** make direct API calls to ETL service (use Backend Service)
- ❌ **Don't** pass tokens in URLs for navigation

### **State Management**
- ✅ **Do** use WebSocket for real-time updates
- ✅ **Do** implement fallback to polling
- ✅ **Do** debounce user input for search/filters
- ❌ **Don't** rely solely on WebSocket for critical data
- ❌ **Don't** update UI without validating data

### **Performance**
- ✅ **Do** implement lazy loading for heavy components
- ✅ **Do** use debouncing for frequent operations
- ✅ **Do** cache static data appropriately
- ❌ **Don't** load all data on initial page load
- ❌ **Don't** make unnecessary API calls

### **Accessibility**
- ✅ **Do** provide proper ARIA labels
- ✅ **Do** support keyboard navigation
- ✅ **Do** maintain focus management in modals
- ❌ **Don't** rely solely on color for information
- ❌ **Don't** ignore screen reader compatibility
