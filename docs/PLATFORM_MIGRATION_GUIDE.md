# Platform Migration Guide

This guide helps teams transition from the previous microservices architecture to the new unified Pulse Platform with embedded ETL management.

## 🔄 **Architecture Changes**

### **Before: Separate Services**
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │◄──►│   Backend       │◄──►│   ETL Service   │
│   (Port 5173)   │    │   (Port 3002)   │    │   (Port 8000)   │
│                 │    │                 │    │                 │
│ • Separate UI   │    │ • API Gateway   │    │ • Standalone UI │
│ • Direct API    │    │ • Auth Service  │    │ • Direct Access │
│ • Independent   │    │ • Data APIs     │    │ • Admin Portal  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### **After: Unified Platform**
```
┌─────────────────────────────────────────────────────────────────┐
│                    Pulse Platform Frontend                     │
│                         (Port 5173)                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  📊 DORA Metrics    📈 Analytics    🔧 Settings                 │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              🔧 ETL Management (Admin Only)                │ │
│  │              iframe: localhost:8000                        │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                    │                       │
                    ▼                       ▼
┌─────────────────┐              ┌─────────────────┐
│   Backend       │◄────────────►│   ETL Service   │
│   (Port 3001)   │              │   (Port 8000)   │
│                 │              │                 │
│ • Auth Hub      │              │ • Embedded UI   │
│ • API Gateway   │              │ • Admin APIs    │
│ • Session Mgmt  │              │ • Job Control   │
└─────────────────┘              └─────────────────┘
```

## 📋 **Migration Checklist**

### **Phase 1: Backend Updates**
- [ ] Update authentication to support embedded token validation
- [ ] Add client logo management endpoints
- [ ] Implement session validation for ETL service
- [ ] Update CORS configuration for iframe embedding

### **Phase 2: ETL Service Updates**
- [ ] Add embedded mode support (`?embedded=true`)
- [ ] Implement token-based authentication from URL parameters
- [ ] Add client-specific logo loading
- [ ] Update UI for iframe compatibility (remove header in embedded mode)
- [ ] Add theme inheritance from parent application

### **Phase 3: Frontend Updates**
- [ ] Add ETL management page with iframe integration
- [ ] Implement admin-only access control for ETL menu
- [ ] Add token passing to embedded ETL service
- [ ] Update navigation to include ETL management (admin only)
- [ ] Implement theme synchronization with embedded service

### **Phase 4: Branding Updates**
- [ ] Create platform brand logo for login pages
- [ ] Add client-specific logos for internal pages
- [ ] Update logo loading logic in both services
- [ ] Test branding across all user roles and clients

## 🔧 **Code Changes Required**

### **Frontend Changes**

**1. Add ETL Management Route:**
```typescript
// Add to router configuration
{
  path: '/etl',
  element: <ETLManagement />,
  meta: { requiresAdmin: true }
}
```

**2. Create ETL Component:**
```typescript
const ETLManagement: React.FC = () => {
  const { user, token } = useAuth();
  const { theme, colorMode } = useTheme();
  
  if (!user?.is_admin) {
    return <AccessDenied />;
  }
  
  const etlUrl = `http://localhost:8000/dashboard?embedded=true&token=${token}&theme=${theme}&colorMode=${colorMode}`;
  
  return (
    <iframe
      src={etlUrl}
      className="w-full h-full border-0"
      title="ETL Management"
    />
  );
};
```

**3. Update Navigation:**
```typescript
const navigationItems = [
  { name: 'Home', path: '/home', icon: HomeIcon },
  { name: 'DORA Metrics', path: '/dora', icon: ChartIcon },
  { name: 'Analytics', path: '/analytics', icon: AnalyticsIcon },
  // Add ETL for admin users only
  ...(user?.is_admin ? [
    { name: 'ETL Management', path: '/etl', icon: DatabaseIcon }
  ] : []),
  { name: 'Settings', path: '/settings', icon: SettingsIcon }
];
```

### **ETL Service Changes**

**1. Add Embedded Mode Support:**
```python
@app.middleware("http")
async def embedded_mode_middleware(request: Request, call_next):
    # Check for embedded mode
    is_embedded = request.query_params.get('embedded') == 'true'
    
    # Store in request state for templates
    request.state.embedded = is_embedded
    
    response = await call_next(request)
    return response
