# Frontend App Guide

This guide covers frontend application patterns, UI/UX standards, and client-side functionality.

## 🎨 UI/UX Standards

### **Design System**
- **Framework**: Bootstrap 5.3.0 for responsive components
- **Typography**: Inter font family for modern, clean appearance
- **Color Palette**: Professional blue/violet/emerald with client customization
- **Theme Support**: Light/dark mode with 5-color client schemas

### **Brand Colors**
```css
/* Core brand colors */
:root {
    --brand-primary: #C8102E;    /* WEX Red */
    --brand-secondary: #253746;  /* Dark Blue */
    --brand-accent: #00C7B1;     /* Teal */
    --brand-light: #A2DDF8;      /* Light Blue */
    --brand-warning: #FFBF3F;    /* Yellow */
}
```

### **Component Standards**
- **Modals**: Consistent black/dark background styling
- **Cards**: Clean minimalism over glassmorphism effects
- **Buttons**: Accessible with proper focus states
- **Forms**: Validation feedback with clear error messages

## 🔐 Authentication Flow

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

### **Light/Dark Mode**
```javascript
// Theme management
class ThemeManager {
    constructor() {
        this.currentTheme = localStorage.getItem('theme') || 'light';
        this.applyTheme(this.currentTheme);
    }
    
    toggleTheme() {
        this.currentTheme = this.currentTheme === 'light' ? 'dark' : 'light';
        this.applyTheme(this.currentTheme);
        localStorage.setItem('theme', this.currentTheme);
    }
    
    applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        this.updateThemeIcon(theme);
    }
}
```

### **Client Color Schemas**
```css
/* 5-color client schema system */
[data-client-schema="wex"] {
    --primary: #C8102E;
    --secondary: #253746;
    --accent: #00C7B1;
    --light: #A2DDF8;
    --warning: #FFBF3F;
}

[data-client-schema="custom"] {
    --primary: var(--client-primary, #007bff);
    --secondary: var(--client-secondary, #6c757d);
    --accent: var(--client-accent, #28a745);
    --light: var(--client-light, #f8f9fa);
    --warning: var(--client-warning, #ffc107);
}
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
- ❌ **Don't** clear localStorage before calling logout API
- ❌ **Don't** ignore authentication errors

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