```

**2. Update Authentication:**
```python
async def get_auth_token(request: Request) -> str:
    # Check URL parameter first (for embedded mode)
    token = request.query_params.get('token')
    
    if not token:
        # Fall back to cookie/header
        token = request.cookies.get('pulse_token')
        if not token:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header[7:]
    
    return token
```

**3. Update Templates:**
```html
<!-- Add embedded mode check -->
{% if not request.state.embedded %}
<header class="main-header">
  <!-- Header content -->
</header>
{% endif %}

<main class="{% if request.state.embedded %}embedded-content{% else %}normal-content{% endif %}">
  <!-- Page content -->
</main>
```

### **Backend Service Changes**

**1. Add Token Validation Endpoint:**
```javascript
// Add endpoint for ETL service to validate tokens
app.get('/api/v1/auth/validate-token', authenticateToken, (req, res) => {
  res.json({
    valid: true,
    user: req.user
  });
});
```

**2. Update CORS Configuration:**
```javascript
app.use(cors({
  origin: [
    'http://localhost:5173',  // Frontend
    'http://localhost:8000',  // ETL Service
  ],
  credentials: true
}));
```

## 🧪 **Testing Migration**

### **1. Authentication Flow**
- [ ] Login via main platform works
- [ ] Admin users can access ETL management
- [ ] Non-admin users cannot see ETL menu
- [ ] Token validation works across services

### **2. Embedded Interface**
- [ ] ETL iframe loads correctly
- [ ] Theme inheritance works
- [ ] Client logos display correctly
- [ ] All ETL functionality works in embedded mode

### **3. Branding**
- [ ] Login pages show platform branding
- [ ] Internal pages show client-specific logos
- [ ] Logo switching works for different clients
- [ ] Fallback logos work when client logo missing

### **4. User Experience**
- [ ] Navigation feels seamless
- [ ] No authentication prompts in embedded mode
- [ ] Real-time updates work across iframe boundary
- [ ] Responsive design works on all screen sizes

## 🚀 **Deployment Strategy**

### **Rolling Deployment**
1. **Deploy Backend Service** - Update authentication and CORS
2. **Deploy ETL Service** - Add embedded mode support
3. **Deploy Frontend** - Add ETL management integration
4. **Update Documentation** - Reflect new architecture

### **Rollback Plan**
- Keep previous service versions available
- Database schema remains compatible
- Can revert to separate service access if needed
- Monitor for any integration issues

## 📊 **Success Metrics**

### **Technical Metrics**
- [ ] Authentication success rate > 99%
- [ ] iframe loading time < 2 seconds
- [ ] Cross-service token validation < 100ms
- [ ] Zero authentication errors in embedded mode

### **User Experience Metrics**
- [ ] Admin users can access ETL without additional login
- [ ] Navigation between platform and ETL feels seamless
- [ ] No user complaints about access or functionality
- [ ] Consistent branding across all interfaces

## 🔍 **Troubleshooting**

### **Common Issues**

**1. iframe Not Loading:**
- Check CORS configuration
- Verify token is being passed correctly
- Check for JavaScript console errors

**2. Authentication Failures:**
- Verify JWT secret is consistent across services
- Check token expiration times
- Validate Backend Service is accessible from ETL

**3. Branding Issues:**
- Verify client logo files exist in static directories
- Check logo mapping configuration
- Test with different client users

**4. Theme Inheritance:**
- Verify theme parameters are passed in URL
- Check CSS variable inheritance
- Test theme switching in parent application

This migration guide ensures a smooth transition to the unified Pulse Platform architecture while maintaining all existing functionality.
